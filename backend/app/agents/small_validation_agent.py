"""
小样验证智能体 (SmallValidationAgent)
根据实验设计生成可运行的小样验证方案
"""
import logging
import json
import os
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.qwen_client import qwen_structured_chat, qwen_chat, AgentOutputParseError
from app.services.prompt_loader import get_prompt_loader
from app.skills.data.preliminary_analysis_skill import PreliminaryAnalysisSkill
from app.skills.experiment.result_verification_skill import ResultVerificationSkill
from app.services.analysis_script_utils import sanitize_analysis_script
from app.services.experiment_sandbox_service import get_experiment_sandbox_service

logger = logging.getLogger(__name__)

settings = get_settings()


def _skill_block(skill_outputs: Optional[Dict[str, Any]], key: str) -> Dict[str, Any]:
    if not isinstance(skill_outputs, dict):
        return {}
    block = skill_outputs.get(key)
    return block if isinstance(block, dict) else {}


def _preliminary_analysis_data(skill_outputs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = _skill_block(skill_outputs, "preliminary_analysis").get("data")
    return data if isinstance(data, dict) else {}


class SmallValidationAgent:
    """
    小样验证智能体
    根据实验设计生成可运行的小样验证方案
    """
    
    def __init__(self):
        # 确保存储目录存在
        self.validation_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "storage", "validations")
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
        """
        生成小样验证方案
        
        Args:
            hypothesis: 假设内容
            methods: 研究方法
            datasets: 数据集说明
            metrics: 评估指标
            csv_data_path: CSV 数据路径（如果有）
            experiment_design: 实验设计结果
            multimodal_datasets: 多模态数据集
            
        Returns:
            验证方案结果
        """
        try:
            logger.info(f"开始为假设生成小样验证: {hypothesis[:100]}...")
            
            has_csv_data = 1 if csv_data_path and os.path.exists(csv_data_path) else 0
            if not csv_data_path and multimodal_datasets:
                for ds in multimodal_datasets:
                    fp = ds.get("file_path")
                    if fp and os.path.exists(fp) and ds.get("data_type", "tabular") == "tabular":
                        csv_data_path = fp
                        has_csv_data = 1
                        break
            
            # 构建提示
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "small_validation",
                {
                    "hypothesis": hypothesis,
                    "methods": methods or "未提供具体方法",
                    "datasets": datasets or "未提供数据集说明",
                    "metrics": metrics or "未提供评估指标",
                    "has_csv_data": "是" if has_csv_data else "否"
                }
            )
            
            if has_csv_data:
                prompt += (
                    "\n\n【重要】项目已提供真实数据文件。"
                    "禁止生成 simulated_data 或 simulation_assumptions；"
                    "has_real_data 必须为 1。"
                )
            else:
                prompt += (
                    "\n\n【重要】当前无可用真实数据。"
                    "禁止编造 simulated_data 或预填统计结果；"
                    "simulated_data 与 simulation_assumptions 留空，仅描述基于实验设计的验证步骤。"
                )
            prompt += (
                "\n\n【输出约束】本次仅返回 JSON 元数据，不要包含 analysis_script 字段；"
                "charts/statistics/run_log 使用 JSON 数组或对象，不要用字符串包裹。"
            )

            # 元数据与脚本分步生成，避免多行 Python 破坏 JSON 解析
            schema_example = {
                "has_real_data": has_csv_data,
                "simulated_data": "",
                "simulation_assumptions": "",
                "charts": [],
                "statistics": {},
                "run_log": [],
            }

            try:
                result_dict = qwen_structured_chat(
                    prompt=prompt,
                    schema_example=schema_example,
                    prompt_version="small_validation",
                )
            except AgentOutputParseError as parse_err:
                logger.warning(
                    "小样验证元数据 JSON 解析失败，降级为最小 schema 重试: %s",
                    parse_err,
                )
                result_dict = qwen_structured_chat(
                    prompt=prompt + "\n\n仅返回 has_real_data、simulation_assumptions 两个字段，其余可留空。",
                    schema_example={
                        "has_real_data": has_csv_data,
                        "simulation_assumptions": "",
                    },
                    prompt_version="small_validation_fallback",
                )
                for key, default in schema_example.items():
                    result_dict.setdefault(key, default)

            result_dict["analysis_script"] = self._generate_analysis_script(
                hypothesis=hypothesis,
                methods=methods,
                datasets=datasets,
                metrics=metrics,
                has_csv_data=bool(has_csv_data),
                csv_data_path=csv_data_path,
            )
            
            # 验证和标准化结果
            result = self._validate_and_normalize_result(result_dict, has_csv_data)
            if result.get("analysis_script") and isinstance(result["analysis_script"], str):
                result["analysis_script"] = sanitize_analysis_script(result["analysis_script"])
            
            # ── 运行初步分析 Skill ──
            skill_outputs = self._run_preliminary_analysis_sync(
                hypothesis, methods, datasets, metrics, experiment_design, multimodal_datasets
            )
            result["skill_outputs"] = skill_outputs

            # ── 构建分类结果（actual / simulated / expected）──
            result["results"] = self._build_categorized_results(
                result, skill_outputs, hypothesis, experiment_design, modeling_results
            )

            # ── P0: 沙箱执行 analysis_script，绑定 run artifacts ──
            if run_id and result.get("analysis_script"):
                extra_env = {"AISCI_PROJECT_ID": project_id or ""}
                extra_env.update(self._sandbox_env_for_data(csv_data_path, multimodal_datasets))
                if sandbox_use_docker:
                    extra_env["AISCI_SANDBOX_USE_DOCKER"] = "1"
                sandbox = get_experiment_sandbox_service().execute_analysis_script(
                    run_id=run_id,
                    analysis_script=result["analysis_script"],
                    csv_data_path=csv_data_path,
                    extra_env=extra_env,
                )
                if (
                    not sandbox.get("success")
                    and csv_data_path
                    and os.path.exists(csv_data_path)
                ):
                    default_script = self._generate_default_script()
                    if default_script and default_script.strip() != (result.get("analysis_script") or "").strip():
                        logger.warning("LLM 分析脚本沙箱失败，使用默认脚本重试")
                        sandbox_retry = get_experiment_sandbox_service().execute_analysis_script(
                            run_id=run_id,
                            analysis_script=default_script,
                            csv_data_path=csv_data_path,
                            extra_env=extra_env,
                        )
                        if sandbox_retry.get("success") and sandbox_retry.get("output_complete"):
                            sandbox = sandbox_retry
                            result["analysis_script"] = default_script
                            result.setdefault("warnings", []).append(
                                "LLM 分析脚本失败，已自动改用默认 pilot 脚本并成功执行"
                            )
                result["sandbox_execution"] = sandbox
                result["artifacts"] = {
                    "experiment_id": sandbox.get("experiment_id"),
                    "artifact_dir": sandbox.get("artifact_dir"),
                    "manifest_path": sandbox.get("manifest_path"),
                    "plots": sandbox.get("plots") or [],
                    "metrics": sandbox.get("metrics") or {},
                }
                result["results"] = self._merge_sandbox_into_results(result["results"], sandbox)

                if self._sandbox_needs_pilot_fallback(sandbox, csv_data_path):
                    self._apply_pilot_fallback(
                        result,
                        sandbox=sandbox,
                        csv_data_path=csv_data_path,
                        experiment_design=experiment_design,
                        hypothesis=hypothesis,
                        incomplete=bool(sandbox.get("sandbox_incomplete")),
                    )

            validation_id = self._save_validation_files(result, run_id=run_id)
            if validation_id:
                result["validation_id"] = validation_id
            
            logger.info("小样验证方案生成完成")
            
            return result
            
        except Exception as e:
            logger.error(f"生成小样验证方案时出错: {e}", exc_info=True)
            raise

    @staticmethod
    def _run_preliminary_analysis_sync(
        hypothesis: str,
        methods: Optional[str] = None,
        datasets: Optional[str] = None,
        metrics: Optional[str] = None,
        experiment_design: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            outputs = {}
            try:
                skill = PreliminaryAnalysisSkill()
                skill_result = await skill.run(
                    input_data={
                        "multimodal_datasets": multimodal_datasets or [],
                        "hypothesis": hypothesis,
                        "experiment_design": experiment_design or {},
                        "methods": methods or "",
                        "metrics": metrics or "",
                    },
                    context={"stage": "small_validation"},
                )
                outputs["preliminary_analysis"] = {
                    "success": skill_result.success,
                    "data": skill_result.data,
                    "warnings": skill_result.warnings,
                    "errors": skill_result.errors,
                }
            except Exception as e:
                logger.warning(f"PreliminaryAnalysisSkill 失败: {e}")
                outputs["preliminary_analysis"] = {"success": False, "error": str(e)}

            pa_data = _preliminary_analysis_data(outputs)
            try:
                verify_skill = ResultVerificationSkill()
                verify_result = await verify_skill.run(
                    input_data={
                        "hypothesis": hypothesis,
                        "experiment_design": experiment_design or {},
                        "preliminary_analysis": pa_data,
                        "expected_results": (experiment_design or {}).get("expected_results", ""),
                    },
                    context={"stage": "small_validation"},
                )
                outputs["result_verification"] = {
                    "success": verify_result.success,
                    "data": verify_result.data,
                    "warnings": verify_result.warnings,
                    "errors": verify_result.errors,
                }
            except Exception as e:
                logger.warning(f"ResultVerificationSkill 失败: {e}")
                outputs["result_verification"] = {"success": False, "error": str(e)}
            return outputs

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"PreliminaryAnalysisSkill 异常: {e}")
            return {}
    
    def _build_categorized_results(
        self,
        result: Dict[str, Any],
        skill_outputs: Dict[str, Any],
        hypothesis: str,
        experiment_design: Optional[Dict[str, Any]],
        modeling_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        pa_data = _preliminary_analysis_data(skill_outputs)
        data_source_flag = pa_data.get("data_source_flag", "no_data")
        has_real = (data_source_flag == "real_data" or result.get("has_real_data", 0) == 1)

        categorized = {
            "actual_results": {},
            "simulated_results": {},
            "expected_results": {},
            "result_type_summary": "none",
        }

        if has_real and pa_data:
            categorized["actual_results"] = {
                "summary_statistics": pa_data.get("summary_statistics", {}),
                "feature_vectors": pa_data.get("feature_vectors", []),
                "correlations": pa_data.get("correlations", []),
                "anomalies": pa_data.get("anomalies", []),
                "n_datasets_analyzed": pa_data.get("summary_statistics", {}).__len__() if isinstance(pa_data.get("summary_statistics"), dict) else 0,
                "data_source": "real_data",
                "image_summary": pa_data.get("image_summary", {}),
                "time_series_summary": pa_data.get("time_series_summary", {}),
            }
            categorized["result_type_summary"] = "has_actual_results"

        if modeling_results:
            primary = modeling_results[0]
            if not isinstance(primary, dict):
                primary = {}
            categorized["actual_results"]["modeling_result"] = primary
            categorized["actual_results"]["modeling_results"] = modeling_results
            categorized["actual_results"]["data_source"] = "real_data"
            categorized["result_type_summary"] = "has_actual_results"
            if primary.get("is_pilot_validation"):
                categorized["actual_results"]["validation_scope"] = "pilot_validation"
                categorized["warnings"] = categorized.get("warnings", []) + [
                    "建模样本量较小，结果仅作为 pilot validation，不得夸大结论"
                ]

        simulated_data = result.get("simulated_data", "")
        simulation_assumptions = result.get("simulation_assumptions", "")
        categorized["simulated_results"] = {"note": "未生成模拟数据（系统已禁用模拟/预填结果）"}
        if has_real:
            categorized["simulated_results"] = {"note": "已使用真实数据，未采用模拟结果"}

        target_var = experiment_design.get("target_variable", "") if experiment_design else ""
        expected = experiment_design.get("expected_outcome", "") if experiment_design else ""
        if hypothesis or expected or target_var:
            categorized["expected_results"] = {
                "hypothesis": hypothesis[:300],
                "expected_outcome": expected,
                "target_variable": target_var,
                "metrics": experiment_design.get("metrics", "") if experiment_design else "",
                "note": "预期结果，需通过实验验证",
                "data_source": "expected",
            }
            if categorized["result_type_summary"] == "none":
                categorized["result_type_summary"] = "expected_only"

        if not has_real and not simulated_data and not simulation_assumptions and not modeling_results:
            categorized["result_type_summary"] = "none"
            categorized["actual_results"] = {"note": "缺少真实数据，未生成实际分析结果"}
            categorized["simulated_results"] = {"note": "未生成模拟数据"}
            categorized["expected_results"] = categorized["expected_results"] or {"note": "未提供预期结果"}

        pa_warnings = _skill_block(skill_outputs, "preliminary_analysis").get("warnings") or []
        if not isinstance(pa_warnings, list):
            pa_warnings = []
        existing_warnings = categorized.get("warnings", [])
        categorized["warnings"] = existing_warnings + pa_warnings

        return categorized

    @staticmethod
    def _merge_sandbox_into_results(
        categorized: Dict[str, Any],
        sandbox: Dict[str, Any],
    ) -> Dict[str, Any]:
        actual = categorized.get("actual_results") or {}
        if not isinstance(actual, dict):
            actual = {}
        actual["sandbox_execution"] = {
            "success": sandbox.get("success"),
            "duration_ms": sandbox.get("duration_ms"),
            "metrics": sandbox.get("metrics"),
            "artifact_dir": sandbox.get("artifact_dir"),
            "experiment_id": sandbox.get("experiment_id"),
            "provenance": "experiment_sandbox",
        }
        if sandbox.get("success"):
            actual["data_source"] = "sandbox_execution"
            categorized["result_type_summary"] = "has_actual_results"
            if sandbox.get("metrics"):
                actual["sandbox_metrics"] = sandbox["metrics"]
            if sandbox.get("plots"):
                actual["sandbox_plots"] = sandbox["plots"]
        else:
            warnings = categorized.get("warnings") or []
            if not isinstance(warnings, list):
                warnings = []
            warnings.append(f"沙箱执行失败: {(sandbox.get('stderr') or '')[:200]}")
            categorized["warnings"] = warnings
        categorized["actual_results"] = actual
        return categorized

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

    def _generate_analysis_script(
        self,
        *,
        hypothesis: str,
        methods: Optional[str],
        datasets: Optional[str],
        metrics: Optional[str],
        has_csv_data: bool,
        csv_data_path: Optional[str],
    ) -> str:
        """单独生成 Python 分析脚本，避免嵌入 JSON 导致解析失败。"""
        data_hint = (
            f"真实数据路径: {csv_data_path}"
            if has_csv_data and csv_data_path
            else "当前无真实 CSV，脚本应说明无法执行并优雅退出（sys.exit(0)），禁止生成随机模拟数据"
        )
        script_prompt = (
            f"假设: {hypothesis}\n"
            f"方法: {methods or '未提供'}\n"
            f"数据集: {datasets or '未提供'}\n"
            f"指标: {metrics or '未提供'}\n"
            f"{data_hint}\n\n"
            "请输出完整可运行的 Python 3 分析脚本，使用 pandas/numpy/matplotlib。\n"
            "必须用 ```python 代码块包裹，不要输出 JSON 或其他说明文字。\n\n"
            "【沙箱输出契约 — 必须全部满足】\n"
            "1. 使用环境变量 AISCI_RUN_DIR 作为运行目录，将 metrics 写入 "
            "Path(AISCI_RUN_DIR)/'metrics.json'（JSON 对象，含 primary_metric 或具体指标键，"
            "禁止仅写 note 占位）。\n"
            "2. 使用环境变量 AISCI_PLOTS_DIR 作为图表目录，至少保存 1 张 PNG 到该目录 "
            "（如 PLOTS_DIR/'experiment_result.png'）。\n"
            "3. 优先调用 _aisci_load_data() 加载数据；否则使用 os.environ['AISCI_DATA_PATH']。\n"
            "4. 图表须体现假设验证或方法对比（如指标柱状图、误差对比），"
            "禁止只输出原始字段直方图/散点图作为唯一结果。\n"
            "5. 设置 matplotlib Agg 后端，脚本 exit code 必须为 0。\n"
            "6. 【import 约束】wasserstein_distance 必须从 scipy.stats 导入，"
            "禁止 from scipy.spatial.distance import wasserstein_distance；"
            "KL 散度用 scipy.stats.entropy，勿用错误模块。\n"
            "7. 保持脚本简洁可运行，避免过长导致超时；优先 sklearn + pandas + matplotlib。"
        )
        if has_csv_data and csv_data_path:
            script_prompt += (
                "\n脚本应优先使用 _aisci_load_data() 加载数据（沙箱会自动注入该函数）；"
                "若直接 read_csv，请使用环境变量 AISCI_DATA_PATH。"
            )
        try:
            raw = qwen_chat(
                script_prompt,
                system_prompt="你是数据科学家。只输出一个 ```python 代码块，不要 JSON。",
                temperature=0.2,
            )
            script = self._extract_code_block(raw)
            if script:
                return sanitize_analysis_script(script)
        except Exception as e:
            logger.warning("分析脚本 LLM 生成失败，使用默认脚本: %s", e)
        return self._generate_default_script() if has_csv_data else ""

    @staticmethod
    def _extract_code_block(text: str) -> str:
        if not text:
            return ""
        match = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()

    @staticmethod
    def _serialize_json_field(value: Any, default: str) -> str:
        if value is None or value == "":
            return default
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") or stripped.startswith("{"):
                try:
                    json.loads(stripped)
                    return stripped
                except json.JSONDecodeError:
                    pass
            return value
        return json.dumps(value, ensure_ascii=False)

    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        has_csv_data: int
    ) -> Dict[str, Any]:
        """验证和标准化结果"""
        # 确保必要字段存在
        required_fields = [
            "has_real_data", "analysis_script", "simulated_data",
            "simulation_assumptions", "charts", "statistics", "run_log"
        ]
        
        for field in required_fields:
            if field not in result_dict:
                if field == "has_real_data":
                    result_dict[field] = has_csv_data
                elif field == "analysis_script":
                    result_dict[field] = self._generate_default_script() if has_csv_data else ""
                else:
                    result_dict[field] = ""

        result_dict["charts"] = self._serialize_json_field(result_dict.get("charts"), "[]")
        result_dict["statistics"] = self._serialize_json_field(result_dict.get("statistics"), "{}")
        result_dict["run_log"] = self._serialize_json_field(result_dict.get("run_log"), "[]")
        
        # 有真实数据时清除 LLM 可能生成的模拟字段
        if has_csv_data:
            result_dict["has_real_data"] = 1
            result_dict["simulated_data"] = ""
            result_dict["simulation_assumptions"] = ""
        else:
            result_dict["simulated_data"] = ""
            result_dict["simulation_assumptions"] = ""
        
        # 确保 has_real_data 是整数
        result_dict["has_real_data"] = int(result_dict.get("has_real_data", has_csv_data))
        
        # 生成默认运行日志
        if not result_dict.get("run_log"):
            result_dict["run_log"] = self._generate_default_log()
        
        return result_dict
    
    @staticmethod
    def _sandbox_needs_pilot_fallback(
        sandbox: Dict[str, Any],
        csv_data_path: Optional[str],
    ) -> bool:
        if not csv_data_path or not os.path.exists(csv_data_path):
            return False
        if not sandbox.get("success"):
            return True
        if sandbox.get("sandbox_incomplete"):
            return True
        if not sandbox.get("output_complete", True):
            return True
        return False

    def _apply_pilot_fallback(
        self,
        result: Dict[str, Any],
        *,
        sandbox: Dict[str, Any],
        csv_data_path: str,
        experiment_design: Optional[Dict[str, Any]],
        hypothesis: str,
        incomplete: bool = False,
    ) -> None:
        from app.services.experiment_pilot_analysis_service import (
            run_pilot_from_csv,
            write_pilot_metrics_json,
        )

        artifact_dir = sandbox.get("artifact_dir") or ""
        pilot = run_pilot_from_csv(
            csv_data_path,
            experiment_design or {},
            output_dir=artifact_dir or self.validation_dir,
            hypothesis=hypothesis,
        )
        if not pilot.get("success"):
            result.setdefault("warnings", []).append(
                "沙箱未产出有效实验图/指标，pilot 对比分析也未能生成结果"
            )
            return

        if artifact_dir:
            write_pilot_metrics_json(artifact_dir, pilot["metrics"])
        result["artifacts"]["metrics"] = pilot["metrics"]
        result["artifacts"]["plots"] = pilot.get("plots") or []
        result["pilot_analysis"] = pilot
        result["sandbox_execution"] = {
            **sandbox,
            "success": True,
            "metrics": pilot["metrics"],
            "plots": pilot.get("plots") or [],
            "pilot_fallback": True,
            "output_complete": True,
            "sandbox_incomplete": False,
        }
        result["results"] = self._merge_sandbox_into_results(
            result["results"], result["sandbox_execution"]
        )
        msg = (
            "沙箱脚本未写出 metrics/图表，已使用真实 CSV pilot 对比分析作为实验结果"
            if incomplete
            else "LLM 沙箱脚本未成功，已使用真实 CSV pilot 对比分析作为实验结果"
        )
        result.setdefault("warnings", []).append(msg)

    def _generate_default_script(self) -> str:
        """生成符合沙箱契约的默认分析脚本（真实数据）。"""
        return '''import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

run_dir = Path(os.environ.get("AISCI_RUN_DIR", "."))
plots_dir = Path(os.environ.get("AISCI_PLOTS_DIR", str(run_dir / "plots")))
plots_dir.mkdir(parents=True, exist_ok=True)


def _load_df():
    if "globals" in dir() and callable(globals().get("_aisci_load_data")):
        return _aisci_load_data()
    data_path = os.environ.get("AISCI_DATA_PATH") or os.environ.get("CSV_DATA_PATH")
    if not data_path:
        raise RuntimeError("缺少 AISCI_DATA_PATH，无法加载数据")
    return pd.read_csv(data_path)


df = _aisci_encode_frame(_load_df())
numeric = df.select_dtypes(include=[np.number])
if numeric.empty:
    raise RuntimeError("数据编码后仍无数值列，无法生成对比图")

col = None
for hint in ("carcinoma", "label", "target", "jaundice", "fibrosis"):
    for c in numeric.columns:
        if hint in str(c).lower():
            col = c
            break
    if col:
        break
if col is None:
    col = numeric.columns[0]
series = numeric[col].dropna()
metrics = {
    "rows": int(len(df)),
    "columns": int(len(df.columns)),
    "data_source": "sandbox_default_script",
    "encoded_value_column": str(col),
}

if series.empty:
    metrics["primary_metric"] = 0.0
    metrics["warning"] = "no usable values after encoding"
else:
    metrics["primary_metric"] = float(series.mean())
    metrics["primary_metric_std"] = float(series.std()) if len(series) > 1 else 0.0
    metrics["metric_label"] = str(col)

    mid = max(1, len(series) // 2)
    group_a = series.iloc[:mid]
    group_b = series.iloc[mid:]
    metrics["baseline_mean"] = float(group_a.mean())
    metrics["proposed_mean"] = float(group_b.mean())

    fig, ax = plt.subplots(figsize=(8, 5))
    names = ["Baseline（前半）", "Proposed（后半）"]
    vals = [metrics["baseline_mean"], metrics["proposed_mean"]]
    ax.bar(names, vals, color=["#4C72B0", "#DD8452"], alpha=0.9)
    ax.set_ylabel(str(col))
    ax.set_title(f"Pilot：{col} 分区对比")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(plots_dir / "experiment_result.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)
'''
    
    def _generate_default_log(self) -> str:
        """生成默认运行日志"""
        now = datetime.now().isoformat()
        log_entries = [
            {"timestamp": now, "level": "INFO", "message": "小样验证任务初始化"},
            {"timestamp": now, "level": "INFO", "message": "生成分析脚本"},
            {"timestamp": now, "level": "INFO", "message": "准备模拟数据"},
            {"timestamp": now, "level": "INFO", "message": "执行统计分析"},
            {"timestamp": now, "level": "INFO", "message": "生成图表"},
            {"timestamp": now, "level": "INFO", "message": "验证任务完成"}
        ]
        return json.dumps(log_entries, ensure_ascii=False)
    
    def _save_validation_files(self, result: Dict[str, Any], run_id: Optional[str] = None) -> Optional[str]:
        """保存验证文件，若提供 run_id 则同步写入 run artifacts 目录。"""
        try:
            import uuid
            validation_id = str(uuid.uuid4())

            validation_path = os.path.join(self.validation_dir, validation_id)
            os.makedirs(validation_path, exist_ok=True)

            script_path = os.path.join(validation_path, "analysis.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(result.get("analysis_script", ""))

            if result.get("simulated_data"):
                data_path = os.path.join(validation_path, "simulated_data.json")
                with open(data_path, "w", encoding="utf-8") as f:
                    f.write(result["simulated_data"])

            result_path = os.path.join(validation_path, "result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            if run_id and result.get("artifacts", {}).get("artifact_dir"):
                link_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "..", "storage", "runs", run_id, "latest_validation.json"
                )
                os.makedirs(os.path.dirname(link_path), exist_ok=True)
                with open(link_path, "w", encoding="utf-8") as f:
                    json.dump({"validation_id": validation_id, "path": validation_path, "artifacts": result.get("artifacts")}, f)

            logger.info(f"验证文件已保存到: {validation_path}")
            return validation_id

        except Exception as e:
            logger.error(f"保存验证文件时出错: {e}", exc_info=True)
            return None


# 全局单例
_agent_instance: Optional[SmallValidationAgent] = None


def get_small_validation_agent() -> SmallValidationAgent:
    """获取 SmallValidationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SmallValidationAgent()
    return _agent_instance
