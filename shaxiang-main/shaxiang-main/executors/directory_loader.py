"""
目录级数据加载器

针对"一个数据集 = 一个目录 + 多个子目录 + 数千个小文件"的场景，
根据 DatasetProfile 自动递归扫描、解析、合并，输出统一 DataFrame。
"""
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from executors.data_adapter import BaseDataAdapter, DataConfig, ADAPTER_REGISTRY
from executors.dataset_profile import DatasetProfile, get_profile


class DirectoryLoader(BaseDataAdapter):
    """
    目录级数据加载器

    工作流程:
    1. 根据 DataConfig 中的 source_path(目录) + profile_name 获取 DatasetProfile
    2. 递归扫描目录，找到所有匹配 scan_pattern + file_extensions 的文件
    3. 读取每个文件为 DataFrame（处理注释行、分隔符、列名等）
    4. 根据 filename_parser / path_parser 从文件名/路径提取元信息
    5. 根据 sensor_merge 合并多个传感器文件（如 MobiAct 的 acc+gyro+ori）
    6. 合并所有文件为一个大的 DataFrame
    7. 应用标签映射、train-test 划分
    """
    adapter_type = "directory"

    def load(self, config: DataConfig) -> pd.DataFrame:
        """
        从目录加载数据

        Args:
            config: DataConfig，其中:
                - source_path: 数据集根目录路径
                - 额外字段（通过 config 传递）:
                  - profile_name: 预置 Profile 名称，如 "SisFall"
                  - profile_json: 自定义 Profile JSON 路径（与 profile_name 二选一）
                  - use_inertial_signals: bool (UCI HAR 专用，是否加载原始信号而非预提取特征)
                  - split: str (划分方式: train/test/all)
        """
        root_dir = Path(config.source_path)
        if not root_dir.exists():
            raise FileNotFoundError(f"数据集目录不存在: {root_dir}")

        # 获取 Profile
        profile_name = getattr(config, 'profile_name', None) or ""
        profile_json = getattr(config, 'profile_json', None) or ""
        if profile_name and profile_name != "AutoDetect":
            profile = get_profile(profile_name)
        elif profile_json:
            # UI / AutoDetect 存的是 JSON 字符串内容；也兼容文件路径
            raw = profile_json.strip()
            if raw.startswith("{"):
                import json
                profile = DatasetProfile.from_dict(json.loads(raw))
            else:
                profile = DatasetProfile.from_json(raw)
        else:
            raise ValueError("directory 类型需要提供 profile_name 或 profile_json")

        # 多模态：输出 file_path + label 的 manifest DataFrame（不把像素/波形展开）
        modality = (getattr(profile, "modality", None) or "tabular").lower()
        if modality in {"image", "audio", "mixed"}:
            df = self._load_media_manifest(root_dir, profile, config)
            df = self._apply_custom_rules(df, profile)
            for col in profile.drop_columns or []:
                if col in df.columns:
                    df = df.drop(columns=[col])
            return df

        # UCI HAR: 动态加载特征名（处理重复）
        if profile.custom_rules.get("features_file"):
            features_path = root_dir / profile.custom_rules["features_file"]
            if features_path.exists():
                with open(features_path, 'r', encoding='utf-8') as f:
                    feature_names = [line.strip().split(' ', 1)[1] for line in f if line.strip()]
                # 为重复特征名添加后缀 _1, _2, ...
                from collections import Counter
                name_counts = Counter()
                deduped = []
                for name in feature_names:
                    name_counts[name] += 1
                    if name_counts[name] > 1:
                        deduped.append(f"{name}_{name_counts[name]-1}")
                    else:
                        deduped.append(name)
                profile.column_names = deduped

        # 扫描文件
        files = self._scan_files(root_dir, profile)
        if not files:
            raise ValueError(f"在 {root_dir} 中未找到匹配的数据文件")

        # 读取并解析每个文件
        dataframes = []
        for file_path in files:
            df = self._read_file(file_path, profile)
            if df is not None and not df.empty:
                # 提取元信息
                meta = self._extract_metadata(file_path, root_dir, profile)
                for k, v in meta.items():
                    df[k] = v

                # UCI HAR 特殊处理：从同目录加载 label 和 subject
                if profile.custom_rules.get("load_labels_from_separate_file"):
                    self._load_uci_har_labels(df, file_path)

                dataframes.append(df)

        if not dataframes:
            raise ValueError("未能读取任何有效的数据文件")

        # 合并所有 DataFrame
        combined = pd.concat(dataframes, ignore_index=True)

        # 传感器合并
        if profile.sensor_merge.enabled:
            combined = self._merge_sensors(combined, profile)

        # 标签映射
        if profile.label_mapping and profile.label_column:
            if profile.label_column in combined.columns:
                combined[profile.label_column] = combined[profile.label_column].map(profile.label_mapping)

        # 特殊后处理
        combined = self._apply_custom_rules(combined, profile)

        # 删除不需要的列
        for col in profile.drop_columns:
            if col in combined.columns:
                combined = combined.drop(columns=[col])

        return combined

    def _scan_files(self, root_dir: Path, profile: DatasetProfile) -> list[Path]:
        """扫描目录，返回匹配的文件列表"""
        files = list(root_dir.glob(profile.scan_pattern))
        if profile.file_extensions:
            files = [f for f in files if f.suffix.lower() in profile.file_extensions]
        # 排除不需要的文件
        for pattern in profile.exclude_patterns:
            files = [f for f in files if not re.search(pattern, f.name)]
        return sorted(files)

    def _read_file(self, file_path: Path, profile: DatasetProfile) -> Optional[pd.DataFrame]:
        """读取单个文件为 DataFrame"""
        try:
            # 处理注释行
            comment = profile.comment_prefix if profile.comment_prefix else None

            # 处理特殊标记（如 MobiAct 的 @DATA）
            skip = profile.skip_rows
            if profile.custom_rules.get("find_data_marker"):
                marker = profile.custom_rules["find_data_marker"]
                skip = self._find_marker_line(file_path, marker)

            # 读取数据
            df = pd.read_csv(
                file_path,
                sep=profile.delimiter,
                header=0 if profile.has_header else None,
                names=profile.column_names if not profile.has_header else None,
                comment=comment,
                skiprows=skip,
                engine='python',
                on_bad_lines='skip',
            )

            # 去除尾部符号（如 SisFall 的分号）
            if profile.custom_rules.get("strip_suffix"):
                suffix = profile.custom_rules["strip_suffix"]
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].astype(str).str.rstrip(suffix).str.strip()
                        # 尝试转为数值
                        df[col] = pd.to_numeric(df[col], errors='coerce')

            # 删除全空列
            df = df.dropna(axis=1, how='all')
            # 删除全空行
            df = df.dropna(axis=0, how='all')

            return df
        except Exception as e:
            # 忽略无法读取的文件
            return None

    def _find_marker_line(self, file_path: Path, marker: str) -> int:
        """找到标记行，返回需要跳过的行数"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if marker in line:
                    return i + 1
        return 0

    def _extract_metadata(self, file_path: Path, root_dir: Path, profile: DatasetProfile) -> dict:
        """从文件名和路径提取元信息"""
        meta = {}
        rel_path = file_path.relative_to(root_dir)
        parts = list(rel_path.parts)

        # 文件名解析
        if profile.filename_parser.pattern and profile.filename_parser.fields:
            match = re.search(profile.filename_parser.pattern, file_path.name)
            if match:
                for i, field in enumerate(profile.filename_parser.fields):
                    meta[field] = match.group(i + 1)

        # 路径解析
        if profile.path_parser.path_components and profile.path_parser.field_names:
            for idx, field_name in zip(profile.path_parser.path_components, profile.path_parser.field_names):
                try:
                    meta[field_name] = parts[idx]
                except IndexError:
                    pass

        return meta

    def _merge_sensors(self, df: pd.DataFrame, profile: DatasetProfile) -> pd.DataFrame:
        """合并传感器数据（如 MobiAct 的 acc+gyro+ori）"""
        merge_key = profile.sensor_merge.merge_key
        if merge_key not in df.columns:
            return df

        # 确定合并的分组键（不包括 sensor_type）
        group_cols = [c for c in df.columns if c != merge_key and c not in profile.sensor_merge.merge_columns]
        if not group_cols:
            return df

        # 按分组键分组，为每种 sensor 创建独立的列（跳过 NaN）
        sensor_types = df[merge_key].dropna().unique()
        merged_dfs = []

        for sensor in sensor_types:
            if pd.isna(sensor):
                continue
            sensor_df = df[df[merge_key] == sensor].copy()
            # 重命名数据列
            for col in profile.sensor_merge.merge_columns:
                if col in sensor_df.columns:
                    sensor_df = sensor_df.rename(columns={col: f"{sensor}_{col}"})
            sensor_df = sensor_df.drop(columns=[merge_key], errors='ignore')
            merged_dfs.append(sensor_df)

        if not merged_dfs:
            return df

        # 取第一个 sensor 的 DataFrame 作为基础
        base = merged_dfs[0]
        for other in merged_dfs[1:]:
            # 找到共同的非数据列用于合并
            common_cols = list(set(base.columns) & set(other.columns) - set(profile.sensor_merge.merge_columns))
            if common_cols:
                base = base.merge(other, on=common_cols, how='outer')
            else:
                # 如果没有共同列，直接 concat
                base = pd.concat([base, other], ignore_index=True)

        return base

    def _load_uci_har_labels(self, df: pd.DataFrame, file_path: Path):
        """为 UCI HAR 加载对应的 label 和 subject"""
        parent = file_path.parent
        name = file_path.name
        # X_train.txt -> y_train.txt, subject_train.txt
        # X_test.txt -> y_test.txt, subject_test.txt
        if name.startswith("X_"):
            suffix = name[2:]  # "train.txt" or "test.txt"
            labels_file = parent / f"y_{suffix}"
            subjects_file = parent / f"subject_{suffix}"

            if labels_file.exists():
                labels = pd.read_csv(labels_file, header=None, sep=r"\s+", engine="python")
                if len(labels) == len(df):
                    df["label"] = labels.iloc[:, 0].values

            if subjects_file.exists():
                subjects = pd.read_csv(subjects_file, header=None, sep=r"\s+", engine="python")
                if len(subjects) == len(df):
                    df["subject"] = subjects.iloc[:, 0].values

            # 标记 train/test
            if "train" in suffix:
                df["split"] = "train"
            elif "test" in suffix:
                df["split"] = "test"

    def _load_media_manifest(
        self,
        root_dir: Path,
        profile: DatasetProfile,
        config: DataConfig,
    ) -> pd.DataFrame:
        """
        加载图片/音频数据集为统一 manifest：
        列至少包含 file_path；若可推断则有 label。
        """
        path_col = profile.path_column or "file_path"
        label_col = profile.label_column or "label"

        if profile.manifest_pattern:
            df = self._read_manifest_table(root_dir, profile)
            # 规范化路径列
            src_col = self._guess_path_column(df, profile.path_column)
            if src_col is None:
                raise ValueError(
                    f"manifest 中未找到路径列（尝试: {profile.path_column} / path / filepath / filename）"
                )
            abs_paths = []
            for raw in df[src_col].astype(str).tolist():
                abs_paths.append(str(self._resolve_media_path(root_dir, raw)))
            out = df.copy()
            out[path_col] = abs_paths
            if src_col != path_col and src_col in out.columns:
                # 保留原列，同时提供统一 file_path
                pass
            if label_col not in out.columns:
                for cand in ("label", "class", "category", "target", "y"):
                    if cand in out.columns:
                        out = out.rename(columns={cand: label_col})
                        break
        else:
            # ImageFolder / 扁平媒体目录
            files = self._scan_media_files(root_dir, profile)
            if not files:
                raise ValueError(f"在 {root_dir} 中未找到媒体文件")
            rows = []
            for fp in files:
                meta = self._extract_metadata(fp, root_dir, profile)
                row = {
                    path_col: str(fp.resolve()),
                    "rel_path": str(fp.relative_to(root_dir)),
                    **meta,
                }
                if label_col not in row and "label" in meta:
                    row[label_col] = meta["label"]
                rows.append(row)
            out = pd.DataFrame(rows)

        # 过滤不存在的路径
        exists_mask = out[path_col].astype(str).map(lambda p: Path(p).exists())
        missing = int((~exists_mask).sum())
        if missing:
            out = out.loc[exists_mask].reset_index(drop=True)
        if out.empty:
            raise ValueError("媒体清单为空或文件路径全部无效")

        # 加载阶段提前采样，便于 smoke / 小样验证（优先分层，避免少数类被抽没）
        sample_n = 0
        try:
            sample_n = int(getattr(config, "sample_size", 0) or 0)
        except (TypeError, ValueError):
            sample_n = 0
        if sample_n > 0 and len(out) > sample_n:
            method = (getattr(config, "sample_method", None) or "random").lower()
            strat_col = None
            if method == "stratified":
                targets = getattr(config, "target_columns", None) or []
                if targets and targets[0] in out.columns:
                    strat_col = targets[0]
                elif label_col in out.columns:
                    strat_col = label_col
            if strat_col:
                out = self._stratified_sample(out, sample_n, strat_col)
            else:
                out = out.sample(n=sample_n, random_state=42).reset_index(drop=True)

        out.attrs["modality"] = getattr(profile, "modality", "image")
        return out

    def _scan_media_files(self, root_dir: Path, profile: DatasetProfile) -> list[Path]:
        exts = {e.lower() for e in (profile.media_extensions or profile.file_extensions or [])}
        if not exts:
            modality = (profile.modality or "").lower()
            if modality == "audio":
                exts = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
            else:
                exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        files = list(root_dir.glob(profile.scan_pattern or "**/*"))
        files = [f for f in files if f.is_file() and f.suffix.lower() in exts]
        for pattern in profile.exclude_patterns or []:
            files = [f for f in files if not re.search(pattern, f.name)]
        return sorted(files)

    def _read_manifest_table(self, root_dir: Path, profile: DatasetProfile) -> pd.DataFrame:
        matches = list(root_dir.glob(profile.manifest_pattern))
        if not matches:
            raise FileNotFoundError(f"未找到 manifest: {profile.manifest_pattern}")
        path = matches[0]
        if path.suffix.lower() == ".json":
            raw = pd.read_json(path)
            if isinstance(raw, pd.Series):
                raw = raw.to_frame()
            return raw
        return pd.read_csv(
            path,
            sep=profile.delimiter or ",",
            header=0 if profile.has_header else None,
            names=profile.column_names if (not profile.has_header and profile.column_names) else None,
            engine="python",
            on_bad_lines="skip",
        )

    @staticmethod
    def _guess_path_column(df: pd.DataFrame, preferred: str = "") -> Optional[str]:
        if preferred and preferred in df.columns:
            return preferred
        candidates = [
            "file_path", "filepath", "path", "filename", "file", "image", "audio",
            "img", "wav", "relative_path", "rel_path",
        ]
        lower_map = {str(c).lower(): c for c in df.columns}
        for name in candidates:
            if name in lower_map:
                return lower_map[name]
        # 启发式：值像路径的列
        for c in df.columns:
            series = df[c].astype(str).head(8)
            if series.str.contains(r"[/\\]|\.jpg|\.png|\.wav|\.mp3", regex=True, case=False).mean() > 0.5:
                return c
        return None

    @staticmethod
    def _resolve_media_path(root_dir: Path, raw: str) -> Path:
        p = Path(raw)
        if p.is_absolute() and p.exists():
            return p
        cand = (root_dir / raw).resolve()
        if cand.exists():
            return cand
        # 仅文件名时递归查找一层常用位置
        name = Path(raw).name
        hits = list(root_dir.rglob(name))
        if hits:
            return hits[0].resolve()
        return cand

    def _apply_custom_rules(self, df: pd.DataFrame, profile: DatasetProfile) -> pd.DataFrame:
        """应用自定义规则"""
        rules = profile.custom_rules

        # SisFall: 从 activity_code 生成 label
        if rules.get("label_from_activity_code") and "activity_code" in df.columns:
            df["label"] = df["activity_code"].astype(str).str[0].map(lambda x: 1 if x == 'F' else 0)

        return df


# 注册到适配器注册表
ADAPTER_REGISTRY["directory"] = DirectoryLoader()
