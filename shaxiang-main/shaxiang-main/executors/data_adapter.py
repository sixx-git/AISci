"""
跨领域数据适配层

设计理念:
- 不同领域的数据格式差异巨大，通过 DataAdapter 抽象屏蔽差异
- 所有数据最终被标准化为 pandas DataFrame + metadata
- LLM 在 Plan 阶段通过 parameters.data_config 指定数据源和预处理方式
- DataAdapter 支持链式组合（加载 → 清洗 → 特征工程 → 标准化）
"""
import os
import json
import pandas as pd
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any


@dataclass
class DataConfig:
    """数据配置 — 由 LLM 在 Plan 阶段生成，嵌入到 plan.parameters["data_config"]"""
    source_type: str = "local_csv"  # local_csv, local_json, local_parquet, huggingface, uploaded, directory
    source_path: str = ""            # 文件路径或 HuggingFace dataset ID
    # 列映射 (解决不同领域列名不同的问题)
    column_mapping: dict = field(default_factory=dict)  # {"old_name": "standard_name"}
    # 预处理步骤
    preprocessing_steps: list[str] = field(default_factory=list)  # ["drop_na", "normalize", "filter_rows:age>18"]
    # 特征列和目标列
    feature_columns: list[str] = field(default_factory=list)
    target_columns: list[str] = field(default_factory=list)
    # 采样配置
    sample_size: int = 0             # 0 表示不采样，使用全部数据
    sample_method: str = "random"   # random, stratified, first_n
    # 数据过滤条件 (JSON 表达式)
    filters: list[str] = field(default_factory=list)  # ["age > 18", "score >= 0"]
    # 目录级数据集专用 (source_type == "directory")
    profile_name: str = ""           # 预置 Profile 名称
    profile_json: str = ""           # 自定义 Profile JSON 字符串

    @classmethod
    def from_dict(cls, data: dict) -> 'DataConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


class BaseDataAdapter(ABC):
    """数据适配器抽象基类"""

    adapter_type: str = "base"

    @abstractmethod
    def load(self, config: DataConfig) -> pd.DataFrame:
        """从数据源加载数据为 DataFrame"""
        ...

    def preprocess(self, df: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
        """标准化预处理流程"""
        # 1. 列映射
        if config.column_mapping:
            df = df.rename(columns=config.column_mapping)

        # 2. 过滤
        for filter_expr in config.filters:
            try:
                df = df.query(filter_expr)
            except Exception:
                pass  # 跳过无效过滤表达式

        # 3. 预处理步骤
        for step in config.preprocessing_steps:
            df = self._apply_step(df, step)

        # 4. 采样（stratified 尽量按标签分层，避免少数类被抽没）
        if config.sample_size > 0 and len(df) > config.sample_size:
            method = (config.sample_method or "random").lower()
            if method == "stratified":
                stratify_col = None
                if config.target_columns:
                    stratify_col = config.target_columns[0]
                if not stratify_col or stratify_col not in df.columns:
                    for cand in ("label", "class", "target", "y"):
                        if cand in df.columns:
                            stratify_col = cand
                            break
                if stratify_col and stratify_col in df.columns:
                    df = self._stratified_sample(df, config.sample_size, stratify_col)
                else:
                    df = df.sample(n=config.sample_size, random_state=42)
            elif method == "first_n":
                df = df.head(config.sample_size)
            else:
                df = df.sample(n=config.sample_size, random_state=42)

        return df

    @staticmethod
    def _stratified_sample(df: pd.DataFrame, n: int, col: str, random_state: int = 42) -> pd.DataFrame:
        """按标签分层抽样：每类保底后再按剩余规模比例补足，减轻极端不平衡。"""
        n = min(int(n), len(df))
        if n <= 0:
            return df.iloc[0:0].copy()
        if n >= len(df):
            return df.copy()

        groups = [(label, g) for label, g in df.groupby(col, dropna=False)]
        k = max(len(groups), 1)
        min_per = max(2, min(20, n // max(k * 2, 1)))

        chosen_parts: list[pd.DataFrame] = []
        leftovers: dict[Any, pd.DataFrame] = {}
        taken = 0
        for label, g in groups:
            take = min(len(g), min_per)
            if take <= 0:
                leftovers[label] = g
                continue
            picked = g.sample(n=take, random_state=random_state) if take < len(g) else g
            chosen_parts.append(picked)
            leftovers[label] = g.drop(index=picked.index)
            taken += take

        remaining = max(0, n - taken)
        if remaining > 0:
            left_sizes = {lb: len(rest) for lb, rest in leftovers.items() if len(rest) > 0}
            total_left = sum(left_sizes.values()) or 1
            # 先按比例分配，再把凑整误差补给剩余最多的类
            budgets = {
                lb: min(left_sizes[lb], int(remaining * left_sizes[lb] / total_left))
                for lb in left_sizes
            }
            allocated = sum(budgets.values())
            deficit = remaining - allocated
            for lb in sorted(left_sizes, key=left_sizes.get, reverse=True):
                if deficit <= 0:
                    break
                room = left_sizes[lb] - budgets[lb]
                add = min(room, deficit)
                budgets[lb] += add
                deficit -= add
            for lb, budget in budgets.items():
                if budget <= 0:
                    continue
                rest = leftovers[lb]
                chosen_parts.append(rest.sample(n=budget, random_state=random_state))

        out = pd.concat(chosen_parts).drop_duplicates() if chosen_parts else df.iloc[0:0].copy()
        if len(out) > n:
            out = out.sample(n=n, random_state=random_state)
        elif len(out) < n:
            pool = df.drop(index=out.index, errors="ignore")
            if len(pool) > 0:
                out = pd.concat([out, pool.sample(n=min(n - len(out), len(pool)), random_state=random_state)])
        return out.reset_index(drop=True)

    def load_and_preprocess(self, config: DataConfig) -> pd.DataFrame:
        """加载并预处理，返回标准化 DataFrame"""
        df = self.load(config)
        df = self.preprocess(df, config)
        return df

    def _apply_step(self, df: pd.DataFrame, step: str) -> pd.DataFrame:
        """应用单个预处理步骤"""
        if step == "drop_na":
            return df.dropna()
        elif step == "drop_duplicates":
            return df.drop_duplicates()
        elif step.startswith("normalize:"):
            # normalize:column_name → Min-Max 归一化
            col = step.split(":", 1)[1]
            if col in df.columns and df[col].dtype in ['float64', 'int64']:
                df[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min() + 1e-8)
            return df
        elif step.startswith("filter_rows:"):
            # filter_rows:condition → pandas query
            condition = step.split(":", 1)[1]
            try:
                return df.query(condition)
            except Exception:
                return df
        elif step.startswith("select_cols:"):
            # select_cols:col1,col2 → 选择特定列
            cols = step.split(":", 1)[1].split(",")
            available = [c for c in cols if c in df.columns]
            return df[available] if available else df
        return df

    def get_metadata(self, df: pd.DataFrame, config: DataConfig) -> dict:
        """提取数据集元信息，供 LLM 了解数据概况"""
        numeric_columns = list(df.select_dtypes(include=['number']).columns)
        non_numeric_columns = [c for c in df.columns if c not in numeric_columns]
        suggested_targets = [
            c for c in df.columns
            if str(c).lower() in {"label", "target", "y", "class", "activity", "fall", "is_fall"}
            or "label" in str(c).lower()
        ]
        metadata = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
            "numeric_columns": numeric_columns,
            "non_numeric_columns": non_numeric_columns,
            "suggested_target_columns": suggested_targets or (
                ["label"] if "label" in df.columns else non_numeric_columns[:1]
            ),
            "numeric_stats": {},
            "missing_values": {},
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        }
        for col in numeric_columns:
            metadata["numeric_stats"][col] = {
                "min": round(float(df[col].min()), 4),
                "max": round(float(df[col].max()), 4),
                "mean": round(float(df[col].mean()), 4),
                "std": round(float(df[col].std()), 4),
                "median": round(float(df[col].median()), 4),
            }
        for col in df.columns:
            missing = int(df[col].isna().sum())
            if missing > 0:
                metadata["missing_values"][col] = {"count": missing, "pct": round(missing / len(df) * 100, 1)}

        # 多模态 manifest：识别 file_path 列
        path_candidates = [
            c for c in df.columns
            if str(c).lower() in {"file_path", "filepath", "path", "filename", "image", "audio", "rel_path"}
        ]
        modality = getattr(df, "attrs", {}).get("modality") if hasattr(df, "attrs") else None
        if path_candidates and not modality:
            sample_vals = df[path_candidates[0]].astype(str).head(5).tolist()
            joined = " ".join(sample_vals).lower()
            if any(x in joined for x in (".jpg", ".png", ".jpeg", ".webp", ".gif")):
                modality = "image"
            elif any(x in joined for x in (".wav", ".mp3", ".flac", ".ogg", ".m4a")):
                modality = "audio"
            else:
                modality = "media"
        if modality:
            metadata["modality"] = modality
            metadata["media_path_column"] = path_candidates[0] if path_candidates else "file_path"
            metadata["sample_paths"] = (
                df[metadata["media_path_column"]].astype(str).head(5).tolist()
                if metadata["media_path_column"] in df.columns else []
            )
            if "label" in df.columns:
                try:
                    metadata["label_distribution"] = df["label"].astype(str).value_counts().head(20).to_dict()
                except Exception:
                    pass
        return metadata


class CsvAdapter(BaseDataAdapter):
    """CSV 文件适配器"""
    adapter_type = "local_csv"

    def load(self, config: DataConfig) -> pd.DataFrame:
        return pd.read_csv(config.source_path)


class JsonAdapter(BaseDataAdapter):
    """JSON 文件适配器 (支持 records 格式)"""
    adapter_type = "local_json"

    def load(self, config: DataConfig) -> pd.DataFrame:
        with open(config.source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            # 尝试找第一个 list 类型的值
            for k, v in data.items():
                if isinstance(v, list):
                    return pd.DataFrame(v)
            return pd.DataFrame([data])
        return pd.DataFrame()


class ParquetAdapter(BaseDataAdapter):
    """Parquet 文件适配器"""
    adapter_type = "local_parquet"

    def load(self, config: DataConfig) -> pd.DataFrame:
        return pd.read_parquet(config.source_path)


class HuggingFaceAdapter(BaseDataAdapter):
    """HuggingFace 数据集适配器 (需要 datasets 库)"""
    adapter_type = "huggingface"

    def load(self, config: DataConfig) -> pd.DataFrame:
        try:
            from datasets import load_dataset
            parts = config.source_path.split("/", 1)
            dataset = load_dataset(parts[0], parts[1] if len(parts) > 1 else None)
            # 取 train split 或第一个 split
            if hasattr(dataset, 'train'):
                return dataset['train'].to_pandas()
            elif isinstance(dataset, dict):
                first_key = list(dataset.keys())[0]
                return dataset[first_key].to_pandas()
            return dataset.to_pandas()
        except ImportError:
            raise ImportError("HuggingFace 适配器需要 datasets 库: pip install datasets")
        except Exception as e:
            raise RuntimeError(f"加载 HuggingFace 数据集失败: {e}")


class UploadedDataAdapter(BaseDataAdapter):
    """用户上传数据适配器 (根据文件扩展名自动选择解析器)"""
    adapter_type = "uploaded"

    def load(self, config: DataConfig) -> pd.DataFrame:
        path = Path(config.source_path)
        suffix = path.suffix.lower()
        if suffix == '.csv':
            return pd.read_csv(path)
        elif suffix in ('.json', '.jsonl'):
            if suffix == '.jsonl':
                return pd.read_json(path, lines=True)
            return pd.read_json(path)
        elif suffix == '.parquet':
            return pd.read_parquet(path)
        elif suffix == '.xlsx':
            return pd.read_excel(path)
        elif suffix == '.tsv':
            return pd.read_csv(path, sep='\t')
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")


class DirectoryAdapter(BaseDataAdapter):
    """目录级数据集适配器 — 委托 DirectoryLoader（统一扫描/合并逻辑）。"""
    adapter_type = "directory"

    def load(self, config: DataConfig) -> pd.DataFrame:
        from executors.directory_loader import DirectoryLoader

        return DirectoryLoader().load(config)

    def _load_with_profile(self, root_dir: Path, profile: 'DatasetProfile') -> pd.DataFrame:
        import re

        all_dfs = []
        from executors.glob_utils import glob_files

        files = glob_files(
            root_dir,
            profile.scan_pattern or "**/*",
            getattr(profile, "file_extensions", None),
            getattr(profile, "exclude_patterns", None),
        )

        if not files:
            raise ValueError(
                f"在 {root_dir} 中未找到匹配 {profile.scan_pattern} 的文件"
                f"（extensions={list(getattr(profile, 'file_extensions', None) or [])}）"
            )

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                df = self._read_single_file(file_path, profile)
                if df.empty:
                    continue

                if profile.filename_parser and profile.filename_parser.pattern:
                    self._parse_filename(df, file_path.name, profile.filename_parser)

                if profile.path_parser and profile.path_parser.path_components:
                    rel_path = file_path.relative_to(root_dir)
                    self._parse_path(df, rel_path, profile.path_parser)

                all_dfs.append(df)
            except Exception as e:
                import logging
                logging.warning(f"跳过文件 {file_path}: {e}")
                continue

        if not all_dfs:
            raise ValueError("未能加载任何有效数据文件")

        merged = pd.concat(all_dfs, ignore_index=True)

        if profile.sensor_merge and profile.sensor_merge.enabled:
            merged = self._merge_sensors(merged, profile.sensor_merge)

        if profile.custom_rules:
            merged = self._apply_custom_rules(merged, profile.custom_rules)

        if profile.column_names and not profile.has_header:
            col_count = min(len(profile.column_names), len(merged.columns))
            merged.columns = list(profile.column_names[:col_count]) + list(merged.columns[col_count:])

        if profile.label_column and "activity_code" in merged.columns:
            merged[profile.label_column] = merged["activity_code"].apply(
                lambda x: 1 if str(x).startswith("F") else 0
            )

        return merged

    def _read_single_file(self, file_path: Path, profile: 'DatasetProfile') -> pd.DataFrame:
        import pandas as pd

        kwargs = {
            "sep": profile.delimiter,
            "header": 0 if profile.has_header else None,
            "skiprows": profile.skip_rows,
            "engine": "python",
            "on_bad_lines": "skip",
        }

        if profile.comment_prefix:
            kwargs["comment"] = profile.comment_prefix

        if profile.column_names and not profile.has_header:
            kwargs["names"] = profile.column_names

        df = pd.read_csv(file_path, **kwargs)

        if profile.custom_rules.get("strip_suffix"):
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].str.rstrip(profile.custom_rules["strip_suffix"])

        if profile.custom_rules.get("find_data_marker"):
            marker = profile.custom_rules["find_data_marker"]
            with open(file_path, 'r', encoding='utf-8') as f:
                skip_lines = 0
                for line in f:
                    if marker in line:
                        break
                    skip_lines += 1
            kwargs["skiprows"] = skip_lines
            df = pd.read_csv(file_path, **kwargs)

        return df

    def _parse_filename(self, df: pd.DataFrame, filename: str, parser: 'FilenameParser'):
        import re
        match = re.match(parser.pattern, filename)
        if match:
            for i, field in enumerate(parser.fields):
                df[field] = match.group(i + 1)

    def _parse_path(self, df: pd.DataFrame, rel_path: Path, parser: 'PathParser'):
        parts = list(rel_path.parts)
        for i, comp in enumerate(parser.path_components):
            if comp < 0:
                idx = len(parts) + comp
            else:
                idx = comp
            if 0 <= idx < len(parts):
                df[parser.field_names[i]] = parts[idx]

    def _merge_sensors(self, df: pd.DataFrame, sensor_merge: 'SensorMerge') -> pd.DataFrame:
        if sensor_merge.merge_key not in df.columns:
            return df

        sensors = df[sensor_merge.merge_key].unique()
        if len(sensors) <= 1:
            return df

        merged_df = None
        for sensor in sensors:
            sensor_df = df[df[sensor_merge.merge_key] == sensor].copy()
            rename_map = {
                col: f"{sensor}_{col}" if col != sensor_merge.align_by else col
                for col in sensor_merge.merge_columns
                if col in sensor_df.columns
            }
            sensor_df = sensor_df.rename(columns=rename_map)
            if merged_df is None:
                merged_df = sensor_df
            else:
                if sensor_merge.align_by and sensor_merge.align_by in merged_df.columns:
                    merged_df = pd.merge(merged_df, sensor_df, on=sensor_merge.align_by, how='outer')
                else:
                    merged_df = pd.concat([merged_df, sensor_df], ignore_index=True)

        return merged_df

    def _apply_custom_rules(self, df: pd.DataFrame, rules: dict) -> pd.DataFrame:
        if rules.get("load_labels_from_separate_file"):
            import os
            root_dir = Path(df.columns[0]) if len(df) == 0 else None
            for f in ["y_train.txt", "y_test.txt", "subject_train.txt", "subject_test.txt"]:
                label_file = root_dir / f if root_dir else None
                if label_file and label_file.exists():
                    labels = pd.read_csv(label_file, header=None, squeeze=True)
                    label_col = f.replace(".txt", "")
                    df[label_col] = labels.values[:len(df)]

        if rules.get("drop_columns"):
            df = df.drop(columns=[c for c in rules["drop_columns"] if c in df.columns])

        return df


# 适配器注册表
ADAPTER_REGISTRY: dict[str, BaseDataAdapter] = {
    "local_csv": CsvAdapter(),
    "local_json": JsonAdapter(),
    "local_parquet": ParquetAdapter(),
    "huggingface": HuggingFaceAdapter(),
    "uploaded": UploadedDataAdapter(),
    "directory": DirectoryAdapter(),
}

# 热重载后仍强制使用 DirectoryLoader（避免回退到旧 DirectoryAdapter 实现）
try:
    from executors.directory_loader import DirectoryLoader as _DirectoryLoader

    ADAPTER_REGISTRY["directory"] = _DirectoryLoader()
except Exception:
    pass


def get_adapter(source_type: str) -> BaseDataAdapter:
    """根据 source_type 获取对应的适配器"""
    adapter = ADAPTER_REGISTRY.get(source_type)
    if not adapter:
        raise ValueError(f"不支持的数据源类型: {source_type}，可用: {list(ADAPTER_REGISTRY.keys())}")
    return adapter


def load_data_from_config(data_config: dict) -> tuple[pd.DataFrame, dict]:
    """
    便捷函数: 从配置字典加载数据

    Args:
        data_config: 嵌入在 plan.parameters["data_config"] 中的配置

    Returns:
        (DataFrame, metadata_dict)
    """
    # 兼容 LLM 常见别名: type/path → source_type/source_path
    normalized = dict(data_config or {})
    if "source_type" not in normalized and "type" in normalized:
        normalized["source_type"] = normalized.pop("type")
    if "source_path" not in normalized and "path" in normalized:
        normalized["source_path"] = normalized.pop("path")

    config = DataConfig.from_dict(normalized)
    adapter = get_adapter(config.source_type)
    df = adapter.load_and_preprocess(config)
    metadata = adapter.get_metadata(df, config)
    return df, metadata
