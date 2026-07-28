"""
自适应多表合并（通用，非特定数据集特判）。

参考 Spark unionByName / DuckDB union_by_name 思路：
1. 按列名集合聚类（schema fingerprint）
2. 同 schema → 竖向合并（按列名对齐，缺列填空）
3. 异 schema 且行数接近、列重叠很低 → 视为互补矩阵，横向拼接
4. 异 schema 但共享主键（battery_id/sol/…）→ 以最大事实表为左表 left join 维表
5. 多候选按「数值信息量优先」打分；禁止「3 行脏合并」压过数万行大表

目标：目录多文件时尽量利用同键维表丰富主表，同时绝不因错误 join 把大数据压成几行。
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

SchemaFp = frozenset

# 实体/运行级主键（优先）；时间戳类放最后，且单独提高门槛
_JOIN_KEY_CANDIDATES = (
    "battery_id",
    "cell_id",
    "device_id",
    "sol",
    "run_id",
    "run",
    "trial_id",
    "trial",
    "sample_id",
    "subject_id",
    "subject",
    "session_id",
    "session",
    "cycle_index",
    "cycle",
    "filename",
    "file_name",
    "file",
    "uid",
    "uuid",
    "id",
    "timestamp",
    "time",
    "date",
)

_WEAK_TIME_KEYS = frozenset({"timestamp", "time", "date", "datetime"})
JoinKey = Union[str, Tuple[str, ...]]


@dataclass
class TablePiece:
    path: str
    df: pd.DataFrame

    @property
    def schema_fp(self) -> SchemaFp:
        return frozenset(str(c).strip().lower() for c in self.df.columns)

    @property
    def nrows(self) -> int:
        return int(len(self.df))


def _norm_col(c: object) -> str:
    return str(c).strip().lower()


def _jaccard(a: SchemaFp, b: SchemaFp) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _null_frac(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 1.0
    try:
        return float(df.isna().mean().mean())
    except Exception:
        return 1.0


def _score(df: pd.DataFrame, *, n_sources: int = 1) -> tuple:
    """越高越好：有数值列 > 行×数值列信息量 > 纳入文件数 > 低空值 > 行列规模。

    注意：信息量必须排在「文件数」之前，否则 2 文件×3 行会压过 1 文件×2 万行。
    """
    if df is None or df.empty:
        return (0, -1, 0, -1.0, 0, 0)
    try:
        from executors.numeric_coerce import count_numeric_columns

        n_num = count_numeric_columns(df)
    except Exception:
        n_num = int(df.select_dtypes(include=["number"]).shape[1])
    nrows, ncols = len(df), int(df.shape[1])
    return (
        1 if n_num > 0 else 0,
        nrows * max(n_num, 1),
        max(1, int(n_sources)),
        -_null_frac(df),
        nrows * max(ncols, 1),
        ncols,
    )


def _ncols_compatible(a: int, b: int, tol: float = 0.08) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= tol


def _vertical_union(dfs: Sequence[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    if len(dfs) == 1:
        return dfs[0].copy()
    return pd.concat(list(dfs), ignore_index=True, sort=False)


def _horizontal_join(dfs: Sequence[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    n = min(len(d) for d in dfs)
    parts = [d.iloc[:n].reset_index(drop=True) for d in dfs]
    out = pd.concat(parts, axis=1)
    return out.loc[:, ~out.columns.duplicated()].copy()


def _cluster_by_schema(pieces: Sequence[TablePiece]) -> List[List[TablePiece]]:
    clusters: List[List[TablePiece]] = []
    fps: List[SchemaFp] = []
    ncols_ref: List[int] = []
    for p in pieces:
        placed = False
        pn = int(p.df.shape[1])
        for i, fp in enumerate(fps):
            same = p.schema_fp == fp
            close = _jaccard(p.schema_fp, fp) >= 0.85 and _ncols_compatible(pn, ncols_ref[i])
            if same or close:
                clusters[i].append(p)
                fps[i] = fps[i] | p.schema_fp
                ncols_ref[i] = max(ncols_ref[i], pn)
                placed = True
                break
        if not placed:
            clusters.append([p])
            fps.append(p.schema_fp)
            ncols_ref.append(pn)
    return clusters


def _row_compatible(a: int, b: int, tol: float = 0.02) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= tol


def _resolve_key_cols(df: pd.DataFrame, keys: Sequence[str]) -> Optional[List[str]]:
    resolved = []
    for key in keys:
        hit = None
        for c in df.columns:
            if _norm_col(c) == key:
                hit = str(c)
                break
        if hit is None:
            return None
        resolved.append(hit)
    return resolved


def _key_uniqueness(df: pd.DataFrame, key_cols: Sequence[str]) -> float:
    if df is None or df.empty or not key_cols:
        return 0.0
    n = len(df)
    if n <= 0:
        return 0.0
    return float(df.drop_duplicates(subset=list(key_cols)).shape[0]) / float(n)


def _shared_columns(dfs: Sequence[pd.DataFrame]) -> List[str]:
    counter: Counter[str] = Counter()
    for df in dfs:
        seen = set()
        for c in df.columns:
            k = _norm_col(c)
            if k and k not in seen:
                counter[k] += 1
                seen.add(k)
    return [k for k, n in counter.items() if n >= 2]


def _pick_join_keys(dfs: Sequence[pd.DataFrame]) -> List[JoinKey]:
    """返回候选主键：优先复合键 (entity, cycle)，再单键；弱化纯时间戳。"""
    if len(dfs) < 2:
        return []
    shared = set(_shared_columns(dfs))
    out: List[JoinKey] = []

    # 复合键：实体 + 周期/轮次
    entity_keys = [
        k
        for k in (
            "battery_id",
            "cell_id",
            "device_id",
            "subject_id",
            "subject",
            "sample_id",
            "run_id",
            "sol",
            "id",
        )
        if k in shared
    ]
    cycle_keys = [k for k in ("cycle_index", "cycle", "trial", "trial_id", "run") if k in shared]
    for e in entity_keys:
        for c in cycle_keys:
            if e != c:
                out.append((e, c))

    preferred = [k for k in _JOIN_KEY_CANDIDATES if k in shared and k not in _WEAK_TIME_KEYS]
    out.extend(preferred)

    # 时间戳仅在没有更好实体键时考虑
    if not preferred and not any(isinstance(x, tuple) for x in out):
        out.extend([k for k in _JOIN_KEY_CANDIDATES if k in shared and k in _WEAK_TIME_KEYS])

    # 去重保持顺序
    seen = set()
    uniq: List[JoinKey] = []
    for item in out:
        marker = item if isinstance(item, str) else tuple(item)
        if marker in seen:
            continue
        seen.add(marker)
        uniq.append(item)
    return uniq[:8]


def _dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.loc[:, ~df.columns.duplicated()].copy()


def _normalize_key_frame(df: pd.DataFrame, keys: Sequence[str]) -> Optional[pd.DataFrame]:
    cols = _resolve_key_cols(df, keys)
    if cols is None:
        return None
    part = df.copy()
    rename = {}
    for canon, actual in zip(keys, cols):
        if actual != canon:
            if canon in part.columns and actual != canon:
                part = part.rename(columns={canon: f"{canon}__dup"})
            rename[actual] = canon
    if rename:
        part = part.rename(columns=rename)
    mask = pd.Series(True, index=part.index)
    for k in keys:
        mask &= part[k].notna()
    part = part.loc[mask].copy()
    return part if not part.empty else None


def _left_enrich_on_keys(
    dfs: Sequence[pd.DataFrame],
    keys: Sequence[str],
    *,
    min_overlap: float = 0.3,
) -> Optional[Tuple[pd.DataFrame, int]]:
    """以最大表为事实表，把「键上近似唯一」的维表 left join 上去；不压缩事实表行数。"""
    prepared: List[pd.DataFrame] = []
    for df in dfs:
        part = _normalize_key_frame(df, keys)
        if part is not None:
            prepared.append(part)
    if len(prepared) < 2:
        return None

    # 事实表 = 行数最大；维表需在键上相对唯一
    prepared.sort(key=len, reverse=True)
    base = prepared[0]
    base_n = len(base)
    dims = []
    for part in prepared[1:]:
        uniq = _key_uniqueness(part, keys)
        if uniq < 0.85:
            # 另一个时序/多点表：跳过，避免先去重再 join 丢掉细节
            continue
        dims.append(part.drop_duplicates(subset=list(keys), keep="first"))
    if not dims:
        return None

    out = base
    base_keys = set(map(tuple, out[list(keys)].astype(str).itertuples(index=False, name=None)))
    used_dims = 0
    for i, part in enumerate(dims, start=1):
        other_keys = set(map(tuple, part[list(keys)].astype(str).itertuples(index=False, name=None)))
        if not base_keys or not other_keys:
            continue
        overlap = len(base_keys & other_keys) / max(1, min(len(base_keys), len(other_keys)))
        if overlap < min_overlap:
            logger.info("跳过维表#%s：keys=%s 重叠率=%.2f", i, keys, overlap)
            continue
        before_cols = set(map(_norm_col, out.columns))
        rename = {}
        for c in part.columns:
            if _norm_col(c) in keys:
                continue
            if _norm_col(c) in before_cols:
                rename[c] = f"{c}__{i}"
        if rename:
            part = part.rename(columns=rename)
        out = out.merge(part, on=list(keys), how="left")
        used_dims += 1

    if used_dims <= 0:
        return None
    out = _dedupe_columns(out)
    # 严禁把大表压成小表：合并后行数不得明显小于事实表
    if len(out) < max(1, int(base_n * 0.9)):
        logger.info(
            "拒绝键合并：结果行数 %s < 事实表 %s 的 90%% (keys=%s)",
            len(out),
            base_n,
            keys,
        )
        return None
    return out, 1 + used_dims


def _attach_combine_meta(
    df: pd.DataFrame,
    *,
    pieces: Sequence[TablePiece],
    used_paths: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    out = df.copy()
    scanned = [Path(p.path).name for p in pieces]
    used = [Path(p).name for p in (used_paths or [p.path for p in pieces])]
    meta = {
        "files_scanned": len(pieces),
        "files_used": len(used),
        "scanned_files": scanned,
        "used_files": used,
    }
    try:
        out.attrs["combine_meta"] = meta
    except Exception:
        pass
    return out


def adaptive_combine_tables(
    pieces: Sequence[TablePiece],
    *,
    max_null_frac: float = 0.55,
) -> pd.DataFrame:
    """
    对多张表做自适应合并。

    Returns:
        合并后的 DataFrame（可能为空，由调用方处理）
    """
    valid = [p for p in pieces if p.df is not None and not p.df.empty]
    if not valid:
        return pd.DataFrame()
    if len(valid) == 1:
        return _attach_combine_meta(valid[0].df, pieces=valid, used_paths=[valid[0].path])

    clusters = _cluster_by_schema(valid)
    cluster_dfs: List[pd.DataFrame] = []
    cluster_fps: List[SchemaFp] = []
    cluster_paths: List[List[str]] = []
    for group in clusters:
        merged = _vertical_union([p.df for p in group])
        cluster_dfs.append(merged)
        cluster_fps.append(frozenset().union(*[p.schema_fp for p in group]))
        cluster_paths.append([p.path for p in group])

    candidates: List[Tuple[pd.DataFrame, int, List[str]]] = []
    for df, paths in zip(cluster_dfs, cluster_paths):
        candidates.append((df, len(paths), list(paths)))

    used = set()
    for i in range(len(cluster_dfs)):
        if i in used:
            continue
        bundle = [cluster_dfs[i]]
        bundle_idx = [i]
        for j in range(i + 1, len(cluster_dfs)):
            if j in used:
                continue
            if _jaccard(cluster_fps[i], cluster_fps[j]) > 0.2:
                continue
            if not _row_compatible(len(cluster_dfs[i]), len(cluster_dfs[j])):
                continue
            bundle.append(cluster_dfs[j])
            bundle_idx.append(j)
        if len(bundle) >= 2:
            joined = _horizontal_join(bundle)
            paths = [p for idx in bundle_idx for p in cluster_paths[idx]]
            candidates.append((joined, len(paths), paths))
            used.update(bundle_idx)
            logger.info(
                "自适应横向拼接: clusters=%s rows=%s cols=%s null=%.3f",
                bundle_idx,
                len(joined),
                joined.shape[1],
                _null_frac(joined),
            )

    # 按主键把维表挂到最大事实表（不压缩大表）
    for key in _pick_join_keys(cluster_dfs):
        keys = (key,) if isinstance(key, str) else tuple(key)
        keyed_dfs = []
        keyed_paths: List[str] = []
        for df, paths in zip(cluster_dfs, cluster_paths):
            if _resolve_key_cols(df, keys) is None:
                continue
            keyed_dfs.append(df)
            keyed_paths.extend(paths)
        if len(keyed_dfs) < 2:
            continue
        min_overlap = 0.5 if any(k in _WEAK_TIME_KEYS for k in keys) else 0.3
        joined_pack = _left_enrich_on_keys(keyed_dfs, keys, min_overlap=min_overlap)
        if joined_pack is None:
            continue
        joined, n_used = joined_pack
        if _null_frac(joined) > max_null_frac + 0.15:
            logger.info(
                "按键合并候选过脏: keys=%s null=%.3f",
                keys,
                _null_frac(joined),
            )
            continue
        # 结果相对目录最大单表若缩水超过 50%，直接丢弃（防 timestamp 脏 join）
        max_single = max(len(df) for df in cluster_dfs)
        if max_single >= 100 and len(joined) < int(max_single * 0.5):
            logger.info(
                "拒绝键合并缩水: keys=%s rows=%s max_single=%s",
                keys,
                len(joined),
                max_single,
            )
            continue
        # 路径近似：用参与键合并的全部候选路径，实际挂上的维表数体现在 n_used
        candidates.append((joined, max(n_used, 2), list(dict.fromkeys(keyed_paths))))
        logger.info(
            "自适应按键富集: keys=%s rows=%s cols=%s sources≈%s null=%.3f",
            keys,
            len(joined),
            joined.shape[1],
            n_used,
            _null_frac(joined),
        )

    horiz = [c for c in candidates if c[0] is not None and not c[0].empty]
    if len(horiz) >= 2:
        best_h = max(horiz, key=lambda t: _score(t[0], n_sources=t[1]))
        similar = [best_h]
        best_fp = frozenset(_norm_col(c) for c in best_h[0].columns)
        for other in horiz:
            if other is best_h:
                continue
            ofp = frozenset(_norm_col(c) for c in other[0].columns)
            if _jaccard(best_fp, ofp) >= 0.5:
                similar.append(other)
        if len(similar) >= 2:
            same_width = all(
                _ncols_compatible(best_h[0].shape[1], s[0].shape[1]) for s in similar
            )
            if same_width:
                merged = _vertical_union([s[0] for s in similar])
                paths = [p for s in similar for p in s[2]]
                candidates.append((merged, len(set(paths)), list(dict.fromkeys(paths))))

    ranked = sorted(
        (c for c in candidates if c[0] is not None and not c[0].empty),
        key=lambda t: _score(t[0], n_sources=t[1]),
        reverse=True,
    )
    if not ranked:
        return pd.DataFrame()

    best_df, best_n, best_paths = ranked[0]
    # 最终保险：仅当目录存在「明显更大」的单簇时，才因缩水回退（避免误伤小样本目录）
    max_cluster_i = max(range(len(cluster_dfs)), key=lambda i: len(cluster_dfs[i]))
    max_cluster = cluster_dfs[max_cluster_i]
    max_n = len(max_cluster)
    if max_n >= 100 and len(best_df) < int(max_n * 0.5):
        logger.warning(
            "最佳候选行数过少(%s)相对最大单簇(%s)，回退大表",
            len(best_df),
            max_n,
        )
        best_df = max_cluster
        best_n = len(cluster_paths[max_cluster_i])
        best_paths = cluster_paths[max_cluster_i]

    if _null_frac(best_df) > max_null_frac and cluster_dfs:
        fallback_i = max(
            range(len(cluster_dfs)),
            key=lambda i: _score(cluster_dfs[i], n_sources=len(cluster_paths[i])),
        )
        fallback = cluster_dfs[fallback_i]
        logger.warning(
            "自适应合并空值过高(null=%.3f)，回退最大单簇(null=%.3f, rows=%s)",
            _null_frac(best_df),
            _null_frac(fallback),
            len(fallback),
        )
        best_df = fallback
        best_n = len(cluster_paths[fallback_i])
        best_paths = cluster_paths[fallback_i]

    logger.info(
        "自适应合并选定: rows=%s cols=%s null=%.3f clusters=%s pieces=%s used=%s",
        len(best_df),
        best_df.shape[1],
        _null_frac(best_df),
        len(clusters),
        len(valid),
        best_n,
    )
    return _attach_combine_meta(best_df, pieces=valid, used_paths=best_paths)


def stem_group_key(path: str) -> Optional[str]:
    """可选：从文件名提取数字后缀分组键（通用启发式，非业务特判）。"""
    name = Path(path).stem
    m = re.search(r"_(\d+)$", name)
    return m.group(1) if m else None
