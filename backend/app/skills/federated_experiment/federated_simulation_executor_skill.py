"""联邦小样验证模拟执行 Skill"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from app.core.iterative_science import check_vfl_alignment_gate
from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._utils import safe_float


class FederatedSimulationExecutorSkill(BaseSkill):
    name = "FederatedSimulationExecutor"
    description = "基于 CSV 聚合分析或生成 simulated pilot；VFL 含对齐 gate"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        datasets = input_data.get("datasets", []) or []
        fl_context = input_data.get("fl_context", {}) or {}
        plan = input_data.get("experiment_plan", {}) or {}
        fl_setting = fl_context.get("fl_setting", plan.get("fl_setting", "unknown"))

        alignment_gate = check_vfl_alignment_gate(fl_context, datasets)
        if fl_setting == "vertical_fl" and not alignment_gate.get("passed"):
            result.data = {
                "execution_mode": "gate_blocked",
                "alignment_gate": alignment_gate,
                "best_method": "",
                "metric_comparison": [],
                "non_iid_sensitivity": {},
                "communication_efficiency": {},
                "client_drift_analysis": {},
                "next_round_suggestions": [
                    alignment_gate.get("reason", "VFL 对齐 gate 未通过"),
                    "补充 entity_id/aligned_id 非空记录或提高 aligned_sample_rate 后重跑",
                ],
                "result_source": "gate_blocked: vfl_alignment",
                "fl_setting": fl_setting,
            }
            result.add_warning(alignment_gate.get("reason", "VFL 对齐 gate 未通过"))
            return result

        tabular = [d for d in datasets if d.get("data_type") == "tabular" and d.get("file_path")]
        has_fl_cols = bool(fl_context.get("detected_fields"))

        if tabular:
            from app.skills.federated_experiment.federated_runtime_executor_skill import (
                FederatedRuntimeExecutorSkill,
            )

            runtime_skill = FederatedRuntimeExecutorSkill()
            runtime_res = await runtime_skill.run(
                {
                    "datasets": datasets,
                    "fl_context": fl_context,
                    "experiment_plan": plan,
                },
                {"stage": "federated_runtime"},
            )
            runtime_data = runtime_res.data or {}
            if runtime_data.get("available") and runtime_data.get("pilot"):
                pilot = dict(runtime_data["pilot"])
                pilot["alignment_gate"] = alignment_gate
                result.data = pilot
                return result

            csv_result = self._analyze_csv(tabular[0], fl_context, plan)
            if csv_result:
                csv_result["alignment_gate"] = alignment_gate
                result.data = csv_result
                return result

            result.data = {
                "execution_mode": "uploaded_csv_analysis_failed",
                "alignment_gate": alignment_gate,
                "best_method": "",
                "metric_comparison": [],
                "non_iid_sensitivity": {},
                "communication_efficiency": {},
                "client_drift_analysis": {},
                "next_round_suggestions": [
                    "已上传 CSV 但无法解析联邦指标列（需 method/global_accuracy 或 VFL 对齐字段）",
                    "请检查列名后重新上传或在工作流中重跑小样验证",
                ],
                "result_source": "uploaded_csv_analysis_failed",
                "fl_setting": fl_setting,
            }
            result.add_warning("已上传数据但无法解析，未生成 simulated pilot")
            return result

        if has_fl_cols:
            result.add_warning("检测到联邦字段但缺少可解析 CSV")
        else:
            result.data = {
                "execution_mode": "skipped",
                "alignment_gate": alignment_gate,
                "missing_requirements": [
                    "缺少联邦实验 CSV（横向: method/global_accuracy；VFL: party_id/entity_id/label）",
                ],
                "best_method": "",
                "metric_comparison": [],
                "non_iid_sensitivity": {},
                "communication_efficiency": {},
                "client_drift_analysis": {},
                "next_round_suggestions": ["请上传包含 baseline 对比结果的 CSV 后重跑小样验证"],
                "result_source": "skipped due to missing data",
                "fl_setting": fl_setting,
            }
            return result

        result.data = {
            "execution_mode": "skipped",
            "alignment_gate": alignment_gate,
            "missing_requirements": [
                "缺少可用于联邦小样验证的 CSV（需上传真实实验结果表）",
            ],
            "best_method": "",
            "metric_comparison": [],
            "non_iid_sensitivity": {},
            "communication_efficiency": {},
            "client_drift_analysis": {},
            "next_round_suggestions": ["请上传包含 baseline 对比结果的 CSV 后重跑小样验证"],
            "result_source": "skipped due to missing data",
            "fl_setting": fl_setting,
        }
        return result

    def _analyze_csv(
        self,
        dataset: Dict[str, Any],
        fl_context: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        path = dataset.get("file_path", "")
        if not path or not os.path.exists(path):
            return None
        try:
            import pandas as pd

            ext = os.path.splitext(path)[1].lower()
            df = pd.read_excel(path) if ext in (".xlsx", ".xls") else pd.read_csv(path)
        except Exception:
            return None

        cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}
        fl_setting = fl_context.get("fl_setting", plan.get("fl_setting", "unknown"))

        method_col = cols_lower.get("method")
        if not method_col and fl_setting == "vertical_fl":
            method_col = cols_lower.get("party_id") or cols_lower.get("feature_owner")

        acc_col = (
            cols_lower.get("global_accuracy")
            or cols_lower.get("prediction_accuracy")
            or cols_lower.get("accuracy")
        )
        if not acc_col:
            return None

        if method_col:
            groups = list(df.groupby(method_col, dropna=True))
        else:
            groups = [("aggregate", df)]

        metric_comparison: List[Dict[str, Any]] = []
        for method, g in groups:
            entry = {
                "method": str(method),
                "global_accuracy": safe_float(g[acc_col].mean()),
                "prediction_accuracy": safe_float(g[acc_col].mean()),
                "sample_count": int(len(g)),
            }
            f1_col = cols_lower.get("f1_score")
            if f1_col:
                entry["f1_score"] = safe_float(g[f1_col].mean())
            comm_col = cols_lower.get("communication_cost_mb") or cols_lower.get("communication_cost")
            if comm_col:
                entry["communication_cost_mb"] = safe_float(g[comm_col].mean())
                entry["communication_cost"] = entry["communication_cost_mb"]
            drift_col = cols_lower.get("client_drift")
            if drift_col:
                entry["client_drift"] = safe_float(g[drift_col].mean())
            lat_col = cols_lower.get("inference_latency")
            if lat_col:
                entry["inference_latency"] = safe_float(g[lat_col].mean())
            metric_comparison.append(entry)

        if not metric_comparison:
            return None

        metric_comparison.sort(
            key=lambda x: (x.get("global_accuracy") or x.get("prediction_accuracy") or 0),
            reverse=True,
        )
        best = metric_comparison[0]

        non_iid_col = cols_lower.get("non_iid_degree")
        non_iid_sensitivity: Dict[str, Any] = {}
        if non_iid_col and method_col:
            for method, g in df.groupby(method_col, dropna=True):
                non_iid_sensitivity[str(method)] = {
                    "mean_non_iid_degree": safe_float(g[non_iid_col].mean()),
                    "global_accuracy": safe_float(g[acc_col].mean()),
                }

        comm_eff: Dict[str, Any] = {}
        comm_col = cols_lower.get("communication_cost_mb") or cols_lower.get("communication_cost")
        rounds_col = cols_lower.get("communication_rounds") or cols_lower.get("communication_round")
        if comm_col:
            for row in metric_comparison:
                comm_eff[row["method"]] = {
                    "communication_cost_mb": row.get("communication_cost_mb"),
                    "global_accuracy": row.get("global_accuracy"),
                    "communication_rounds": None,
                }
                if rounds_col and method_col:
                    sub = df[df[method_col] == row["method"]]
                    comm_eff[row["method"]]["communication_rounds"] = safe_float(sub[rounds_col].mean())

        drift_analysis: Dict[str, Any] = {}
        drift_col = cols_lower.get("client_drift")
        if drift_col:
            for row in metric_comparison:
                drift_analysis[row["method"]] = {"client_drift": row.get("client_drift")}

        return {
            "execution_mode": "uploaded_csv",
            "best_method": best.get("method", ""),
            "metric_comparison": metric_comparison,
            "non_iid_sensitivity": non_iid_sensitivity,
            "communication_efficiency": comm_eff,
            "client_drift_analysis": drift_analysis,
            "next_round_suggestions": [
                f"优先复现最佳方法 {best.get('method')} 并扩大样本/参与方",
                "补充 counter baseline（Local Only / Centralized）对比",
            ],
            "result_source": f"uploaded_csv analysis: {dataset.get('filename', 'dataset')}",
            "fl_setting": fl_setting,
        }

    def _build_simulation(self, plan: Dict[str, Any], fl_context: Dict[str, Any]) -> Dict[str, Any]:
        fl_setting = fl_context.get("fl_setting", plan.get("fl_setting", "horizontal_fl"))
        baselines = (plan.get("baselines") or ["FedAvg", "FedProx", "SCAFFOLD"])[:4]
        if fl_setting == "vertical_fl":
            baselines = (plan.get("baselines") or [
                "Centralized Training", "Local Only", "SplitNN", "VFL-LR",
            ])[:4]

        metric_comparison = []
        for i, method in enumerate(baselines):
            acc = round(0.62 + i * 0.04, 4)
            entry = {
                "method": method,
                "global_accuracy": acc,
                "prediction_accuracy": acc,
                "f1_score": round(acc - 0.02, 4),
                "communication_cost_mb": round(80 + i * 15, 2),
                "simulated": True,
            }
            if fl_setting != "vertical_fl":
                entry["client_drift"] = round(0.15 - i * 0.02, 4)
            else:
                entry["inference_latency"] = round(12 + i * 2, 2)
            metric_comparison.append(entry)

        metric_comparison.sort(key=lambda x: x["global_accuracy"], reverse=True)
        return {
            "execution_mode": "simulation",
            "best_method": metric_comparison[0]["method"],
            "metric_comparison": metric_comparison,
            "non_iid_sensitivity": {"note": "simulated sweep (marked simulated)"},
            "communication_efficiency": {
                m["method"]: {
                    "communication_cost_mb": m["communication_cost_mb"],
                    "global_accuracy": m["global_accuracy"],
                }
                for m in metric_comparison
            },
            "client_drift_analysis": {
                m["method"]: {"client_drift": m.get("client_drift")}
                for m in metric_comparison
                if m.get("client_drift") is not None
            },
            "next_round_suggestions": [
                "上传真实联邦/VFL 实验 CSV 替换 simulated pilot",
                "每条 replan action 含 expected_check，可在下一轮 Pipeline 验收",
            ],
            "result_source": "simulated pilot result (explicitly marked simulated)",
            "fl_setting": fl_setting,
        }
