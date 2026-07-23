"""
自适应多表合并（通用，非特定数据集特判）。

参考 Spark unionByName / DuckDB union_by_name 思路：
1. 按列名集合聚类（schema fingerprint）
2. 同 schema → 竖向合并（按列名对齐，缺列填空）
3. 异 schema 且行数接近、列重叠很低 → 视为互补矩阵，横向拼接
4. 多候选方案按「空值率 + 覆盖行数」打分，择优；过差则回退到最大单簇

目标：目录里混有多文件、多 schema 时，自行选择 join / concat，避免盲目竖拼产生高空值脏表。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

SchemaFp = frozenset


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


def _score(df: pd.DataFrame) -> tuple[float, int, int]:
    """越高越好：优先低空值，再优先信息量（行×列），避免仅元数据窄表胜出。"""
    if df is None or df.empty:
        return (-1.0, 0, 0)
    nrows, ncols = len(df), int(df.shape[1])
    return (-_null_frac(df), nrows * max(ncols, 1), ncols)


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
            # 同簇：完全一致，或高度重叠且列数接近（避免 Choice_95 与 Choice_100 竖拼成脏表）
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


def adaptive_combine_tables(
    pieces: Sequence[TablePiece],
    *,
    max_null_frac: float = 0.45,
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
        return valid[0].df.copy()

    clusters = _cluster_by_schema(valid)
    # 每簇先竖向合并
    cluster_dfs: List[pd.DataFrame] = []
    cluster_fps: List[SchemaFp] = []
    for group in clusters:
        merged = _vertical_union([p.df for p in group])
        cluster_dfs.append(merged)
        cluster_fps.append(frozenset().union(*[p.schema_fp for p in group]))

    candidates: List[pd.DataFrame] = list(cluster_dfs)

    # 互补簇：低列重叠 + 行数接近 → 横向拼接
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
            candidates.append(joined)
            used.update(bundle_idx)
            logger.info(
                "自适应横向拼接: clusters=%s rows=%s cols=%s null=%.3f",
                bundle_idx,
                len(joined),
                joined.shape[1],
                _null_frac(joined),
            )

    # 若多个互补「试次长度」cohort（行数不同但各自已横拼），再竖向合并这些候选中最好的横拼结果
    # 这里用：对所有「单簇」与「横拼」候选，再尝试竖向合并空值可接受的子集
    # 简化：取评分最高的单一候选；若存在多个横拼结果行数不同，竖向 union
    horiz = [c for c in candidates if c is not None and not c.empty]
    if len(horiz) >= 2:
        # 仅当它们列重叠较高时才竖拼（同一逻辑表的不同 cohort）
        best_h = max(horiz, key=_score)
        similar = [best_h]
        best_fp = frozenset(str(c).strip().lower() for c in best_h.columns)
        for other in horiz:
            if other is best_h:
                continue
            ofp = frozenset(str(c).strip().lower() for c in other.columns)
            if _jaccard(best_fp, ofp) >= 0.5:
                similar.append(other)
        if len(similar) >= 2:
            # 仅列集合与列数都接近时才竖拼不同 cohort，避免 95/100/150 试次宽表互污染
            same_width = all(
                _ncols_compatible(best_h.shape[1], s.shape[1]) for s in similar
            )
            if same_width:
                candidates.append(_vertical_union(similar))

    ranked = sorted((c for c in candidates if c is not None and not c.empty), key=_score, reverse=True)
    if not ranked:
        return pd.DataFrame()

    best = ranked[0]
    # 若最佳方案仍然过脏，回退到最大单簇
    if _null_frac(best) > max_null_frac and cluster_dfs:
        fallback = max(cluster_dfs, key=_score)
        logger.warning(
            "自适应合并空值过高(null=%.3f)，回退最大单簇(null=%.3f, rows=%s)",
            _null_frac(best),
            _null_frac(fallback),
            len(fallback),
        )
        best = fallback

    logger.info(
        "自适应合并选定: rows=%s cols=%s null=%.3f clusters=%s pieces=%s",
        len(best),
        best.shape[1],
        _null_frac(best),
        len(clusters),
        len(valid),
    )
    return best.copy()


def stem_group_key(path: str) -> Optional[str]:
    """可选：从文件名提取数字后缀分组键（通用启发式，非业务特判）。"""
    name = Path(path).stem
    m = re.search(r"_(\d+)$", name)
    return m.group(1) if m else None
