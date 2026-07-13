"""
小样验证智能体 (SmallValidationAgent)
假设 → 数据就绪检查 → 沙箱执行 → metrics/图表
"""
import logging
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.services.analysis_script_utils import sanitize_analysis_script
from app.services.analysis_script_generator import (
    build_spec_validation_script,
    generate_analysis_script,
)
from app.services.experiment_spec_service import (
    assess_sandbox_spec_alignment,
    assess_validation_readiness,
    build_default_spec_from_datasets,
    enrich_spec_from_design,
)
from app.services.validation_data_guidance_service import build_validation_data_guidance
from app.services.experiment_sandbox_service import get_experiment_sandbox_service

logger = logging.getLogger(__name__)


class SmallValidationAgent:
    """根据实验设计在沙箱中执行小样验证。"""

    def __init__(self):
        self.validation_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "..", "storage", "validations"
        )
        os.makedirs(self.validation_dir, exist_ok=True)

    def generate_validation(
        self,
        hypothesis: str,
        methods: Optional[str] = None,
        datasets: Optional[str] = None,
        metrics: Optional[str] = None,
        csv_data_path: Optional[str] = None,
        experiment_design: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
        modeling_results: Optional[List[Dict[str, Any]]] = None,
        project_mode: str = "general",
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        sandbox_use_docker: bool = False,
    ) -> Dict[str, Any]:
        hypothesis = (hypothesis or "").strip()
        logger.info("开始小样验证: %s", hypothesis[:100] or "(无假设文本)")

        has_uploaded_data = self._resolve_csv_path(csv_data_path, multimodal_datasets)
        csv_data_path = has_uploaded_data["csv_data_path"]
        file_exists = has_uploaded_data["file_exists"]

        result: Dict[str, Any] = {
            "hypothesis": hypothesis,
            "has_uploaded_data": 1 if file_exists else 0,
            "has_real_data": 0,
            "simulated_data": "",
            "simulation_assumptions": "",
            "charts": "[]",
            "statistics": "{}",
            "run_log": self._build_run_log(hypothesis, experiment_design, file_exists),
            "warnings": [],
            "skill_outputs": {},
        }

        result["analysis_script"], result["script_source"] = self._resolve_analysis_script(
            hypothesis=hypothesis,
            methods=methods,
            datasets=datasets,
            metrics=metrics,
            has_csv_data=file_exists,
            csv_data_path=csv_data_path,
            experiment_design=experiment_design,
        )
        if result.get("analysis_script") and isinstance(result["analysis_script"], str):
            result["analysis_script"] = sanitize_analysis_script(result["analysis_script"])

        readiness = assess_validation_readiness(
            experiment_design,
            multimodal_datasets,
            hypothesis=hypothesis,
        )
        for w in readiness.get("warnings") or []:
            result.setdefault("warnings", []).append(w)
        result["validation_readiness"] = readiness

        if readiness.get("blocked"):
            self._apply_blocked_result(
                result,
                readiness,
                experiment_design,
                multimodal_datasets,
                hypothesis,
            )
        elif run_id and result.get("analysis_script"):
            self._run_sandbox_validation(
                result,
                readiness=readiness,
                experiment_design=experiment_design,
                multimodal_datasets=multimodal_datasets,
                csv_data_path=csv_data_path,
                file_exists=file_exists,
                hypothesis=hypothesis,
                modeling_results=modeling_results,
                run_id=run_id,
                project_id=project_id,
                sandbox_use_docker=sandbox_use_docker,
            )
        elif file_exists:
            result["validation_status"] = "skipped"
            result.setdefault("warnings", []).append("缺少 run_id 或分析脚本，未执行沙箱")
        else:
            result["validation_status"] = "need_data"

        result["results"] = self._build_categorized_results(
            result, hypothesis, experiment_design, modeling_results
        )

        validation_id = self._save_validation_files(result, run_id=run_id)
        if validation_id:
            result["validation_id"] = validation_id

        logger.info("小样验证完成: status=%s", result.get("validation_status"))
        return result

    @staticmethod
    def _resolve_csv_path(
        csv_data_path: Optional[str],
        multimodal_datasets: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        if csv_data_path and os.path.exists(csv_data_path):
            return {"csv_data_path": csv_data_path, "file_exists": True}
        for ds in multimodal_datasets or []:
            fp = ds.get("file_path")
            if fp and os.path.exists(fp) and ds.get("data_type", "tabular") == "tabular":
                return {"csv_data_path": fp, "file_exists": True}
        return {"csv_data_path": csv_data_path, "file_exists": False}

    def _apply_blocked_result(
        self,
        result: Dict[str, Any],
        readiness: Dict[str, Any],
        experiment_design: Optional[Dict[str, Any]],
        multimodal_datasets: Optional[List[Dict[str, Any]]],
        hypothesis: str,
    ) -> None:
        blockers = readiness.get("blockers") or []
        result["validation_status"] = "blocked"
        result["validation_blocked"] = True
        result["validation_blocked_reason"] = "; ".join(blockers[:3])
        result["has_real_data"] = 0
        result.setdefault("warnings", []).extend(blockers)
        result["validation_data_guidance"] = build_validation_data_guidance(
            experiment_design,
            multimodal_datasets,
            hypothesis=hypothesis,
            blockers=blockers,
            fetch_downloads=True,
        )
        guidance = result["validation_data_guidance"]
        if guidance.get("summary"):
            result.setdefault("warnings", []).insert(
                0,
                f"数据不匹配：{guidance['summary']}",
            )

    def _run_sandbox_validation(
        self,
        result: Dict[str, Any],
        *,
        readiness: Dict[str, Any],
        experiment_design: Optional[Dict[str, Any]],
        multimodal_datasets: Optional[List[Dict[str, Any]]],
        csv_data_path: Optional[str],
        file_exists: bool,
        hypothesis: str,
        modeling_results: Optional[List[Dict[str, Any]]],
        run_id: str,
        project_id: Optional[str],
        sandbox_use_docker: bool,
    ) -> None:
        ed = dict(experiment_design) if experiment_design else {}
        resolved_spec = readiness.get("experiment_spec") or {}
        if resolved_spec:
            ed_spec = ed.get("experiment_spec")
            if not isinstance(ed_spec, dict) or not ed_spec.get("target_column"):
                ed["experiment_spec"] = enrich_spec_from_design(resolved_spec, ed)

        extra_env = {"AISCI_PROJECT_ID": project_id or ""}
        extra_env.update(self._sandbox_env_for_data(csv_data_path, multimodal_datasets))
        if sandbox_use_docker:
            extra_env["AISCI_SANDBOX_USE_DOCKER"] = "1"

        sandbox_svc = get_experiment_sandbox_service()
        sandbox = sandbox_svc.execute_analysis_script(
            run_id=run_id,
            analysis_script=result["analysis_script"],
            csv_data_path=csv_data_path,
            extra_env=extra_env,
        )

        spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}
        if not spec and multimodal_datasets:
            spec = build_default_spec_from_datasets(multimodal_datasets, hypothesis=hypothesis)

        if (
            (not sandbox.get("success") or not sandbox.get("output_complete"))
            and csv_data_path
            and os.path.exists(csv_data_path)
            and spec
        ):
            spec_script = build_spec_validation_script(spec)
            current_script = (result.get("analysis_script") or "").strip()
            if spec_script.strip() and spec_script.strip() != current_script:
                logger.warning("分析脚本未产出有效结果，改用 spec 对齐脚本重试")
                sandbox_retry = sandbox_svc.execute_analysis_script(
                    run_id=run_id,
                    analysis_script=spec_script,
                    csv_data_path=csv_data_path,
                    extra_env=extra_env,
                )
                if sandbox_retry.get("success") and sandbox_retry.get("output_complete"):
                    sandbox = sandbox_retry
                    result["analysis_script"] = spec_script
                    result["script_source"] = "spec_validation_script"
                    result.setdefault("warnings", []).append(
                        "原脚本未通过，已改用 experiment_spec 对齐的确定性验证脚本"
                    )

        alignment = assess_sandbox_spec_alignment(sandbox.get("metrics"), spec, sandbox=sandbox)
        result["spec_alignment"] = alignment
        if sandbox.get("success") and not alignment.get("aligned"):
            sandbox = dict(sandbox)
            sandbox["success"] = False
            sandbox["spec_misaligned"] = True
            result.setdefault("warnings", []).append(
                alignment.get("reason") or "沙箱产出未对齐 experiment_spec"
            )

        result["sandbox_execution"] = sandbox
        result["artifacts"] = {
            "experiment_id": sandbox.get("experiment_id"),
            "artifact_dir": sandbox.get("artifact_dir"),
            "manifest_path": sandbox.get("manifest_path"),
            "plots": sandbox.get("plots") or [],
            "metrics": sandbox.get("metrics") or {},
        }
        result["has_real_data"] = 1 if file_exists and sandbox.get("success") else 0
        result["validation_status"] = (
            "completed" if sandbox.get("success") and alignment.get("aligned") else "failed"
        )

        if sandbox.get("success") and alignment.get("aligned"):
            result["skill_outputs"] = {
                "sandbox_verification": {
                    "success": True,
                    "data": {
                        "verified": True,
                        "metrics": sandbox.get("metrics"),
                        "plot_count": len(sandbox.get("plots") or []),
                    },
                    "warnings": [],
                }
            }
        else:
            stderr = (sandbox.get("stderr") or "")[:500]
            result["skill_outputs"] = {
                "sandbox_verification": {
                    "success": False,
                    "data": {"verified": False},
                    "warnings": [stderr] if stderr else ["沙箱执行未通过"],
                }
            }

    def _build_categorized_results(
        self,
        result: Dict[str, Any],
        hypothesis: str,
        experiment_design: Optional[Dict[str, Any]],
        modeling_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        has_real = result.get("has_real_data", 0) == 1
        categorized: Dict[str, Any] = {
            "actual_results": {},
            "simulated_results": {"note": "系统已禁用模拟/预填结果"},
            "expected_results": {},
            "result_type_summary": "none",
        }

        sandbox = result.get("sandbox_execution") or {}
        if has_real and sandbox.get("success"):
            categorized["actual_results"] = {
                "data_source": "sandbox_execution",
                "sandbox_metrics": sandbox.get("metrics"),
                "sandbox_plots": sandbox.get("plots") or [],
                "sandbox_execution": {
                    "success": sandbox.get("success"),
                    "duration_ms": sandbox.get("duration_ms"),
                    "metrics": sandbox.get("metrics"),
                    "artifact_dir": sandbox.get("artifact_dir"),
                    "experiment_id": sandbox.get("experiment_id"),
                    "provenance": "experiment_sandbox",
                },
            }
            categorized["result_type_summary"] = "has_actual_results"

        if modeling_results:
            primary = modeling_results[0] if isinstance(modeling_results[0], dict) else {}
            categorized["actual_results"]["modeling_result"] = primary
            categorized["actual_results"]["modeling_results"] = modeling_results
            categorized["actual_results"]["data_source"] = "real_data"
            categorized["result_type_summary"] = "has_actual_results"

        ed = experiment_design or {}
        expected = ed.get("expected_results") or ed.get("expected_outcome") or ""
        if hypothesis or expected:
            categorized["expected_results"] = {
                "hypothesis": hypothesis[:300],
                "expected_outcome": expected,
                "metrics": ed.get("metrics", ""),
                "note": "预期结果，需通过实验验证",
            }
            if categorized["result_type_summary"] == "none":
                categorized["result_type_summary"] = "expected_only"

        if result.get("validation_status") == "blocked":
            categorized["actual_results"] = {
                "note": "数据与假设不匹配，未执行沙箱验证",
                "data_source": "blocked",
            }
            categorized["result_type_summary"] = "none"
        elif not has_real and sandbox and sandbox.get("success") is False:
            categorized["actual_results"] = {
                "note": "沙箱执行失败",
                "data_source": "sandbox_failed",
            }
            stderr = (sandbox.get("stderr") or "")[:200]
            if stderr:
                categorized["warnings"] = [f"沙箱执行失败: {stderr}"]
        elif not has_real and not modeling_results:
            categorized["actual_results"] = {"note": "缺少可用于验证的真实数据"}
            categorized["result_type_summary"] = "none"

        return categorized

    @staticmethod
    def _build_run_log(
        hypothesis: str,
        experiment_design: Optional[Dict[str, Any]],
        file_exists: bool,
    ) -> str:
        now = datetime.now().isoformat()
        ed = experiment_design or {}
        entries = [
            {"timestamp": now, "level": "INFO", "message": "小样验证初始化"},
            {"timestamp": now, "level": "INFO", "message": f"假设: {(hypothesis or '未提供')[:120]}"},
            {
                "timestamp": now,
                "level": "INFO",
                "message": "已上传数据" if file_exists else "尚无可用上传数据",
            },
        ]
        steps = ed.get("experimental_steps")
        if steps and isinstance(steps, str):
            entries.append({
                "timestamp": now,
                "level": "INFO",
                "message": f"实验步骤: {steps[:200]}{'…' if len(steps) > 200 else ''}",
            })
        entries.append({"timestamp": now, "level": "INFO", "message": "等待沙箱执行"})
        return json.dumps(entries, ensure_ascii=False)

    @staticmethod
    def _sandbox_env_for_data(
        csv_data_path: Optional[str],
        multimodal_datasets: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, str]:
        from app.core.dataset_scale import (
            parse_dataset_extra_metadata,
            resolve_analysis_tier,
            tier_sample_rows,
            tier_sandbox_timeout_sec,
        )

        tier = "T0"
        sample_parquet = ""
        if csv_data_path and os.path.exists(csv_data_path):
            tier = resolve_analysis_tier(os.path.getsize(csv_data_path))
        for ds in multimodal_datasets or []:
            fp = ds.get("file_path")
            if csv_data_path and fp == csv_data_path:
                meta = parse_dataset_extra_metadata(ds.get("extra_metadata"))
                if isinstance(ds.get("analysis_tier"), str):
                    tier = ds["analysis_tier"]
                elif meta.get("analysis_tier"):
                    tier = str(meta["analysis_tier"])
                sample_parquet = str(
                    ds.get("sample_parquet_path") or meta.get("sample_parquet_path") or ""
                )
                break

        env = {
            "AISCI_DATA_TIER": tier,
            "AISCI_SAMPLE_ROWS": str(tier_sample_rows(tier) or 0),
            "AISCI_SANDBOX_TIMEOUT_SEC": str(tier_sandbox_timeout_sec(tier)),
        }
        if sample_parquet and os.path.isfile(sample_parquet):
            env["AISCI_SAMPLE_PARQUET"] = sample_parquet
        return env

    def _resolve_analysis_script(
        self,
        *,
        hypothesis: str,
        methods: Optional[str],
        datasets: Optional[str],
        metrics: Optional[str],
        has_csv_data: bool,
        csv_data_path: Optional[str],
        experiment_design: Optional[Dict[str, Any]],
    ) -> tuple[str, str]:
        ed = experiment_design or {}
        design_script = ed.get("analysis_script")
        if isinstance(design_script, dict):
            if design_script.get("_truncated"):
                design_script = None
            else:
                design_script = str(design_script.get("preview") or "")
        if isinstance(design_script, str) and design_script.strip():
            return sanitize_analysis_script(design_script), "experiment_design"

        spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}
        fallback = generate_analysis_script(
            hypothesis=hypothesis,
            methods=methods or ed.get("methods"),
            datasets=datasets or ed.get("datasets"),
            metrics=metrics or ed.get("metrics"),
            baselines=ed.get("baselines"),
            experimental_steps=ed.get("experimental_steps"),
            experiment_spec=spec,
            has_csv_data=has_csv_data,
            csv_data_path=csv_data_path,
        )
        source = "small_validation_from_spec" if spec else "small_validation_fallback"
        return fallback, source

    def _save_validation_files(
        self, result: Dict[str, Any], run_id: Optional[str] = None
    ) -> Optional[str]:
        try:
            import uuid

            validation_id = str(uuid.uuid4())
            validation_path = os.path.join(self.validation_dir, validation_id)
            os.makedirs(validation_path, exist_ok=True)

            script_path = os.path.join(validation_path, "analysis.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(result.get("analysis_script", ""))

            result_path = os.path.join(validation_path, "result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            if run_id and result.get("artifacts", {}).get("artifact_dir"):
                link_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "..",
                    "storage",
                    "runs",
                    run_id,
                    "latest_validation.json",
                )
                os.makedirs(os.path.dirname(link_path), exist_ok=True)
                with open(link_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "validation_id": validation_id,
                            "path": validation_path,
                            "artifacts": result.get("artifacts"),
                        },
                        f,
                    )

            logger.info("验证文件已保存: %s", validation_path)
            return validation_id
        except Exception as e:
            logger.error("保存验证文件失败: %s", e, exc_info=True)
            return None


_agent_instance: Optional[SmallValidationAgent] = None


def get_small_validation_agent() -> SmallValidationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SmallValidationAgent()
    return _agent_instance
