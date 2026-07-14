"""验证/试点执行层级与数据真实性标注"""
from __future__ import annotations

from typing import Any, Dict, Optional


EXECUTION_TIER_LABELS: Dict[str, str] = {
    "real_sandbox": "真实沙箱",
    "real_sandbox_docker": "Docker 沙箱",
    "runtime_local": "本地联邦 Runtime",
    "flower": "Flower Runtime",
    "fate_compatible": "FATE 兼容 VFL",
    "csv_real": "真实 CSV 联邦",
    "csv_simulation": "CSV 仿真",
    "gate_blocked": "Gate 阻塞",
    "skipped": "已跳过",
    "metadata_only": "仅元数据",
    "unknown": "未知",
}

DATA_AUTHENTICITY_LABELS: Dict[str, str] = {
    "user_upload": "用户上传",
    "extracted_pdf": "PDF 抽取",
    "merged_csv": "Data Finder 合并",
    "data_finder": "Data Finder",
    "external_hf": "HuggingFace",
    "synthetic_fallback": "合成降级",
    "unknown": "未知",
}


def _infer_federated_tier(mode: str) -> str:
    mapping = {
        "runtime_local": "runtime_local",
        "flower": "flower",
        "fate_compatible": "fate_compatible",
        "uploaded_csv": "csv_real",
        "simulation": "csv_simulation",
        "gate_blocked": "gate_blocked",
        "skipped": "skipped",
    }
    return mapping.get(mode, mode or "unknown")


def annotate_validation_execution_metadata(
    small_validation: Optional[Dict[str, Any]],
    *,
    project_mode: str = "general",
) -> Dict[str, Any]:
    """为 small_validation 结果附加 execution_tier 与 data_authenticity。"""
    sv = dict(small_validation or {})
    sb = sv.get("sandbox_execution") or {}
    fp = sv.get("federated_pilot") or {}

    execution_tier = "unknown"
    data_authenticity = "unknown"
    tier_notes: list[str] = []

    if sb.get("success") is not None or sb.get("return_code") is not None:
        if sb.get("used_docker") or sb.get("docker_isolated"):
            execution_tier = "real_sandbox_docker"
        elif sb.get("pilot_fallback") or sb.get("spec_misaligned"):
            execution_tier = "metadata_only"
            tier_notes.append("沙箱产出未通过 spec 对齐验证")
        else:
            execution_tier = "real_sandbox"
        tier_notes.append("Python 沙箱执行")
        ds_src = sb.get("dataset_source") or sb.get("data_source")
        if ds_src:
            data_authenticity = str(ds_src)
        else:
            data_authenticity = "user_upload"

    if fp:
        mode = str(fp.get("execution_mode") or "")
        execution_tier = _infer_federated_tier(mode)
        tier_notes.append(f"联邦 pilot mode={mode}")
        fp_src = fp.get("data_source") or fp.get("csv_source")
        if fp_src:
            data_authenticity = str(fp_src)
        elif fp.get("merged_csv_path") or mode == "uploaded_csv":
            data_authenticity = "merged_csv"
        elif mode == "simulation":
            data_authenticity = "synthetic_fallback"

    if not fp and not sb:
        execution_tier = "skipped"
        tier_notes.append("未产生验证执行结果")

    sv["execution_tier"] = execution_tier
    sv["execution_tier_label"] = EXECUTION_TIER_LABELS.get(execution_tier, execution_tier)
    sv["data_authenticity"] = data_authenticity
    sv["data_authenticity_label"] = DATA_AUTHENTICITY_LABELS.get(data_authenticity, data_authenticity)
    sv["execution_notes"] = tier_notes
    return sv
