"""可验证假设、结构化 replan 与 Campaign 迭代辅助逻辑"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Tuple


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
