"""联邦小样验证模拟执行 Skill"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._utils import safe_float


class FederatedSimulationExecutorSkill(BaseSkill):
    name = "FederatedSimulationExecutor"
    description = "基于 CSV 聚合分析或生成 simulated pilot，数据不足时 skipped"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        datasets = input_data.get("datasets", []) or []
        fl_context = input_data.get("fl_context", {}) or {}
        plan = input_data.get("experiment_plan", {}) or {}

        tabular = [d for d in datasets if d.get("data_type") == "tabular" and d.get("file_path")]
        required_cols = {"method", "global_accuracy", "f1_score"}
        has_fl_cols = bool(fl_context.get("detected_fields"))

        if tabular:
            csv_result = self._analyze_csv(tabular[0], fl_context, plan)
            if csv_result:
                result.data = csv_result
                return result

        if has_fl_cols and tabular:
            result.add_warning("CSV 缺少 method/global_accuracy 等列，无法做 uploaded_csv 聚合，改用 simulation")
        elif not tabular and not has_fl_cols:
            result.data = {
                "execution_mode": "skipped",
                "missing_requirements": [
                    "缺少联邦实验 CSV（需含 method、non_iid_degree、global_accuracy、f1_score 等列）",
                ],
                "best_method": "",
                "metric_comparison": [],
                "non_iid_sensitivity": {},
                "communication_efficiency": {},
                "client_drift_analysis": {},
                "next_round_suggestions": ["请上传包含联邦 baseline 对比结果的 CSV 后重跑小样验证"],
                "result_source": "skipped due to missing data",
            }
            return result

        sim = self._build_simulation(plan, fl_context)
        result.data = sim
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
        method_col = cols_lower.get("method")
        acc_col = cols_lower.get("global_accuracy") or cols_lower.get("accuracy")
        f1_col = cols_lower.get("f1_score")
        if not method_col or not acc_col:
            return None

        grouped = df.groupby(method_col, dropna=True)
        metric_comparison: List[Dict[str, Any]] = []
        for method, g in grouped:
            entry = {
                "method": str(method),
                "global_accuracy": safe_float(g[acc_col].mean()),
                "sample_count": int(len(g)),
            }
            if f1_col:
                entry["f1_score"] = safe_float(g[f1_col].mean())
            comm_col = cols_lower.get("communication_cost_mb")
            if comm_col:
                entry["communication_cost_mb"] = safe_float(g[comm_col].mean())
            drift_col = cols_lower.get("client_drift")
            if drift_col:
                entry["client_drift"] = safe_float(g[drift_col].mean())
            metric_comparison.append(entry)

        if not metric_comparison:
            return None

        metric_comparison.sort(key=lambda x: (x.get("global_accuracy") or 0), reverse=True)
        best = metric_comparison[0]

        non_iid_col = cols_lower.get("non_iid_degree")
        non_iid_sensitivity: Dict[str, Any] = {}
        if non_iid_col and method_col:
            for method, g in grouped:
                non_iid_sensitivity[str(method)] = {
                    "mean_non_iid_degree": safe_float(g[non_iid_col].mean()),
                    "global_accuracy": safe_float(g[acc_col].mean()),
                }

        comm_eff: Dict[str, Any] = {}
        comm_col = cols_lower.get("communication_cost_mb")
        rounds_col = cols_lower.get("communication_rounds")
        if comm_col and acc_col:
            for row in metric_comparison:
                comm_eff[row["method"]] = {
                    "communication_cost_mb": row.get("communication_cost_mb"),
                    "global_accuracy": row.get("global_accuracy"),
                    "communication_rounds": None,
                }
                if rounds_col:
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
                f"优先复现最佳方法 {best.get('method')} 并扩大客户端数量",
                "补充 counter baseline（LocalOnly / FedProx）对比",
            ],
            "result_source": f"uploaded_csv analysis: {dataset.get('filename', 'dataset')}",
            "fl_setting": fl_context.get("fl_setting", plan.get("fl_setting", "unknown")),
        }

    def _build_simulation(self, plan: Dict[str, Any], fl_context: Dict[str, Any]) -> Dict[str, Any]:
        baselines = (plan.get("baselines") or ["FedAvg", "FedProx", "SCAFFOLD"])[:4]
        metric_comparison = []
        for i, method in enumerate(baselines):
            acc = round(0.62 + i * 0.04, 4)
            metric_comparison.append(
                {
                    "method": method,
                    "global_accuracy": acc,
                    "f1_score": round(acc - 0.02, 4),
                    "communication_cost_mb": round(80 + i * 15, 2),
                    "client_drift": round(0.15 - i * 0.02, 4),
                    "simulated": True,
                }
            )
        metric_comparison.sort(key=lambda x: x["global_accuracy"], reverse=True)
        return {
            "execution_mode": "simulation",
            "best_method": metric_comparison[0]["method"],
            "metric_comparison": metric_comparison,
            "non_iid_sensitivity": {"note": "simulated Non-IID sweep (marked simulated)"},
            "communication_efficiency": {
                m["method"]: {
                    "communication_cost_mb": m["communication_cost_mb"],
                    "global_accuracy": m["global_accuracy"],
                }
                for m in metric_comparison
            },
            "client_drift_analysis": {
                m["method"]: {"client_drift": m["client_drift"]} for m in metric_comparison
            },
            "next_round_suggestions": [
                "上传真实联邦实验 CSV 替换 simulated pilot",
                "增加 FedMD/FedDF 异构 baseline 对比",
            ],
            "result_source": "simulated pilot result (explicitly marked simulated)",
            "fl_setting": fl_context.get("fl_setting", plan.get("fl_setting", "unknown")),
        }
