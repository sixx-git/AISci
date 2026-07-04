"""实验工作流 Skill — 任务分解、协议、仿真、分析、重规划、实验笔记"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult
from app.skills.data.preliminary_analysis_skill import PreliminaryAnalysisSkill
from app.skills.modeling.model_evaluation_skill import ModelEvaluationSkill
from app.skills.modeling.self_correction_skill import SelfCorrectionSkill

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class TaskDecompositionSkill(BaseSkill):
    name = "TaskDecomposition"
    description = "把科研目标拆成任务树"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        goal = input_data.get("research_question") or input_data.get("goal", "")
        try:
            llm = qwen_structured_chat(
                prompt=f"请将以下科研目标分解为可执行任务树（含依赖关系）:\n{goal}",
                schema_example={
                    "task_tree": [
                        {"id": "t1", "title": "文献调研", "depends_on": [], "priority": "high"},
                        {"id": "t2", "title": "数据采集", "depends_on": ["t1"], "priority": "high"},
                    ],
                    "critical_path": ["t1", "t2"],
                },
                prompt_version="task_decomposition",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class ExperimentProtocolSkill(BaseSkill):
    name = "ExperimentProtocol"
    description = "生成实验流程、变量、对照组"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        design = input_data.get("experiment_design") or {}
        hypothesis = input_data.get("hypothesis", "")
        try:
            llm = qwen_structured_chat(
                prompt=(
                    f"假设: {hypothesis}\n实验设计摘要: {json.dumps(design, ensure_ascii=False)[:1500]}\n"
                    "生成标准实验协议：自变量、因变量、对照组、控制变量、步骤。"
                ),
                schema_example={
                    "variables": {"independent": [], "dependent": [], "controls": []},
                    "control_groups": [{"name": "baseline", "description": "..."}],
                    "protocol_steps": ["步骤1", "步骤2"],
                    "randomization": "分层随机",
                },
                prompt_version="experiment_protocol",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class SimulationExecutorSkill(BaseSkill):
    name = "SimulationExecutor"
    description = "调用 Python sandbox 执行小实验（基于 PreliminaryAnalysis）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = PreliminaryAnalysisSkill()
        return await inner.run(input_data, context)


class ResultAnalyzerSkill(BaseSkill):
    name = "ResultAnalyzer"
    description = "读取结果、统计显著性、生成图表"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        evaluation_input = input_data.get("evaluation") or {}
        if evaluation_input.get("models"):
            inner = ModelEvaluationSkill()
            return await inner.run(
                {
                    "task_type": input_data.get("task_type", "classification"),
                    "models": evaluation_input.get("models", []),
                    "dataset_id": input_data.get("dataset_id", ""),
                },
                context,
            )
        pa = input_data.get("preliminary_analysis") or {}
        result.data = {
            "summary_statistics": pa.get("summary_statistics", {}),
            "plots": pa.get("plots", []),
            "significance_note": "需至少两组对照与样本量>=30 方可做 t-test",
            "preliminary_result": pa.get("preliminary_result", {}),
        }
        if not pa:
            result.add_warning("缺少可分析结果")
        return result


class ReplanningSkill(BaseSkill):
    name = "Replanning"
    description = "根据失败或低分结果重新规划"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = SelfCorrectionSkill()
        res = await inner.run(input_data, context)
        suggestions = (res.data or {}).get("self_correction_suggestions", [])
        res.data = {
            **(res.data or {}),
            "replan_actions": [s.get("next_action") for s in suggestions if s.get("next_action")],
            "replan_summary": "; ".join(s.get("suggestion", "") for s in suggestions[:3]),
        }
        return res


class LabNotebookSkill(BaseSkill):
    name = "LabNotebook"
    description = "记录每轮实验计划、参数、结果和结论"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        project_id = input_data.get("project_id", "")
        entry = {
            "timestamp": datetime.now(CHINA_TZ).isoformat(),
            "round": input_data.get("round", 1),
            "plan": input_data.get("experiment_protocol") or input_data.get("plan"),
            "parameters": input_data.get("parameters", {}),
            "results": input_data.get("results", {}),
            "conclusion": input_data.get("conclusion", ""),
        }
        if project_id:
            base = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "storage", "lab_notebooks", project_id,
            )
            os.makedirs(base, exist_ok=True)
            path = os.path.join(base, "notebook.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            entry["notebook_path"] = path
        result.data = {"entry": entry}
        return result
