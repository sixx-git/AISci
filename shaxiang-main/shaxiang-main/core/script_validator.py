"""
脚本可执行性校验与小样本试跑门禁。
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from schemas.experiment import ExperimentPlan
from executors.data_adapter import load_data_from_config
from executors.sandbox import SandboxExecutor

logger = logging.getLogger(__name__)

PLACEHOLDER_SCRIPT_PATTERNS = [
    r"see\s+analysis_script",
    r"见\s*analysis_script",
    r"as\s+above",
    r"同上",
    r"省略",
    r"TODO",
    r"\.\.\.\s*$",
]


def enrich_column_contract(metadata: dict, df=None) -> dict:
    """补齐数值列/非数值列等契约信息，供 LLM 与门禁使用。"""
    meta = dict(metadata or {})
    columns = list(meta.get("columns") or [])
    dtypes = dict(meta.get("dtypes") or {})

    numeric_columns = list(meta.get("numeric_columns") or [])
    non_numeric_columns = list(meta.get("non_numeric_columns") or [])

    if df is not None:
        columns = list(df.columns)
        dtypes = {col: str(df[col].dtype) for col in df.columns}
        numeric_columns = list(df.select_dtypes(include=["number"]).columns)
        non_numeric_columns = [c for c in columns if c not in numeric_columns]
        meta["row_count"] = meta.get("row_count", len(df))
        meta["column_count"] = meta.get("column_count", len(columns))

    if not numeric_columns and dtypes:
        numeric_columns = [
            c for c, dt in dtypes.items()
            if any(x in str(dt).lower() for x in ("int", "float", "number"))
        ]
    if not non_numeric_columns and columns:
        non_numeric_columns = [c for c in columns if c not in numeric_columns]

    suggested_targets = []
    for c in columns:
        cl = str(c).lower()
        if cl in {"label", "target", "y", "class", "activity", "fall", "is_fall"} or "label" in cl:
            suggested_targets.append(c)

    meta["columns"] = columns
    meta["dtypes"] = dtypes
    meta["numeric_columns"] = numeric_columns
    meta["non_numeric_columns"] = non_numeric_columns
    meta["suggested_target_columns"] = suggested_targets or (
        ["label"] if "label" in columns else (non_numeric_columns[:1] if non_numeric_columns else [])
    )

    # 多模态契约
    path_cols = [
        c for c in columns
        if str(c).lower() in {"file_path", "filepath", "path", "filename", "image", "audio", "rel_path"}
    ]
    if path_cols:
        meta["media_path_column"] = path_cols[0]
        if df is not None:
            meta["sample_paths"] = df[path_cols[0]].astype(str).head(5).tolist()
            if not meta.get("modality"):
                joined = " ".join(meta["sample_paths"]).lower()
                if any(x in joined for x in (".jpg", ".png", ".jpeg", ".webp")):
                    meta["modality"] = "image"
                elif any(x in joined for x in (".wav", ".mp3", ".flac", ".ogg")):
                    meta["modality"] = "audio"
                else:
                    meta["modality"] = "media"
    return meta


def _positive_sample_size(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def load_metadata_with_contract(data_config: dict, sample_size: int = 5000) -> dict:
    """加载数据并返回带列契约的 metadata（设计阶段默认采样加速）。"""
    probe_config = dict(data_config or {})
    # sample_size 为 0 / "0" 时视为未设置，避免全量扫百万行
    if sample_size and not _positive_sample_size(probe_config.get("sample_size")):
        probe_config["sample_size"] = sample_size
    df, metadata = load_data_from_config(probe_config)
    return enrich_column_contract(metadata, df)


def validate_plan_static(plan: ExperimentPlan) -> list[str]:
    """静态检查：脚本形态、关键字段。"""
    errors: list[str] = []
    params = plan.parameters or {}
    script = (params.get("script") or plan.analysis_script or "").strip()

    if not script:
        errors.append("缺少可执行脚本: parameters.script 与 analysis_script 均为空")
        return errors

    for pat in PLACEHOLDER_SCRIPT_PATTERNS:
        if re.search(pat, script, flags=re.IGNORECASE | re.MULTILINE):
            errors.append(f"脚本疑似占位文本，不可执行（匹配: {pat}）")
            break

    if "def run(" not in script:
        errors.append("脚本必须定义 def run(df, params) 函数")

    if len(script) < 80:
        errors.append(f"脚本过短（{len(script)} 字符），疑似不完整")

    dc = params.get("data_config")
    if not isinstance(dc, dict) or not (dc.get("source_type") or dc.get("type")):
        errors.append("parameters.data_config 缺少 source_type")
    elif not (dc.get("source_path") or dc.get("path")) and (dc.get("source_type") or dc.get("type")) != "huggingface":
        errors.append("parameters.data_config 缺少 source_path")

    script_params = params.get("script_params") or plan.script_params or {}
    feature_cols = script_params.get("feature_columns") or params.get("feature_columns")
    if isinstance(feature_cols, list):
        bad = [
            c for c in feature_cols
            if isinstance(c, str) and c.lower() in {"activity_code", "subject", "filename"}
        ]
        if bad:
            errors.append(f"feature_columns 含高风险非数值列: {bad}")

    return errors


def smoke_run_plan(
    plan: ExperimentPlan,
    data_config: Optional[dict] = None,
    sample_size: int = 10000,
    require_charts: bool = True,
    stratified: bool = True,
) -> tuple[bool, list[str], Optional[object]]:
    """
    小样本试跑门禁（图表写入 data/charts/smoke）。
    sample_size 可由上层按 LLM 的 script_params 动态传入。

    Returns:
        (ok, errors, result)  result 为 IterationResult 或 None
    """
    errors = validate_plan_static(plan)
    if errors:
        return False, errors, None

    smoke_plan = plan.model_copy(deep=True)
    params = dict(smoke_plan.parameters or {})
    sp = dict(smoke_plan.script_params or {})
    if isinstance(params.get("script_params"), dict):
        sp.update(params["script_params"])
    dc = dict(data_config or params.get("data_config") or {})
    dc["sample_size"] = int(sample_size)
    if stratified:
        dc["sample_method"] = "stratified"
        target = sp.get("target_column") or (dc.get("target_columns") or [None])[0]
        if target:
            dc["target_columns"] = [target]
    params["data_config"] = dc
    sp["sample_size"] = int(sample_size)
    params["script_params"] = sp
    script = (params.get("script") or smoke_plan.analysis_script or "").strip()
    params["script"] = script
    smoke_plan.parameters = params
    smoke_plan.script_params = sp
    smoke_plan.analysis_script = smoke_plan.analysis_script or script

    executor = SandboxExecutor(chart_dir="data/charts/smoke")
    try:
        result = executor.run(smoke_plan)
    except Exception as e:
        return False, [f"smoke_run 执行异常: {e}"], None

    if result.status != "success":
        return False, [f"smoke_run 失败: {result.error_message or result.summary}"], result

    numeric_metrics = [
        dp for dp in (result.data_points or [])
        if isinstance(dp.value, (int, float)) and dp.key not in ("dataset_rows", "dataset_columns", "error")
    ]
    if not numeric_metrics:
        return False, ["smoke_run 未返回有效数值指标"], result

    charts = []
    if require_charts:
        raw = result.raw_output or {}
        if isinstance(raw, dict):
            charts = raw.get("chart_paths") or []
        if not charts:
            return False, ["smoke_run 未产出图表文件（至少需要 1 张）"], result

    logger.info(
        "smoke_run 通过: metrics=%s charts=%s",
        len(numeric_metrics),
        len(charts) if require_charts else 0,
    )
    return True, [], result
