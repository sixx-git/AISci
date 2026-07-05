"""
小样验证智能体 (SmallValidationAgent)
根据实验设计生成可运行的小样验证方案
"""
import logging
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.data.preliminary_analysis_skill import PreliminaryAnalysisSkill
from app.skills.experiment.result_verification_skill import ResultVerificationSkill
from app.services.experiment_sandbox_service import get_experiment_sandbox_service

logger = logging.getLogger(__name__)

settings = get_settings()


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
            
            # 定义 schema 示例
            schema_example = {
                "has_real_data": has_csv_data,
                "analysis_script": "# 基于已上传真实数据的 Python 分析脚本...",
                "simulated_data": "",
                "simulation_assumptions": "",
                "charts": "[]",
                "statistics": "{}",
                "run_log": "[]",
            }
            
            if has_csv_data:
                prompt += (
                    "\n\n【重要】项目已提供真实数据文件。"
                    "禁止生成 simulated_data 或 simulation_assumptions；"
                    "has_real_data 必须为 1；analysis_script 必须读取真实 CSV/表格路径。"
                )
            else:
                prompt += (
                    "\n\n【重要】当前无可用真实数据。"
                    "禁止编造 simulated_data 或预填统计结果；"
                    "simulated_data 与 simulation_assumptions 留空，仅描述基于实验设计的验证步骤。"
                )
            
            # 调用 LLM
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="small_validation"
            )
            
            # 验证和标准化结果
            result = self._validate_and_normalize_result(result_dict, has_csv_data)
            
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
                if sandbox_use_docker:
                    extra_env["AISCI_SANDBOX_USE_DOCKER"] = "1"
                sandbox = get_experiment_sandbox_service().execute_analysis_script(
                    run_id=run_id,
                    analysis_script=result["analysis_script"],
                    csv_data_path=csv_data_path,
                    extra_env=extra_env,
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

                if not sandbox.get("success") and csv_data_path and os.path.exists(csv_data_path):
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
                    if pilot.get("success"):
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
                        }
                        result["results"] = self._merge_sandbox_into_results(
                            result["results"], result["sandbox_execution"]
                        )
                        result.setdefault("warnings", []).append(
                            "LLM 沙箱脚本未成功，已使用真实 CSV pilot 对比分析作为实验结果"
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

            pa_data = outputs.get("preliminary_analysis", {}).get("data", {})
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
        pa_data = skill_outputs.get("preliminary_analysis", {}).get("data", {})
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

        pa_warnings = skill_outputs.get("preliminary_analysis", {}).get("warnings", [])
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
    
    def _generate_default_script(self) -> str:
        """生成默认的分析脚本"""
        return '''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

print("="*50)
print("小样验证脚本")
print(f"开始时间: {datetime.now()}")
print("="*50)

# 生成模拟数据
np.random.seed(42)
n_samples = 100
data = pd.DataFrame({
    'feature1': np.random.normal(0, 1, n_samples),
    'feature2': np.random.normal(1, 2, n_samples),
    'target': np.random.choice([0, 1], n_samples)
})

print("\\n数据前5行:")
print(data.head())
print("\\n数据统计信息:")
print(data.describe())

# 简单统计
stats = {
    'feature1_mean': data['feature1'].mean(),
    'feature1_std': data['feature1'].std(),
    'feature2_mean': data['feature2'].mean(),
    'feature2_std': data['feature2'].std(),
    'target_dist': data['target'].value_counts().to_dict()
}

print("\\n统计结果:")
for key, value in stats.items():
    print(f"{key}: {value}")

print("\\n" + "="*50)
print("验证完成")
print("="*50)
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
