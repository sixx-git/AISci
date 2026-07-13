"""可验证假设、结构化 replan 与 Campaign 迭代辅助逻辑"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


VFL_ALIGNMENT_MIN_RATE = 0.85


def check_vfl_alignment_gate(
    fl_context: Dict[str, Any],
    datasets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """VFL 样本对齐 gate：未通过对齐检查时不进入训练仿真。"""
    fl_setting = (fl_context or {}).get("fl_setting", "")
    if fl_setting != "vertical_fl":
        return {"passed": True, "gate": "vfl_alignment", "skipped": True}

    alignment_keys = list((fl_context or {}).get("alignment_keys") or [])
    if not alignment_keys:
        return {
            "passed": False,
            "gate": "vfl_alignment",
            "reason": "缺少 entity_id / aligned_id 对齐键字段",
            "alignment_success_rate": 0.0,
            "checks": ["alignment_keys_present"],
        }

    preview_rows: List[Dict[str, Any]] = []
    for ds in datasets or []:
        preview_rows.extend((ds.get("preview") or [])[:200])

    entity_col = next(
        (k for k in alignment_keys if k.lower().replace(" ", "_") in ("entity_id", "aligned_id")),
        alignment_keys[0],
    )
    total = len(preview_rows)
    if total == 0:
        return {
            "passed": False,
            "gate": "vfl_alignment",
            "reason": "无 preview 数据，无法估计对齐覆盖率",
            "alignment_success_rate": None,
            "checks": ["preview_available"],
        }

    non_empty = sum(
        1 for row in preview_rows
        if row.get(entity_col) not in (None, "", "nan")
    )
    rate = round(non_empty / total, 4) if total else 0.0
    passed = rate >= VFL_ALIGNMENT_MIN_RATE

    return {
        "passed": passed,
        "gate": "vfl_alignment",
        "alignment_key": entity_col,
        "alignment_success_rate": rate,
        "threshold": VFL_ALIGNMENT_MIN_RATE,
        "sample_size": total,
        "reason": (
            f"对齐覆盖率 {rate:.1%} ≥ {VFL_ALIGNMENT_MIN_RATE:.0%}"
            if passed
            else f"对齐覆盖率 {rate:.1%} < {VFL_ALIGNMENT_MIN_RATE:.0%}，需先改进 PSI/aligned_id"
        ),
        "checks": ["alignment_keys_present", "alignment_rate_threshold"],
    }


def build_verifiable_hypothesis_spec(
    hypothesis: str,
    plan: Dict[str, Any],
    fl_context: Dict[str, Any],
) -> Dict[str, Any]:
    """将假设表述为可检验、可 falsify 的结构。"""
    fl_setting = (fl_context or {}).get("fl_setting", "unknown")
    baselines = plan.get("baselines") or []
    metrics = plan.get("metrics") or []
    primary_metric = "global_accuracy"
    if fl_setting == "vertical_fl":
        primary_metric = "prediction_accuracy" if "prediction_accuracy" in metrics else "accuracy"

    claim = hypothesis.strip() or "待验证联邦学习假设"
    falsification = (
        f"若 {primary_metric} 相对 Centralized Training 提升 < 1% "
        f"且 communication_cost 未下降，则拒绝该假设"
    )
    if fl_setting == "vertical_fl":
        falsification = (
            f"若 alignment_success_rate < {VFL_ALIGNMENT_MIN_RATE} "
            f"或 {primary_metric} 未优于 Local Only，则拒绝该假设"
        )

    return {
        "claim": claim,
        "primary_metric": primary_metric,
        "comparison_baselines": baselines[:4],
        "success_criteria": [
            f"{primary_metric} 优于 Local Only（pilot 可复核）",
            "communication_cost 或 inference_latency 有可量化改善",
        ],
        "falsification_criteria": falsification,
        "stop_criteria": [
            "连续 2 轮 pilot 无指标改善",
            "alignment_success_rate 持续低于阈值",
            "privacy_leakage_risk 超过预设上限",
        ],
        "fl_setting": fl_setting,
    }


def build_general_verifiable_hypothesis_spec(
    hypothesis: str,
    hypo_meta: Optional[Dict[str, Any]] = None,
    experiment_design: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """通用科研模式 — 可 falsify 的结构化假设 spec。"""
    meta = hypo_meta or {}
    ed = experiment_design or {}
    metrics_raw = str(ed.get("metrics") or meta.get("validation_target") or "")
    primary_metric = (
        meta.get("validation_target")
        or (metrics_raw.split(",")[0].strip() if metrics_raw else "")
        or "primary_metric"
    )
    expected = str(
        meta.get("expected_measurable_effect")
        or ed.get("expected_results")
        or ""
    ).strip()
    claim = (hypothesis or meta.get("hypothesis") or "").strip() or "待验证科研假设"

    success_criteria: List[str] = []
    if expected:
        success_criteria.append(expected)
    success_criteria.append(f"{primary_metric} 达到或超过预设阈值（沙箱/pilot 可复核）")
    success_criteria.append("验证执行成功（沙箱 success 或 pilot 非 gate_blocked）")

    falsification = (
        f"若 {primary_metric} 未达预期（{expected or '见 expected_measurable_effect'}）"
        f"或沙箱/验证执行失败，则拒绝该假设"
    )

    fact_ids = list(meta.get("supporting_fact_ids") or [])
    evidence_level = meta.get("evidence_level") or "medium"
    if not fact_ids:
        evidence_level = "low"

    return {
        "claim": claim,
        "primary_metric": primary_metric,
        "comparison_baselines": [],
        "success_criteria": success_criteria[:4],
        "falsification_criteria": falsification,
        "stop_criteria": [
            "连续 2 轮验证无指标改善",
            "证据等级持续为 low 且无新 literature fact",
            "集成评审未 Accept 且质量 Gate 停滞",
        ],
        "mode": "general",
        "supporting_fact_ids": fact_ids[:12],
        "evidence_level": evidence_level,
        "dataset_field_refs": list(meta.get("dataset_field_refs") or [])[:8],
    }


def build_verifiable_hypothesis_spec_for_mode(
    hypothesis: str,
    *,
    project_mode: str = "general",
    hypo_meta: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    fl_context: Optional[Dict[str, Any]] = None,
    experiment_design: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """按项目模式构建 verifiable spec（联邦 / 通用）。"""
    if project_mode == "federated_learning":
        return build_verifiable_hypothesis_spec(
            hypothesis,
            plan or experiment_design or {},
            fl_context or (experiment_design or {}).get("fl_context") or {},
        )
    return build_general_verifiable_hypothesis_spec(
        hypothesis, hypo_meta, experiment_design
    )


def attach_verifiable_specs_to_hypotheses(
    hypothesis_generation: Dict[str, Any],
    *,
    project_mode: str = "general",
    fl_context: Optional[Dict[str, Any]] = None,
    experiment_design: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为每条假设附加 verifiable_spec，并写入 primary_verifiable_spec。"""
    hg = dict(hypothesis_generation or {})
    hypotheses = list(hg.get("hypotheses") or [])
    plan = (experiment_design or {}).get("federated_plan") or {}
    updated: List[Dict[str, Any]] = []

    for hypo in hypotheses:
        h = dict(hypo) if isinstance(hypo, dict) else {"hypothesis": str(hypo)}
        spec = build_verifiable_hypothesis_spec_for_mode(
            h.get("hypothesis", ""),
            project_mode=project_mode,
            hypo_meta=h,
            plan=plan,
            fl_context=fl_context,
            experiment_design=experiment_design,
        )
        h["verifiable_spec"] = spec
        updated.append(h)

    hg["hypotheses"] = updated
    primary_idx = int(hg.get("primary_index") or 0)
    if updated:
        primary_idx = min(max(0, primary_idx), len(updated) - 1)
        hg["primary_verifiable_spec"] = updated[primary_idx].get("verifiable_spec")
    return hg


def evaluate_verifiable_spec_against_validation(
    small_validation: Dict[str, Any],
    verifiable_spec: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """对照 verifiable_spec 与验证结果，生成可审计 checks。"""
    sv = small_validation or {}
    spec = verifiable_spec or sv.get("verifiable_hypothesis") or sv.get("verifiable_spec") or {}
    checks: List[Dict[str, Any]] = []

    sb = sv.get("sandbox_execution") or {}
    if sb.get("success") is not None or sb.get("return_code") is not None:
        passed = bool(sb.get("success")) and not bool(sb.get("pilot_fallback"))
        checks.append({
            "check_id": "sandbox_success",
            "description": "沙箱执行成功",
            "expected": "success=True",
            "actual": str(sb.get("success")),
            "passed": passed,
            "source": "sandbox_execution",
        })
        if sb.get("pilot_fallback"):
            checks.append({
                "check_id": "no_pilot_fallback",
                "description": "不得使用 pilot 兜底替代假设验证",
                "expected": "pilot_fallback=False",
                "actual": "pilot_fallback=True",
                "passed": False,
                "source": "sandbox_execution",
            })
        spec_align = sv.get("spec_alignment") or {}
        if spec_align or sb.get("metrics"):
            checks.append({
                "check_id": "spec_aligned_validation",
                "description": "沙箱产出与 experiment_spec 对齐",
                "expected": "spec_alignment.aligned=True",
                "actual": str(spec_align.get("aligned")),
                "passed": spec_align.get("aligned") is True,
                "source": "spec_alignment",
            })
        metrics = sb.get("metrics") or {}
        if metrics and spec.get("primary_metric"):
            checks.append({
                "check_id": "sandbox_metrics_present",
                "description": f"沙箱产出 metrics（主指标 {spec.get('primary_metric')}）",
                "expected": "metrics 非空",
                "actual": str(list(metrics.keys())[:5]),
                "passed": bool(metrics),
                "source": "sandbox_execution",
            })

    fp = sv.get("federated_pilot") or {}
    if fp:
        gate = fp.get("alignment_gate") or {}
        if gate and not gate.get("skipped"):
            checks.append({
                "check_id": "vfl_alignment_gate",
                "description": "VFL 对齐 gate",
                "expected": "passed=True",
                "actual": str(gate.get("passed")),
                "passed": bool(gate.get("passed")),
                "source": "federated_pilot",
            })
        mode = fp.get("execution_mode", "")
        checks.append({
            "check_id": "federated_pilot_ran",
            "description": "联邦 pilot 已执行",
            "expected": "mode 非 skipped/gate_blocked",
            "actual": mode,
            "passed": mode not in ("skipped", "gate_blocked", ""),
            "source": "federated_pilot",
        })
        comp = fp.get("metric_comparison") or []
        if comp and spec.get("primary_metric"):
            best = max(
                comp,
                key=lambda r: float(
                    r.get("global_accuracy")
                    or r.get("prediction_accuracy")
                    or r.get("accuracy")
                    or 0
                ),
            )
            acc = (
                best.get("global_accuracy")
                or best.get("prediction_accuracy")
                or best.get("accuracy")
            )
            checks.append({
                "check_id": "federated_primary_metric",
                "description": f"联邦 {spec.get('primary_metric')} 有观测值",
                "expected": "best_method accuracy 可读取",
                "actual": f"{best.get('method')}={acc}",
                "passed": acc is not None,
                "source": "federated_pilot",
            })

    evidence_level = spec.get("evidence_level")
    fact_count = len(spec.get("supporting_fact_ids") or [])
    if evidence_level == "low" or fact_count == 0:
        checks.append({
            "check_id": "evidence_sufficiency",
            "description": "文献证据支撑充分",
            "expected": "evidence_level != low 且 supporting_fact_ids ≥ 1",
            "actual": f"level={evidence_level}, facts={fact_count}",
            "passed": evidence_level not in ("low", None) and fact_count > 0,
            "source": "hypothesis_provenance",
        })

    for i, criterion in enumerate((spec.get("success_criteria") or [])[:3], start=1):
        checks.append({
            "check_id": f"success_criterion_{i}",
            "description": str(criterion)[:120],
            "expected": "验证结果支持该判据（启发式）",
            "actual": "见 sandbox/pilot checks",
            "passed": any(c.get("passed") for c in checks if c.get("source") != "hypothesis_provenance"),
            "source": "verifiable_spec",
        })

    return checks


def compute_evidence_provenance_summary(hypo: Dict[str, Any]) -> Dict[str, Any]:
    """从假设 dict 提取溯源摘要，供快照与评审使用。"""
    fact_ids = list(hypo.get("supporting_fact_ids") or [])
    return {
        "supporting_fact_count": len(fact_ids),
        "supporting_fact_ids_sample": fact_ids[:8],
        "data_evidence_count": len(hypo.get("data_evidence_ids") or []),
        "dataset_field_count": len(hypo.get("dataset_field_refs") or []),
        "evidence_level": hypo.get("evidence_level") or "medium",
        "validation_target": hypo.get("validation_target") or "",
    }


def assess_evidence_sufficiency(hypo: Dict[str, Any]) -> Dict[str, Any]:
    """评审侧证据充分度评估。"""
    summary = compute_evidence_provenance_summary(hypo)
    count = summary["supporting_fact_count"]
    level = summary["evidence_level"]
    missing: List[str] = []

    if count == 0:
        missing.append("无 supporting_fact_ids")
    if level == "low":
        missing.append("证据等级为 low")
    if summary["dataset_field_count"] == 0 and summary["data_evidence_count"] == 0:
        missing.append("未绑定数据集字段或多模态 evidence")

    if count >= 3 and level == "high":
        verdict = "adequate"
    elif count >= 1:
        verdict = "weak"
    else:
        verdict = "missing"

    return {
        "evidence_sufficiency": verdict,
        "missing_evidence_types": missing,
        **summary,
    }


def build_structured_replan_actions(
    pilot: Dict[str, Any],
    fl_context: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """根据 pilot 生成可执行、可验证的结构化 replan actions。"""
    actions: List[Dict[str, Any]] = []
    mode = pilot.get("execution_mode", "skipped")
    fl_setting = fl_context.get("fl_setting", pilot.get("fl_setting", "horizontal_fl"))
    best = pilot.get("best_method", "")
    gate = pilot.get("alignment_gate") or {}

    if fl_setting == "vertical_fl" and gate and not gate.get("passed"):
        actions.append({
            "action_id": "vfl_alignment_retry",
            "action_type": "gate_remediation",
            "parameter": "aligned_sample_rate",
            "to_value": 0.95,
            "expected_check": f"alignment_success_rate >= {VFL_ALIGNMENT_MIN_RATE}",
            "priority": "critical",
            "rationale": gate.get("reason", "VFL 对齐 gate 未通过"),
            "verifiable": True,
        })
        actions.append({
            "action_id": "psi_protocol_ablation",
            "action_type": "ablation",
            "parameter": "alignment_protocol",
            "to_value": "PSI with entity_id",
            "expected_check": "alignment_keys 含 entity_id 且 preview 非空 ID ≥ 85%",
            "priority": "high",
            "rationale": "在训练仿真前必须先完成样本 ID 对齐",
            "verifiable": True,
        })

    if mode == "skipped":
        if fl_setting == "vertical_fl":
            actions.append({
                "action_id": "upload_vfl_csv",
                "action_type": "collect_data",
                "parameter": "dataset",
                "to_value": "party_id/entity_id/feature_owner/label_owner/label CSV",
                "expected_check": "fl_setting=vertical_fl 且 detected_fields ≥ 4",
                "priority": "critical",
                "rationale": "缺少 VFL 实验 CSV，无法做 uploaded_csv pilot",
                "verifiable": True,
            })
        else:
            actions.append({
                "action_id": "upload_fl_csv",
                "action_type": "collect_data",
                "parameter": "dataset",
                "to_value": "method/global_accuracy/f1_score CSV",
                "expected_check": "metric_comparison 非空且 best_method 可识别",
                "priority": "critical",
                "rationale": "缺少联邦 baseline 对比 CSV",
                "verifiable": True,
            })
        return actions[:6]

    comparison = pilot.get("metric_comparison") or []
    if best and mode in ("uploaded_csv", "simulation"):
        actions.append({
            "action_id": "sensitivity_best_method",
            "action_type": "adjust_parameter",
            "parameter": "primary_baseline",
            "to_value": best,
            "expected_check": f"下一轮 pilot 中 {best} 仍为 top-1 或 communication 下降 ≥10%",
            "priority": "medium",
            "rationale": f"当前 pilot 最佳方法为 {best}，围绕其做敏感性分析",
            "verifiable": True,
        })

    if fl_setting == "vertical_fl":
        actions.append({
            "action_id": "vfl_privacy_comm_tradeoff",
            "action_type": "grid_search",
            "parameter": "privacy_budget",
            "to_value": "0.5, 1.0, 2.0",
            "expected_check": "Pareto: accuracy↑ 且 privacy_leakage_risk↓ 或 comm↓",
            "priority": "high",
            "rationale": "VFL 需在精度—通信—隐私三维权衡",
            "verifiable": True,
        })
        if len(comparison) >= 2:
            comms = [c.get("communication_cost_mb") or c.get("communication_cost") for c in comparison[:3]]
            if comms and max(c for c in comms if c is not None) == comms[0]:
                actions.append({
                    "action_id": "switch_to_fedbcd",
                    "action_type": "change_baseline",
                    "parameter": "method",
                    "to_value": "FedBCD",
                    "expected_check": "communication_cost 相对 SplitNN 下降 ≥15%",
                    "priority": "high",
                    "rationale": "当前 top 方法通信开销偏高",
                    "verifiable": True,
                })
    elif fl_setting == "heterogeneous_fl":
        actions.append({
            "action_id": "fedmd_grid",
            "action_type": "grid_search",
            "parameter": "distillation_temperature",
            "to_value": "2.0, 4.0, 8.0",
            "expected_check": "global_accuracy 相对 FedAvg 提升 ≥1%",
            "priority": "medium",
            "rationale": "异构场景建议 FedMD/FedDF 蒸馏温度搜索",
            "verifiable": True,
        })
    elif best:
        actions.append({
            "action_id": "non_iid_sweep",
            "action_type": "adjust_parameter",
            "parameter": "non_iid_degree",
            "to_value": "0.3, 0.5, 0.8",
            "expected_check": "client_drift 与 global_accuracy 曲线可复现",
            "priority": "medium",
            "rationale": "围绕最佳方法扫描 Non-IID 程度",
            "verifiable": True,
        })

    if mode == "simulation":
        actions.append({
            "action_id": "replace_simulated_pilot",
            "action_type": "collect_data",
            "parameter": "execution_mode",
            "to_value": "uploaded_csv",
            "expected_check": "result_source 含 uploaded_csv 且 simulated=False",
            "priority": "high",
            "rationale": "当前为 simulated pilot，需真实 CSV 替换",
            "verifiable": True,
        })

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for a in actions:
        aid = a.get("action_id", "")
        if aid in seen:
            continue
        seen.add(aid)
        dedup.append(a)
    return dedup[:8]


def actions_to_feedback_constraints(actions: List[Dict[str, Any]]) -> List[str]:
    """将结构化 actions 转为注入下一轮假设/实验设计的约束语句。"""
    lines: List[str] = []
    for i, act in enumerate(actions[:6], 1):
        check = act.get("expected_check", "")
        param = act.get("parameter", "")
        to_val = act.get("to_value", "")
        rationale = act.get("rationale", "")
        lines.append(
            f"【可验证 replan #{i}】参数={param}→{to_val}；"
            f"验收条件: {check}；依据: {rationale}"
        )
    return lines


def build_campaign_lineage_text(
    pilot: Dict[str, Any],
    actions: List[Dict[str, Any]],
    verifiable_spec: Optional[Dict[str, Any]] = None,
    snapshots: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """生成报告各章下的个性化小节（Markdown ### 标题，LaTeX 导出为 subsection）。"""
    spec = verifiable_spec or {}
    mode = pilot.get("execution_mode", "skipped")
    best = pilot.get("best_method", "N/A")
    gate = pilot.get("alignment_gate") or {}

    methods_extra = (
        "### 可验证科学假设表述\n\n"
        f"- **主张**：{spec.get('claim', '—')}\n"
        f"- **主指标**：{spec.get('primary_metric', '—')}\n"
        f"- **成功判据**：{'；'.join(spec.get('success_criteria') or [])}\n"
        f"- **可 falsify 条件**：{spec.get('falsification_criteria', '—')}\n"
        f"- **停止准则**：{'；'.join(spec.get('stop_criteria') or [])}\n"
    )

    experiments_extra = "### 本轮可检验实验方案\n\n"
    experiments_extra += (
        f"- **执行模式**：{mode}（来源：{pilot.get('result_source', mode)}）\n"
        f"- **当前最优 baseline**：{best}\n"
    )
    if gate and not gate.get("skipped"):
        experiments_extra += (
            f"- **对齐 Gate**：{'通过' if gate.get('passed') else '未通过'} — "
            f"{gate.get('reason', '')}\n"
        )
    if actions:
        experiments_extra += "\n### 下一轮结构化 Replan Actions\n\n"
        for act in actions[:6]:
            experiments_extra += (
                f"- **[{act.get('priority', 'medium')}]** `{act.get('action_id')}`："
                f"调整 {act.get('parameter')} → {act.get('to_value')}；"
                f"验收：{act.get('expected_check')}\n"
            )

    results_extra = "### Pilot 实测反馈与迭代依据\n\n"
    comparison = pilot.get("metric_comparison") or []
    if comparison:
        for row in comparison[:5]:
            acc = row.get("global_accuracy") or row.get("prediction_accuracy") or row.get("accuracy")
            results_extra += (
                f"- {row.get('method')}: acc={acc}, "
                f"comm={row.get('communication_cost_mb') or row.get('communication_cost', 'N/A')}\n"
            )
    else:
        results_extra += "- 尚无 metric_comparison；请上传 CSV 或通过对齐 gate 后重跑 pilot。\n"

    if snapshots:
        results_extra += "\n### Campaign 迭代快照\n\n"
        for snap in snapshots[-4:]:
            results_extra += (
                f"- **{snap.get('label', 'R?')}**：假设片段={str(snap.get('hypothesis', ''))[:80]}…；"
                f"沙箱={snap.get('sandbox_success')}；"
                f"federated_best={snap.get('federated_best_method', '—')}\n"
            )

    rationale_extra = (
        "### 假设—实验—反馈闭环\n\n"
        "系统依据 pilot 结果生成结构化 replan actions，每条 action 含 expected_check，"
        "可在下一轮 Pipeline 中注入实验设计与假设修订约束，形成可审计的迭代 lineage。"
    )

    return {
        "methods": methods_extra,
        "experiments": experiments_extra,
        "results": results_extra,
        "rationale": rationale_extra,
    }


def append_subsections_to_chapter(existing: Any, extra: str) -> str:
    """将 ### 小节追加到章节正文（不改变主 section 结构）。"""
    base = str(existing or "").strip()
    addition = (extra or "").strip()
    if not addition:
        return base
    if not base:
        return addition
    return f"{base}\n\n{addition}"


def _metric_row_values(row: Dict[str, Any]) -> Tuple[float, float, float]:
    acc = row.get("global_accuracy") or row.get("prediction_accuracy") or row.get("accuracy") or 0.0
    comm = row.get("communication_cost_mb") or row.get("communication_cost") or 0.0
    privacy = row.get("privacy_leakage_risk") or row.get("privacy_risk_score")
    if privacy is None:
        privacy = 0.5
    try:
        return float(acc), float(comm), float(privacy)
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.5


def compute_pareto_frontier(metric_comparison: List[Dict[str, Any]]) -> Dict[str, Any]:
    """精度（最大化）与通信（最小化）二维 Pareto 前沿。"""
    points: List[Dict[str, Any]] = []
    for row in metric_comparison or []:
        acc, comm, privacy = _metric_row_values(row)
        points.append({
            "method": row.get("method", ""),
            "accuracy": round(acc, 4),
            "communication_cost": round(comm, 4),
            "privacy_risk": round(privacy, 4),
            "simulated": bool(row.get("simulated")),
        })

    frontier: List[Dict[str, Any]] = []
    for p in points:
        dominated = False
        for q in points:
            if q["method"] == p["method"]:
                continue
            if q["accuracy"] >= p["accuracy"] and q["communication_cost"] <= p["communication_cost"]:
                if q["accuracy"] > p["accuracy"] or q["communication_cost"] < p["communication_cost"]:
                    dominated = True
                    break
        if not dominated:
            frontier.append(p)

    frontier.sort(key=lambda x: (-x["accuracy"], x["communication_cost"]))
    best = frontier[0] if frontier else (max(points, key=lambda x: x["accuracy"]) if points else None)

    return {
        "points": points,
        "frontier": frontier,
        "frontier_3d": compute_pareto_frontier_3d(metric_comparison).get("frontier_3d", []),
        "best_tradeoff_method": best.get("method") if best else "",
        "dimension_notes": "accuracy↑ vs communication_cost↓（privacy_risk 供三维扩展）",
    }


def compute_pareto_frontier_3d(metric_comparison: List[Dict[str, Any]]) -> Dict[str, Any]:
    """三维 Pareto：accuracy↑、communication↓、privacy_risk↓。"""
    points: List[Dict[str, Any]] = []
    for row in metric_comparison or []:
        acc, comm, privacy = _metric_row_values(row)
        points.append({
            "method": row.get("method", ""),
            "accuracy": round(acc, 4),
            "communication_cost": round(comm, 4),
            "privacy_risk": round(privacy, 4),
            "simulated": bool(row.get("simulated")),
        })

    frontier_3d: List[Dict[str, Any]] = []
    for p in points:
        dominated = False
        for q in points:
            if q["method"] == p["method"]:
                continue
            if (
                q["accuracy"] >= p["accuracy"]
                and q["communication_cost"] <= p["communication_cost"]
                and q["privacy_risk"] <= p["privacy_risk"]
            ) and (
                q["accuracy"] > p["accuracy"]
                or q["communication_cost"] < p["communication_cost"]
                or q["privacy_risk"] < p["privacy_risk"]
            ):
                dominated = True
                break
        if not dominated:
            frontier_3d.append(p)

    frontier_3d.sort(key=lambda x: (-x["accuracy"], x["communication_cost"], x["privacy_risk"]))
    best = frontier_3d[0] if frontier_3d else (min(points, key=lambda x: (x["privacy_risk"], -x["accuracy"])) if points else None)

    return {
        "points": points,
        "frontier_3d": frontier_3d,
        "best_tradeoff_method": best.get("method") if best else "",
        "axes": {
            "x": {"label": "Accuracy", "objective": "maximize"},
            "y": {"label": "Communication Cost", "objective": "minimize"},
            "z": {"label": "Privacy Leakage Risk", "objective": "minimize"},
        },
    }


def evaluate_discovery_federated_acceptance(
    hypothesis_review: Dict[str, Any],
    small_validation: Dict[str, Any],
    ensemble_accept_score: float = 6.5,
) -> Dict[str, Any]:
    """Discovery 模式：ensemble Accept + 联邦 pilot 双门槛。"""
    hr = hypothesis_review or {}
    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    decision = ensemble.get("decision") or hr.get("ensemble_decision")
    overall = ensemble.get("overall") or hr.get("ensemble_overall")
    try:
        overall_f = float(overall) if overall is not None else None
    except (TypeError, ValueError):
        overall_f = None

    ensemble_ok = decision == "Accept" or (
        overall_f is not None and overall_f >= ensemble_accept_score
    )

    fp = (small_validation or {}).get("federated_pilot") or {}
    mode = fp.get("execution_mode", "skipped")
    gate = fp.get("alignment_gate") or {}
    gate_ok = gate.get("skipped", True) or gate.get("passed", True)
    runtime_ok = mode in (
        "uploaded_csv", "runtime_local", "flower", "fate_compatible", "simulation"
    )
    federated_ok = runtime_ok and gate_ok

    accept = ensemble_ok and federated_ok
    blockers: List[str] = []
    if not ensemble_ok:
        blockers.append(f"ensemble 未 Accept（decision={decision}, overall={overall_f}）")
    if not gate_ok:
        blockers.append("VFL 对齐 gate 未通过")
    if not runtime_ok:
        blockers.append(f"联邦 pilot 无效（mode={mode}）")

    return {
        "accepted": accept,
        "ensemble_ok": ensemble_ok,
        "federated_ok": federated_ok,
        "blockers": blockers,
        "pilot_mode": mode,
        "best_method": fp.get("best_method"),
        "summary": "Discovery 双门槛通过" if accept else "；".join(blockers),
    }


def evaluate_pilot_improvement(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """对比两轮 pilot 是否改善（用于 Campaign R2 验收）。"""
    def _best_acc(pilot: Dict[str, Any]) -> float:
        comp = pilot.get("metric_comparison") or []
        if not comp:
            return 0.0
        vals = []
        for row in comp:
            acc, _, _ = _metric_row_values(row)
            vals.append(acc)
        return max(vals) if vals else 0.0

    def _mode_rank(mode: str) -> int:
        order = {
            "uploaded_csv": 5,
            "flower": 4,
            "fate_compatible": 4,
            "runtime_local": 4,
            "simulation": 2,
            "gate_blocked": 1,
            "skipped": 0,
        }
        return order.get(mode, 0)

    b_mode = before.get("execution_mode", "skipped")
    a_mode = after.get("execution_mode", "skipped")
    b_acc = _best_acc(before)
    a_acc = _best_acc(after)
    gate_before = (before.get("alignment_gate") or {}).get("passed")
    gate_after = (after.get("alignment_gate") or {}).get("passed")

    improved = (
        _mode_rank(a_mode) > _mode_rank(b_mode)
        or a_acc > b_acc + 0.005
        or (gate_before is False and gate_after is True)
    )

    return {
        "improved": improved,
        "accuracy_delta": round(a_acc - b_acc, 4),
        "mode_before": b_mode,
        "mode_after": a_mode,
        "gate_passed_after": gate_after,
        "summary": (
            f"R2 pilot {'改善' if improved else '未显著改善'}："
            f"mode {b_mode}→{a_mode}，acc Δ{a_acc - b_acc:+.4f}"
        ),
    }


def needs_federated_campaign_refinement(
    small_validation: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """判断联邦 Campaign 是否需自动第二轮（实验设计→pilot）。"""
    fp = small_validation.get("federated_pilot") or {}
    mode = fp.get("execution_mode", "skipped")
    reasons: List[str] = []

    if mode == "gate_blocked":
        reasons.append("VFL 对齐 gate 未通过")
    elif mode == "skipped":
        reasons.append("联邦 pilot 数据不足 (skipped)")
    elif mode == "simulation":
        reasons.append("当前为 simulated pilot，需迭代实验设计并争取 uploaded_csv")

    actions = fp.get("replan_actions") or (
        (fp.get("skill_outputs") or {}).get("federated_replanning") or {}
    ).get("replan_actions") or []
    if any(a.get("priority") == "critical" for a in actions):
        reasons.append("存在 critical 优先级 replan actions")
    elif mode == "uploaded_csv" and any(a.get("priority") == "high" for a in actions):
        reasons.append("uploaded_csv pilot 仍有 high 优先级 replan 待验收")

    return bool(reasons), reasons


def build_general_replan_actions(
    experiment_design: Dict[str, Any],
    small_validation: Optional[Dict[str, Any]] = None,
    data_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """通用模式：从实验设计/验证/数据上下文生成结构化 replan actions。"""
    actions: List[Dict[str, Any]] = []
    ed = experiment_design or {}
    sv = small_validation or {}
    ctx = data_context or {}

    datasets = ctx.get("datasets") or ed.get("project_datasets") or []
    uploaded_count = sum(1 for d in datasets if isinstance(d, dict))
    dr = ed.get("data_requirements") or {}
    gaps = list(ed.get("data_gap") or dr.get("gaps") or [])
    spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}

    adequacy = dr.get("adequacy") if isinstance(dr.get("adequacy"), dict) else ed.get("data_adequacy") or {}
    if adequacy.get("status") == "inadequate":
        actions.append({
            "action_id": "resolve_data_inadequacy",
            "action_type": "collect_data",
            "parameter": "dataset",
            "to_value": "; ".join(adequacy.get("what_hypothesis_needs") or [])[:200] or "与假设匹配的数据",
            "expected_check": "adequacy.status in (adequate, partial)",
            "priority": "critical",
            "rationale": "; ".join(adequacy.get("mismatch_reasons") or dr.get("gaps") or [])[:200]
            or "已上传数据不足以验证假设",
            "verifiable": True,
        })
    elif dr.get("upload_status") == "pending_upload" or (not uploaded_count and gaps):
        actions.append({
            "action_id": "upload_required_data",
            "action_type": "collect_data",
            "parameter": "dataset",
            "to_value": dr.get("required_data_description") or "与假设匹配的 CSV/表格",
            "expected_check": "upload_status=ready 且 uploaded_dataset_count>=1",
            "priority": "critical",
            "rationale": "缺少真实数据，无法完成沙箱验证",
            "verifiable": True,
        })
    elif gaps:
        actions.append({
            "action_id": "align_spec_to_uploaded_data",
            "action_type": "revise_spec",
            "parameter": "experiment_spec",
            "to_value": "仅使用已上传列名",
            "expected_check": "data_gap 为空且 target_column 存在于 CSV",
            "priority": "high",
            "rationale": f"字段缺口: {'; '.join(str(g) for g in gaps[:3])}",
            "verifiable": True,
        })

    gate = ed.get("executability_gate") or {}
    if gate and not gate.get("passed"):
        missing = gate.get("missing_columns") or gate.get("blockers") or []
        actions.append({
            "action_id": "fix_executability_gate",
            "action_type": "revise_design",
            "parameter": "methods/metrics",
            "to_value": "与现有数据列对齐",
            "expected_check": "executability_gate.passed=True",
            "priority": "critical",
            "rationale": "; ".join(str(m) for m in missing[:3]) or "计划相对数据不可执行",
            "verifiable": True,
        })

    sb = sv.get("sandbox_execution") or {}
    if sv:
        if sb and sb.get("success") is False:
            err = (sb.get("stderr") or sb.get("stdout") or "")[:180]
            actions.append({
                "action_id": "fix_analysis_script",
                "action_type": "revise_script",
                "parameter": "analysis_script",
                "to_value": "遵循 experiment_spec + 沙箱契约",
                "expected_check": "sandbox_execution.success=True",
                "priority": "critical",
                "rationale": f"沙箱失败: {err or 'return_code!=0'}",
                "verifiable": True,
            })
        elif sb.get("sandbox_incomplete") or sb.get("output_complete") is False:
            actions.append({
                "action_id": "complete_sandbox_outputs",
                "action_type": "revise_script",
                "parameter": "metrics/plots",
                "to_value": "写出 metrics.json + PLOTS_DIR/*.png",
                "expected_check": "output_complete=True 且 plots>=1",
                "priority": "high",
                "rationale": "沙箱未产出有效 metrics 或实验图",
                "verifiable": True,
            })

        if sv.get("verifiable_passed") is False:
            failed = [
                c.get("description", c.get("check_id"))
                for c in (sv.get("verifiable_checks") or [])
                if c.get("passed") is False
            ]
            actions.append({
                "action_id": "meet_verifiable_spec",
                "action_type": "adjust_validation",
                "parameter": spec.get("primary_metric") or "primary_metric",
                "to_value": "满足 verifiable_hypothesis 判据",
                "expected_check": "verifiable_passed=True",
                "priority": "high",
                "rationale": f"可验证检查未通过: {'; '.join(failed[:3])}",
                "verifiable": True,
            })

        if sv.get("pilot_analysis") and sb.get("pilot_fallback"):
            actions.append({
                "action_id": "replace_pilot_with_design_script",
                "action_type": "revise_script",
                "parameter": "analysis_script",
                "to_value": "实验设计绑定脚本应直接成功",
                "expected_check": "sandbox 成功且 pilot_fallback=False",
                "priority": "medium",
                "rationale": "当前结果来自 pilot 兜底，设计与执行未对齐",
                "verifiable": True,
            })

    dedup: List[Dict[str, Any]] = []
    seen: set = set()
    for act in actions:
        aid = str(act.get("action_id") or "")
        if aid in seen:
            continue
        seen.add(aid)
        dedup.append(act)
    return dedup[:8]


def needs_experiment_self_correction(
    results: Dict[str, Any],
    *,
    correction_count: int = 0,
    max_rounds: int = 2,
    executability_blocked: bool = False,
    validation_skipped: bool = False,
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """判断通用实验设计↔验证自纠错环是否应继续。"""
    if correction_count >= max_rounds:
        return False, ["已达 experiment_self_correction 最大轮次"], []

    ed = results.get("experiment_design") or {}
    sv = results.get("small_validation") or {}
    ctx_datasets = ed.get("project_datasets") or []
    dr = ed.get("data_requirements") or {}
    uploaded = int(dr.get("uploaded_dataset_count") or len(ctx_datasets) or 0)
    adequacy = dr.get("adequacy") if isinstance(dr.get("adequacy"), dict) else ed.get("data_adequacy") or {}

    actions = build_general_replan_actions(ed, sv if sv else None, {"datasets": ctx_datasets})
    critical_data = any(
        a.get("action_id") == "upload_required_data" and a.get("priority") == "critical"
        for a in actions
    )
    if critical_data and uploaded == 0:
        return False, ["需先上传数据后再自迭代"], actions

    reasons: List[str] = []
    if executability_blocked or validation_skipped:
        gate = ed.get("executability_gate") or {}
        if gate and not gate.get("passed"):
            reasons.append("实验可执行性 gate 未通过")

    if not sv and (executability_blocked or validation_skipped):
        if not reasons:
            reasons.append("验证被跳过，需修订实验设计")
    elif sv:
        sb = sv.get("sandbox_execution") or {}
        if sb and sb.get("success") is False:
            reasons.append("沙箱执行失败")
        if sb.get("sandbox_incomplete") or sb.get("output_complete") is False:
            reasons.append("沙箱产出不完整")
        if sv.get("verifiable_passed") is False:
            reasons.append("可验证假设检查未通过")
        if sb.get("pilot_fallback") and sb.get("success"):
            reasons.append("结果来自 pilot 兜底，设计与脚本未对齐")

    if ed.get("validation_blocked") or adequacy.get("status") == "inadequate":
        reasons.append("已上传数据与假设验证目标不匹配")

    if ed.get("data_gap") and uploaded > 0:
        reasons.append("experiment_spec 与已上传字段未完全对齐")

    if not reasons and any(a.get("priority") in ("critical", "high") for a in actions):
        reasons.append("存在待处理的结构化 replan actions")

    if sv and sv.get("verifiable_passed") is True and (sv.get("sandbox_execution") or {}).get("output_complete"):
        return False, [], actions

    return bool(reasons), reasons, actions


def evaluate_general_validation_improvement(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """对比两轮小样验证/沙箱是否改善。"""

    def _score(sv: Dict[str, Any]) -> float:
        if not sv:
            return 0.0
        sb = sv.get("sandbox_execution") or {}
        score = 0.0
        if sb.get("success"):
            score += 3.0
        if sb.get("output_complete"):
            score += 2.0
        if sv.get("verifiable_passed"):
            score += 3.0
        if sb.get("pilot_fallback"):
            score -= 1.5
        metrics = sb.get("metrics") or {}
        if metrics and metrics.get("primary_metric") is not None:
            score += 1.0
        plots = sb.get("plots") or (sv.get("artifacts") or {}).get("plots") or []
        if plots:
            score += 1.0
        return score

    b = _score(before)
    a = _score(after)
    improved = a > b + 0.25
    return {
        "improved": improved,
        "score_before": round(b, 2),
        "score_after": round(a, 2),
        "delta": round(a - b, 2),
        "summary": f"验证 {'改善' if improved else '未显著改善'}：score {b:.1f}→{a:.1f}",
    }

