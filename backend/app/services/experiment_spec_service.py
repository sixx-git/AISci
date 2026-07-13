"""实验设计结构化契约 — 字段校验、默认推断、与 data_requirements 对齐。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.tabular_encoding_utils import _OUTCOME_NAME_HINTS


def normalize_experiment_spec(raw: Any) -> Dict[str, Any]:
    """将 LLM/规则输出的 spec 规范为固定结构。"""
    if not isinstance(raw, dict):
        raw = {}
    baselines = _as_str_list(raw.get("baselines"))
    if not baselines:
        baselines = ["Baseline（对照）", "Proposed（本文方法）"]
    features = _as_str_list(raw.get("feature_columns"))
    secondary = _as_str_list(raw.get("secondary_metrics"))
    target = _clean_column_name(raw.get("target_column"))
    return {
        "target_column": target,
        "feature_columns": features[:40],
        "baselines": baselines[:6],
        "primary_metric": str(raw.get("primary_metric") or "accuracy").strip() or "accuracy",
        "secondary_metrics": secondary[:6],
        "split_strategy": str(raw.get("split_strategy") or "row_half").strip() or "row_half",
        "task_type": str(raw.get("task_type") or "classification").strip() or "classification",
        "encoding_notes": str(raw.get("encoding_notes") or "").strip(),
        "validation_checks": _as_str_list(raw.get("validation_checks"))[:8],
    }


def build_default_spec_from_datasets(
    project_datasets: List[Dict[str, Any]],
    hypothesis: str = "",
) -> Dict[str, Any]:
    """基于 probe 元数据推断默认可执行 spec（规则层，不调用 LLM）。"""
    columns: List[str] = []
    dtypes: Dict[str, Any] = {}
    for ds in project_datasets or []:
        if not isinstance(ds, dict):
            continue
        if ds.get("data_type", "tabular") != "tabular":
            continue
        cols = ds.get("columns") or []
        if cols:
            columns = [str(c) for c in cols]
            dtypes = ds.get("dtypes") or {}
            break

    target: Optional[str] = None
    hints = list(_OUTCOME_NAME_HINTS)
    hypo_lower = (hypothesis or "").lower()
    for token in ("carcinoma", "label", "outcome", "target", "class"):
        if token in hypo_lower and token not in hints:
            hints.insert(0, token)

    for hint in hints:
        for col in columns:
            if hint in col.lower():
                target = col
                break
        if target:
            break

    feature_columns = [c for c in columns if c != target][:30]
    task_type = "classification"
    if target and dtypes.get(target) in ("DOUBLE", "FLOAT", "INTEGER", "BIGINT", "int", "float"):
        uniq_hint = len(columns)
        if uniq_hint > 0:
            task_type = "regression"

    return normalize_experiment_spec({
        "target_column": target,
        "feature_columns": feature_columns,
        "baselines": ["Baseline（对照）", "Proposed（本文方法）"],
        "primary_metric": "accuracy" if task_type == "classification" else "rmse",
        "split_strategy": "row_half",
        "task_type": task_type,
        "encoding_notes": "分类列（present/absent、a699_240 等）沙箱会自动编码为数值",
    })


def enrich_spec_from_design(spec: Dict[str, Any], design: Dict[str, Any]) -> Dict[str, Any]:
    """用实验设计文本字段补全 spec 中缺失项。"""
    out = dict(spec)
    if not out.get("primary_metric") or out.get("primary_metric") == "accuracy":
        metrics_text = str(design.get("metrics") or "").lower()
        if "f1" in metrics_text and "accuracy" not in metrics_text:
            out["primary_metric"] = "f1_score"
        elif "auc" in metrics_text:
            out["primary_metric"] = "auc"
        elif "rmse" in metrics_text or "mse" in metrics_text:
            out["primary_metric"] = "rmse"
            out["task_type"] = "regression"

    if len(out.get("baselines") or []) < 2:
        baselines = _parse_design_list(design.get("baselines"))
        if len(baselines) >= 2:
            out["baselines"] = baselines[:6]
    return normalize_experiment_spec(out)


def validate_spec_against_datasets(
    spec: Dict[str, Any],
    project_datasets: List[Dict[str, Any]],
) -> List[str]:
    """校验 spec 字段是否存在于已上传数据集，返回 data_gap 条目。"""
    if not spec or not project_datasets:
        return []

    available = collect_available_columns(project_datasets)
    if not available:
        return []

    gaps: List[str] = []
    target = spec.get("target_column")
    if target and target not in available:
        preview = "、".join(sorted(available)[:6])
        if target in _TEMPLATE_SPEC_TARGETS:
            gaps.append(
                f"实验设计目标列「{target}」来自医学分类模板示例，与已上传字段（{preview}）不一致；"
                "请上传含该标签列的数据，或重跑实验设计以根据真实字段生成 spec"
            )
        else:
            gaps.append(f"experiment_spec 目标列「{target}」不在已上传数据字段中（现有：{preview}）")

    missing_features = [
        c for c in (spec.get("feature_columns") or []) if c and c not in available
    ]
    if missing_features:
        preview = "、".join(missing_features[:5])
        suffix = f" 等{len(missing_features)}列" if len(missing_features) > 5 else ""
        gaps.append(f"experiment_spec 特征列缺失: {preview}{suffix}")

    if not target and not (spec.get("feature_columns") or []):
        gaps.append("experiment_spec 未指定 target_column 或 feature_columns，沙箱脚本可能无法对齐假设")

    return gaps


def collect_available_columns(project_datasets: List[Dict[str, Any]]) -> set[str]:
    available: set[str] = set()
    for ds in project_datasets:
        if not isinstance(ds, dict):
            continue
        for col in ds.get("columns") or ds.get("column_names") or []:
            available.add(str(col))
        preview = ds.get("preview") or []
        if preview and isinstance(preview[0], dict):
            for k in preview[0].keys():
                if not str(k).startswith("_"):
                    available.add(str(k))
    return available


_TEMPLATE_SPEC_TARGETS = frozenset({
    "carcinoma", "jaundice", "fibrosis", "phosphatase", "age",
})


def reconcile_experiment_spec_with_datasets(
    spec: Dict[str, Any],
    project_datasets: List[Dict[str, Any]],
    *,
    hypothesis: str = "",
) -> tuple[Dict[str, Any], List[str]]:
    """将 experiment_spec 与真实上传字段对齐，避免 LLM 模板列（如 carcinoma）误报。"""
    notes: List[str] = []
    out = normalize_experiment_spec(spec or {})
    available = collect_available_columns(project_datasets)

    if not available:
        target = out.get("target_column")
        if target and target in _TEMPLATE_SPEC_TARGETS:
            out["target_column"] = None
            out["feature_columns"] = []
            notes.append(
                f"已清除实验设计模板目标列「{target}」：当前无可用上传字段，"
                "请先上传数据再生成 spec"
            )
        return out, notes

    inferred = build_default_spec_from_datasets(project_datasets, hypothesis=hypothesis)
    target = out.get("target_column")

    if target and target not in available:
        inferred_target = inferred.get("target_column")
        if inferred_target and inferred_target in available:
            old = target
            out["target_column"] = inferred_target
            feats = [c for c in (inferred.get("feature_columns") or []) if c in available]
            if feats:
                out["feature_columns"] = feats
            notes.append(
                f"目标列已从模板/误指定「{old}」校正为上传数据中的「{inferred_target}」"
            )
        elif target in _TEMPLATE_SPEC_TARGETS:
            col_preview = "、".join(sorted(available)[:6])
            notes.append(
                f"目标列「{target}」为医学分类模板示例，与您上传的字段（{col_preview}）不一致"
            )
    elif not target and inferred.get("target_column") in available:
        out["target_column"] = inferred["target_column"]
        out["feature_columns"] = [
            c for c in (inferred.get("feature_columns") or []) if c in available
        ]
        notes.append(f"已根据上传数据推断目标列「{out['target_column']}」")

    return out, notes


def _filter_stale_data_gap_messages(
    messages: List[str],
    *,
    uploaded_count: int,
) -> List[str]:
    """去掉与当前上传状态矛盾的旧 data_gap（实验设计阶段缓存）。"""
    if uploaded_count <= 0:
        return messages
    stale_fragments = (
        "无可用数据集",
        "尚未上传",
        "未找到匹配的公开数据集",
    )
    filtered: List[str] = []
    for msg in messages:
        text = str(msg)
        if any(frag in text for frag in stale_fragments):
            continue
        filtered.append(text)
    return filtered


def _dedupe_blockers(blockers: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for b in blockers:
        text = str(b).strip()
        if not text or text in seen:
            continue
        # 若已有「不匹配」总述，跳过重复的 carcinoma 细项（避免三条说同一件事）
        if "目标列「" in text and any("不匹配" in x for x in out):
            if any("模板" in x or "不一致" in x for x in out):
                continue
        seen.add(text)
        out.append(text)
    return out


def assess_validation_readiness(
    experiment_design: Optional[Dict[str, Any]],
    project_datasets: Optional[List[Dict[str, Any]]] = None,
    *,
    hypothesis: str = "",
) -> Dict[str, Any]:
    """小样验证前置 gate：数据充分性与 spec 字段是否可执行。"""
    ed = experiment_design or {}
    blockers: List[str] = []
    warnings: List[str] = []
    uploaded = [d for d in (project_datasets or []) if isinstance(d, dict)]
    uploaded_count = len(uploaded)

    dr = ed.get("data_requirements") if isinstance(ed.get("data_requirements"), dict) else {}
    adequacy = dr.get("adequacy") if isinstance(dr.get("adequacy"), dict) else ed.get("data_adequacy") or {}
    status = adequacy.get("status")

    spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}
    spec, reconcile_notes = reconcile_experiment_spec_with_datasets(
        spec, uploaded, hypothesis=hypothesis or ed.get("hypothesis") or ""
    )
    warnings.extend(reconcile_notes)

    if uploaded_count == 0:
        blockers.append("尚未上传任何数据集，请先在「数据集」页上传 CSV/表格")
    elif status == "inadequate":
        reasons = _filter_stale_data_gap_messages(
            list(adequacy.get("mismatch_reasons") or []),
            uploaded_count=uploaded_count,
        )
        if not reasons:
            reasons = _filter_stale_data_gap_messages(
                list(dr.get("gaps") or ed.get("data_gap") or []),
                uploaded_count=uploaded_count,
            )
        blockers.append(
            "已上传数据与假设验证目标不匹配："
            + ("; ".join(str(r) for r in reasons[:3]) if reasons else "数据类型/字段不支持当前假设")
        )
    elif status == "partial":
        warnings.append("数据仅部分匹配假设，小样验证结果应视为 exploratory")

    if ed.get("validation_blocked") and uploaded_count > 0:
        reason = str(ed.get("validation_blocked_reason") or "")
        if reason and "尚未上传" not in reason:
            blockers.append(reason or "实验设计已标记验证阻塞")
    elif ed.get("validation_blocked") and uploaded_count == 0:
        blockers.append(str(ed.get("validation_blocked_reason") or "实验设计已标记验证阻塞"))

    stale_gaps = _filter_stale_data_gap_messages(
        list(ed.get("data_gap") or []),
        uploaded_count=uploaded_count,
    )
    for gap in stale_gaps:
        if gap and gap not in blockers and uploaded_count > 0:
            if "目标列" in gap or "特征列" in gap:
                blockers.append(gap)

    if spec and uploaded:
        spec_gaps = validate_spec_against_datasets(spec, uploaded)
        for gap in spec_gaps:
            if status == "inadequate" and "模板" in gap:
                warnings.append(gap)
            elif gap not in blockers:
                blockers.append(gap)

    gate = ed.get("executability_gate") or {}
    if gate and gate.get("passed") is False:
        for b in (gate.get("blockers") or [])[:3]:
            if b and b not in blockers:
                blockers.append(str(b))

    blockers = _dedupe_blockers(blockers)

    return {
        "blocked": bool(blockers),
        "blockers": blockers,
        "warnings": warnings,
        "experiment_spec": spec,
        "uploaded_dataset_count": uploaded_count,
        "spec_reconcile_notes": reconcile_notes,
    }


def slim_experiment_spec_for_storage(spec: Dict[str, Any]) -> Dict[str, Any]:
    """DB 持久化用的 spec 摘要。"""
    if not isinstance(spec, dict):
        return {}
    return {
        "target_column": spec.get("target_column"),
        "primary_metric": spec.get("primary_metric"),
        "task_type": spec.get("task_type"),
        "split_strategy": spec.get("split_strategy"),
        "baselines": (spec.get("baselines") or [])[:4],
        "feature_columns_count": len(spec.get("feature_columns") or []),
        "feature_columns_preview": (spec.get("feature_columns") or [])[:12],
        "encoding_notes": (spec.get("encoding_notes") or "")[:500],
    }


def format_spec_for_prompt(spec: Dict[str, Any]) -> str:
    """将 spec 格式化为脚本生成 prompt 片段。"""
    if not spec:
        return ""
    lines = ["【experiment_spec 结构化契约 — 脚本必须严格遵循】"]
    if spec.get("target_column"):
        lines.append(f"- 目标列: {spec['target_column']}")
    feats = spec.get("feature_columns") or []
    if feats:
        preview = ", ".join(feats[:15])
        if len(feats) > 15:
            preview += f" …共{len(feats)}列"
        lines.append(f"- 特征列: {preview}")
    baselines = spec.get("baselines") or []
    if baselines:
        lines.append(f"- 基线对比: {' vs '.join(baselines[:3])}")
    lines.append(f"- 主指标: {spec.get('primary_metric', 'accuracy')}")
    lines.append(f"- 任务类型: {spec.get('task_type', 'classification')}")
    lines.append(f"- 划分策略: {spec.get('split_strategy', 'row_half')}")
    if spec.get("encoding_notes"):
        lines.append(f"- 编码说明: {spec['encoding_notes']}")
    return "\n".join(lines)


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    for sep in (";", "；", "\n", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    if " vs " in text.lower():
        return [p.strip() for p in text.split(" vs ") if p.strip()]
    return [text]


def _parse_design_list(raw: Any) -> List[str]:
    return _as_str_list(raw)


def _clean_column_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "无", "未知"):
        return None
    return text


_PROXY_METRIC_SOURCES = frozenset({
    "sandbox_default_script",
    "pilot_fallback",
    "pilot_proxy",
})


def is_proxy_validation_metrics(metrics: Any) -> bool:
    """识别非 spec 对齐的代理指标（旧默认脚本 / pilot 兜底）。"""
    if not isinstance(metrics, dict):
        return True
    source = str(metrics.get("data_source") or "").strip().lower()
    if source in _PROXY_METRIC_SOURCES:
        return True
    mode = str(metrics.get("validation_mode") or "").strip().lower()
    if mode == "spec_aligned":
        return False
    if metrics.get("encoded_value_column") and not metrics.get("baseline_score"):
        return True
    if metrics.get("pilot_fallback"):
        return True
    return False


def assess_sandbox_spec_alignment(
    metrics: Any,
    spec: Optional[Dict[str, Any]],
    *,
    sandbox: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """判断沙箱产出是否真正对齐 experiment_spec 与假设验证目标。"""
    spec = normalize_experiment_spec(spec or {})
    sb = sandbox or {}
    if sb.get("pilot_fallback"):
        return {
            "aligned": False,
            "reason": "结果来自 pilot 兜底，非 experiment_spec 对齐验证",
            "validation_mode": "proxy",
        }
    if not isinstance(metrics, dict) or not metrics:
        return {
            "aligned": False,
            "reason": "沙箱未产出有效 metrics",
            "validation_mode": "none",
        }
    if is_proxy_validation_metrics(metrics):
        return {
            "aligned": False,
            "reason": "指标为代理统计，未按目标列/主指标完成基线对比",
            "validation_mode": "proxy",
        }
    mode = str(metrics.get("validation_mode") or "").strip().lower()
    primary = str(spec.get("primary_metric") or "accuracy").strip().lower()
    metric_keys = {str(k).lower() for k in metrics.keys()}
    has_primary = (
        "primary_metric" in metric_keys
        or primary in metric_keys
        or f"baseline_{primary}" in metric_keys
        or metrics.get("baseline_score") is not None
    )
    has_comparison = (
        metrics.get("baseline_score") is not None
        or metrics.get("proposed_score") is not None
        or any(k.startswith("baseline_") for k in metric_keys)
    )
    if mode == "spec_aligned" and has_primary and has_comparison:
        return {
            "aligned": True,
            "reason": "沙箱产出与 experiment_spec 对齐",
            "validation_mode": "spec_aligned",
            "primary_metric": spec.get("primary_metric"),
        }
    if has_primary and has_comparison and metrics.get("target_column"):
        return {
            "aligned": True,
            "reason": "沙箱产出包含目标列与基线对比指标",
            "validation_mode": "spec_aligned",
            "primary_metric": spec.get("primary_metric"),
        }
    return {
        "aligned": False,
        "reason": "沙箱 metrics 缺少与 experiment_spec 一致的主指标或基线对比",
        "validation_mode": mode or "incomplete",
    }
