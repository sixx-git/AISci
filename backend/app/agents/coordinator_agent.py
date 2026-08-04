"""
CoordinatorAgent - 大家长 Agent

协调者角色：维护项目上下文、预定义常见错误模式、触发补救动作。
不创建独立 LLM 进程，在 PipelineService 内部运行。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 预定义错误规则库 ──
STAGE_ERROR_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
    "problem_understanding": [
        {
            "id": "pu_empty",
            "severity": "high",
            "condition": lambda d: not d.get("research_question") or len(d.get("keywords", [])) < 2,
            "remediation": "hint_rerun",
            "message": "问题理解不充分，建议补充研究问题描述后重跑",
        },
    ],
    "literature_mining": [
        {
            "id": "lm_no_facts",
            "severity": "critical",
            "condition": lambda d: d.get("facts_count", 0) == 0,
            "remediation": "hint_import_literature",
            "message": "未检索到任何文献事实，请先导入文献库或启用 arXiv 检索",
        },
        {
            "id": "lm_few_facts",
            "severity": "medium",
            "condition": lambda d: 0 < d.get("facts_count", 0) < 3,
            "remediation": "hint_gap_search",
            "message": "文献事实不足，建议补充文献后继续",
        },
    ],
    "knowledge_gap": [
        {
            "id": "kg_no_gaps",
            "severity": "low",
            "condition": lambda d: d.get("gaps_count", 0) == 0 and d.get("facts_count", 0) > 0,
            "remediation": "auto_skip",
            "message": "未检测到明显知识缺口，可进入假设生成阶段",
        },
    ],
    "hypothesis_generation": [
        {
            "id": "hg_all_off_topic",
            "severity": "critical",
            "condition": lambda d: d.get("total", 0) > 0 and d.get("off_topic_count", 0) == d.get("total", 0),
            "remediation": "hint_rerun_with_context",
            "message": "所有假设均偏题，建议检查研究问题或补充相关文献",
        },
        {
            "id": "hg_all_low_evidence",
            "severity": "medium",
            "condition": lambda d: d.get("total", 0) > 0 and d.get("low_evidence_count", 0) == d.get("total", 0),
            "remediation": "auto_evidence_iteration",
            "message": "所有假设证据级别为 low，将自动触发证据链迭代",
        },
    ],
    "hypothesis_review": [
        {
            "id": "hr_no_primary",
            "severity": "critical",
            "condition": lambda d: not d.get("has_primary") and d.get("total", 0) > 0,
            "remediation": "hint_revise_hypothesis",
            "message": "无合格主假设，请修订假设或补充文献证据",
        },
    ],
    "report_generation": [
        {
            "id": "rg_low_quality",
            "severity": "critical",
            "condition": lambda d: d.get("quality_score", 100) < 60,
            "remediation": "hint_revise_report",
            "message_template": "报告质量评分过低 ({quality_score})，请检查缺失字段和关键问题",
        },
        {
            "id": "rg_no_refs_verified",
            "severity": "high",
            "condition": lambda d: d.get("has_references") and d.get("refs_verified", 0) == 0,
            "remediation": "hint_verify_references",
            "message": "报告引用未经核验，请检查文献库引用",
        },
        {
            "id": "rg_many_missing_sections",
            "severity": "medium",
            "condition": lambda d: len(d.get("missing_sections", [])) >= 3,
            "remediation": "hint_revise_report",
            "message_template": "报告缺失多个必要章节: {missing_sections}",
        },
    ],
}

# ── 补救动作映射 ──
REMEDIATION_ACTIONS: Dict[str, Dict[str, Any]] = {
    "hint_rerun": {
        "type": "hint",
        "suggestion": "rerun_stage",
        "description": "建议用户重跑当前阶段",
    },
    "hint_import_literature": {
        "type": "hint",
        "suggestion": "import_literature",
        "description": "建议用户导入文献",
    },
    "hint_gap_search": {
        "type": "hint",
        "suggestion": "search_more",
        "description": "建议用户启用数据缺口补搜",
    },
    "hint_rerun_with_context": {
        "type": "hint",
        "suggestion": "rerun_with_context",
        "description": "建议用户补充研究问题或文献后重跑",
    },
    "hint_revise_hypothesis": {
        "type": "hint",
        "suggestion": "revise_hypothesis",
        "description": "建议用户修订假设",
    },
    "hint_revise_report": {
        "type": "hint",
        "suggestion": "revise_report",
        "description": "建议用户修订报告",
    },
    "hint_verify_references": {
        "type": "hint",
        "suggestion": "verify_references",
        "description": "建议用户核验引用",
    },
    "auto_evidence_iteration": {
        "type": "auto",
        "suggestion": "iterate_evidence",
        "description": "自动触发证据链迭代",
    },
    "auto_skip": {
        "type": "auto",
        "suggestion": "continue",
        "description": "自动跳过并继续",
    },
}


class CoordinatorAgent:
    """大家长 Agent：协调者角色

    职责：
    1. 维护项目级结构化上下文快照
    2. 预定义各阶段常见错误模式
    3. 分析错误并触发补救动作（自动或提示）
    4. 报告生成后的专项质量检查
    5. LLM 兜底分析未知错误
    """

    def __init__(self, db=None):
        self.db = db
        self._context: Dict[str, Any] = {
            "research_question": "",
            "stage_results": {},
            "gate_results": [],
            "remediation_actions": [],
            "fact_whitelist": [],
            "hypothesis_versions": [],
        }
        self._hints: List[Dict[str, Any]] = []

    # ── 上下文维护 ──

    def update_context(self, key: str, value: Any) -> None:
        self._context[key] = value

    def update_stage_result(self, stage: str, result: Dict[str, Any]) -> None:
        self._context["stage_results"][stage] = result
        if stage == "literature_mining":
            facts = result.get("facts", [])
            self._context["fact_whitelist"] = [
                f.get("fact_id") for f in facts if isinstance(f, dict) and f.get("fact_id")
            ]
        elif stage == "hypothesis_generation":
            self._context["hypothesis_versions"].append({
                "version": len(self._context["hypothesis_versions"]) + 1,
                "count": len(result.get("hypotheses", [])),
                "off_topic_count": result.get("off_topic_count", 0),
                "low_evidence_count": result.get("low_evidence_count", 0),
                "timestamp": datetime.now().isoformat(),
            })

    @property
    def context(self) -> Dict[str, Any]:
        return self._context

    # ── 错误数据快照构建 ──

    def build_error_snapshot(self, stage: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """从阶段结果构建错误数据快照，供预定义规则匹配"""
        snapshot: Dict[str, Any] = {"stage": stage}

        if stage == "problem_understanding":
            snapshot["research_question"] = result.get("problem_statement", "")
            snapshot["keywords"] = result.get("keywords", [])
        elif stage == "literature_mining":
            facts = result.get("facts", [])
            snapshot["facts_count"] = len(facts)
            snapshot["source_papers"] = result.get("source_papers", [])
        elif stage == "knowledge_gap":
            snapshot["gaps_count"] = len(result.get("knowledge_gaps", []))
            snapshot["facts_count"] = len(self._context["stage_results"].get("literature_mining", {}).get("facts", []))
        elif stage == "hypothesis_generation":
            hypotheses = result.get("hypotheses", [])
            snapshot["total"] = len(hypotheses)
            snapshot["off_topic_count"] = sum(1 for h in hypotheses if isinstance(h, dict) and h.get("off_topic"))
            snapshot["low_evidence_count"] = sum(
                1 for h in hypotheses if isinstance(h, dict) and h.get("evidence_level") == "low"
            )
        elif stage == "hypothesis_review":
            snapshot["total"] = len(result.get("reviews", []))
            snapshot["has_primary"] = result.get("primary_index") is not None
        elif stage == "report_generation":
            snapshot["quality_score"] = result.get("quality_score", 100)
            snapshot["critical_issues"] = result.get("critical_issues", [])
            snapshot["missing_sections"] = result.get("missing_sections", [])
            snapshot["has_references"] = result.get("has_references", False)
            snapshot["refs_verified"] = result.get("refs_verified", 0)

        return snapshot

    # ── 规则匹配 ──

    def _match_pattern(self, stage: str, snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """匹配预定义错误规则"""
        patterns = STAGE_ERROR_PATTERNS.get(stage, [])
        for pattern in patterns:
            try:
                if pattern["condition"](snapshot):
                    # 处理 message_template
                    msg = pattern.get("message", "")
                    if not msg and "message_template" in pattern:
                        tmpl = pattern["message_template"]
                        if isinstance(tmpl, str):
                            try:
                                msg = tmpl.format(**snapshot)
                            except (KeyError, IndexError, ValueError):
                                msg = tmpl
                    # 为 pattern 添加 resolved message
                    result = dict(pattern)
                    result["_resolved_message"] = msg
                    return result
            except Exception as e:
                logger.warning(f"规则匹配异常 [{pattern.get('id')}]: {e}")
        return None

    # ── 决策 ──

    def decide_remediation(self, stage: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """根据阶段和错误快照决定补救动作"""
        pattern = self._match_pattern(stage, snapshot)

        if pattern:
            remediation = pattern["remediation"]
            action = REMEDIATION_ACTIONS.get(remediation, REMEDIATION_ACTIONS.get("hint_rerun", {}))
            decision = {
                "source": "predefined",
                "pattern_id": pattern.get("id"),
                "stage": stage,
                "severity": pattern.get("severity", "medium"),
                "message": pattern.get("_resolved_message", pattern.get("message", "")),
                "remediation": remediation,
                "action": action,
                "snapshot": snapshot,
                "timestamp": datetime.now().isoformat(),
            }
            self._hints.append(decision)
            return decision

        # 未匹配预定义规则 → 不报错（正常通过）
        return {
            "source": "passed",
            "stage": stage,
            "severity": "info",
            "message": "阶段检查通过",
            "remediation": None,
            "action": {"type": "auto", "suggestion": "continue"},
            "snapshot": snapshot,
            "timestamp": datetime.now().isoformat(),
        }

    # ── LLM 兜底分析 ──

    async def analyze_unexpected_error(
        self,
        stage: str,
        error_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """当预定义规则未匹配且存在异常时，调用 LLM 做开放性错误分析"""
        try:
            from app.services.llm_runtime import qwen_structured_chat

            prompt = f"""你是一个科研项目的协调者（大家长 Agent），负责分析各阶段的错误。

当前阶段: {stage}
错误数据: {json.dumps(error_data, ensure_ascii=False)[:2000]}
项目上下文摘要:
- 研究问题: {context.get('research_question', '')[:200]}
- 已有事实数: {len(context.get('fact_whitelist', []))}
- 假设版本数: {len(context.get('hypothesis_versions', []))}

请分析:
1. 错误严重程度 (critical/high/medium/low)
2. 建议的补救动作 (hint_rerun/hint_import_literature/auto_evidence_iteration/hint_revise_hypothesis/hint_revise_report)
3. 友好的提示信息 (中文)
4. 是否可以自动执行补救 (yes/no)

输出 JSON:
{{"severity": "...", "remediation": "...", "message": "...", "auto": false}}"""

            llm_result = await qwen_structured_chat(
                prompt=prompt,
                model="qwen-plus",
                system_prompt="你是科研协调者，只输出 JSON。",
            )
            analysis = json.loads(llm_result)

            remediation = analysis.get("remediation", "hint_rerun")
            action = REMEDIATION_ACTIONS.get(remediation, REMEDIATION_ACTIONS.get("hint_rerun", {}))

            decision = {
                "source": "llm_analysis",
                "stage": stage,
                "severity": analysis.get("severity", "medium"),
                "message": analysis.get("message", ""),
                "remediation": remediation,
                "action": action,
                "snapshot": error_data,
                "timestamp": datetime.now().isoformat(),
            }
            self._hints.append(decision)
            return decision

        except Exception as e:
            logger.warning(f"LLM 兜底分析失败: {e}")
            return {
                "source": "llm_fallback",
                "stage": stage,
                "severity": "low",
                "message": f"阶段检查完成，未检测到预设问题。如需帮助请手动检查。",
                "remediation": None,
                "action": {"type": "auto", "suggestion": "continue"},
                "snapshot": error_data,
                "timestamp": datetime.now().isoformat(),
            }

    # ── 报告后专项检查 ──

    def check_report_post(self, report_result: Dict[str, Any]) -> Dict[str, Any]:
        """报告生成后的专项检查（基于现有质量检查结果）"""
        quality = report_result.get("quality_check", {})
        reviewer = report_result.get("review", {})

        snapshot = {
            "quality_score": quality.get("score", 100),
            "critical_issues": quality.get("critical_issues", []),
            "missing_sections": quality.get("missing_fields", []) + quality.get("missing_sections", []),
            "has_references": bool(report_result.get("references", [])),
            "refs_verified": quality.get("references_verified", 0),
            "review_score": reviewer.get("review_score", 0),
            "publish_ready": reviewer.get("publish_ready", False),
            "weaknesses": reviewer.get("weaknesses", []),
        }

        decision = self.decide_remediation("report_generation", snapshot)
        decision["extra"] = {
            "quality_score": snapshot["quality_score"],
            "publish_ready": snapshot["publish_ready"],
            "review_score": snapshot["review_score"],
        }
        return decision

    # ── Hint 管理 ──

    @property
    def hints(self) -> List[Dict[str, Any]]:
        return self._hints

    def get_pending_hints(self) -> List[Dict[str, Any]]:
        """获取待处理的提示（非 auto 类型）"""
        return [h for h in self._hints if h.get("action", {}).get("type") != "auto"]

    def get_auto_actions(self) -> List[Dict[str, Any]]:
        """获取自动执行的动作"""
        return [h for h in self._hints if h.get("action", {}).get("type") == "auto"]

    def record_remediation_action(self, action: Dict[str, Any]) -> None:
        """记录已执行的补救动作"""
        self._context["remediation_actions"].append({
            "action": action,
            "timestamp": datetime.now().isoformat(),
        })

    # ── 状态序列化 ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self._context,
            "hints": self._hints,
            "timestamp": datetime.now().isoformat(),
        }
