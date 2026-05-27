"""
报告生成智能体 (ReportGenerationAgent)
——面向挑战杯 XH-202619 赛题，生成《科学假设与研究计划》Markdown + PDF。
"""
import logging
import json
import os
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.services.pdf_export_service import export_markdown_to_pdf

logger = logging.getLogger(__name__)

# ── 15 章节结构 ──
REPORT_CHAPTERS = [
    "paper_title",           # 0
    "paper_abstract",        # 1
    "problem_statement",     # 2
    "literature_facts",      # 3  ← Evidence-grounded
    "knowledge_gaps",        # 4
    "scientific_hypothesis", # 5
    "rationale",             # 6
    "technical_details",     # 7
    "datasets",              # 8
    "source",                # 9
    "target",                # 10
    "methods",               # 11
    "experiments",           # 12
    "results_feasibility",   # 13
    "human_review",          # 14
    "references",            # 15 (handled separately)
]

CHALLENGE_CUP_FIELDS = [
    ("paper_title", "0. Paper Title"),
    ("paper_abstract", "1. Paper Abstract"),
    ("problem_statement", "2. Problem Statement"),
    ("literature_facts", "3. Evidence-grounded Literature Facts"),
    ("knowledge_gaps", "4. Knowledge Gaps"),
    ("scientific_hypothesis", "5. Generated Scientific Hypothesis"),
    ("rationale", "6. Rationale"),
    ("technical_details", "7. Technical Details"),
    ("datasets", "8. Datasets"),
    ("source", "9. Source"),
    ("target", "10. Target"),
    ("methods", "11. Methods"),
    ("experiments", "12. Experiments"),
    ("results_feasibility", "13. Results / Feasibility Verification"),
    ("human_review", "14. Human-in-the-loop Review"),
    ("references", "15. References"),
]


class ReportGenerationAgent:
    """面向挑战杯赛题的科技报告生成智能体"""

    def __init__(self):
        self.reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "..", "storage", "reports"
        )
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_report(
        self,
        project_info: Dict[str, Any],
        problem_understanding: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        knowledge_gaps: Dict[str, Any],
        all_hypotheses: List[Dict[str, Any]],
        final_hypothesis: Dict[str, Any],
        experiment_design: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]] = None,
        pipeline_run_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
         Args:
            project_info: 项目基本信息
            problem_understanding: 问题理解结果
            literature_facts: 文献事实列表（来自 LiteratureMiningAgent）
            citation_map: 引用映射列表
            knowledge_gaps: 知识缺口结果
            all_hypotheses: 所有生成的假设列表（包含 supporting_fact_ids）
            final_hypothesis: 评审后的最终假设
            experiment_design: 实验设计
            small_validation: 小样验证结果
            pipeline_run_info: Pipeline 运行信息
        """
        try:
            logger.info(f"开始生成研究报告，项目: {project_info.get('title', 'Unknown')}")

            # ── 格式化输入 ──
            formatted_input = self._format_input(
                project_info,
                problem_understanding,
                literature_facts,
                citation_map,
                knowledge_gaps,
                all_hypotheses,
                final_hypothesis,
                experiment_design,
                small_validation,
            )

            # ── 构建 Prompt ──
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "report_generation", formatted_input
            )

            # ── Schema example ──
            schema_example = {
                "title": "科学假设与研究计划",
                "paper_title": "基于文献挖掘的科学假设与验证计划",
                "paper_abstract": "本文围绕... 通过文献挖掘提取 X 条关键事实...",
                "markdown_content": "# 科学假设与研究计划\n\n...",
                "chapters": {
                    "problem_statement": "...",
                    "literature_facts": "...",
                    "knowledge_gaps": "...",
                    "scientific_hypothesis": "...",
                    "rationale": "...",
                    "technical_details": "...",
                    "datasets": "...",
                    "source": "...",
                    "target": "...",
                    "methods": "...",
                    "experiments": "...",
                    "results_feasibility": "...",
                    "human_review": "...",
                    "references": [],
                },
            }

            # ── LLM ──
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="report_generation",
            )

            # ── 后校验 + 合规检查 ──
            result = self._validate_and_normalize_result(
                result_dict, literature_facts, citation_map, all_hypotheses
            )

            # ── 附加运行摘要 ──
            if pipeline_run_info:
                result = self._append_run_summary_to_report(result, pipeline_run_info)

            # ── 保存文件 ──
            file_info = self._save_report_files(result, project_info)
            result.update(file_info)

            logger.info("研究报告生成完成")
            return result

        except Exception as e:
            logger.error(f"生成报告时出错: {e}", exc_info=True)
            raise

    # ──────── 格式化 ────────

    def _format_input(
        self,
        project_info: Dict[str, Any],
        problem_understanding: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        knowledge_gaps: Dict[str, Any],
        all_hypotheses: List[Dict[str, Any]],
        final_hypothesis: Dict[str, Any],
        experiment_design: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        return {
            "project_info": json.dumps(project_info, ensure_ascii=False, indent=2),
            "problem_understanding": json.dumps(problem_understanding, ensure_ascii=False, indent=2),
            "literature_facts": json.dumps(literature_facts, ensure_ascii=False, indent=2),
            "citation_map": json.dumps(citation_map, ensure_ascii=False, indent=2),
            "knowledge_gaps": json.dumps(knowledge_gaps, ensure_ascii=False, indent=2),
            "all_hypotheses": json.dumps(all_hypotheses, ensure_ascii=False, indent=2),
            "final_hypothesis": json.dumps(final_hypothesis, ensure_ascii=False, indent=2),
            "experiment_design": json.dumps(experiment_design, ensure_ascii=False, indent=2),
            "small_validation": json.dumps(small_validation, ensure_ascii=False, indent=2)
            if small_validation
            else "null",
        }

    # ──────── 校验 ────────

    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        all_hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """验证章节完整性、References 真实性、合规标记"""
        # 顶层字段
        for field in ["title", "paper_title", "paper_abstract", "markdown_content"]:
            if field not in result_dict:
                result_dict[field] = ""

        # chapters 字典
        if "chapters" not in result_dict or not isinstance(result_dict["chapters"], dict):
            result_dict["chapters"] = {}

        chapters = result_dict["chapters"]
        for ch in REPORT_CHAPTERS:
            if ch not in chapters:
                chapters[ch] = [] if ch == "references" else ""

        # ── References 真实性校验 ──
        refs = chapters.get("references", [])
        if not isinstance(refs, list):
            refs = [refs] if refs else []
            chapters["references"] = refs

        ref_check = self._validate_references(refs, literature_facts, citation_map)

        if ref_check["suspicious_count"] > 0 and ref_check["verified_count"] == 0:
            logger.warning(f"参考文献全不可验证: {ref_check['suspicious_count']} 条可疑")
            chapters["references"] = []
            ref_check["references_replaced"] = True

        # ── 合规检查 ──
        compliance = self._build_compliance_check(result_dict, ref_check, literature_facts, all_hypotheses)
        result_dict["compliance_check"] = compliance

        return result_dict

    # ──────── References 校验 ────────

    def _validate_references(
        self,
        references: List[str],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """验证每条引用是否可追溯到 citation_map 或 literature_facts"""
        if not references:
            return {
                "verified_count": 0,
                "suspicious_count": 0,
                "verified_refs": [],
                "suspicious_refs": [],
                "references_replaced": False,
                "note": "暂无文献引用",
            }

        # ── 从 citation_map 构建强验证关键词（标题、作者、DOI、external_id）──
        verified_keywords = set()
        for cit in (citation_map or []):
            for key in ("paper_title", "title", "authors", "doi", "external_id", "source_url"):
                val = cit.get(key, "")
                if isinstance(val, str) and len(val.strip()) >= 5:
                    verified_keywords.add(val.strip().lower())
            # 也加入作者姓
            authors = cit.get("authors", "")
            if isinstance(authors, str) and "," in authors:
                for a in authors.split(","):
                    a = a.strip()
                    if len(a) >= 3:
                        verified_keywords.add(a.lower())

        # ── 从 facts 补充 ──
        for fact in (literature_facts or []):
            title = fact.get("source_paper_title", "")
            if isinstance(title, str) and len(title) >= 5:
                verified_keywords.add(title.lower())
            quote = fact.get("quote_text", "")
            if isinstance(quote, str) and len(quote) >= 20:
                verified_keywords.add(quote[:60].lower())

        verified_refs = []
        suspicious_refs = []

        for ref in references:
            if not ref or not isinstance(ref, str):
                suspicious_refs.append(str(ref) if ref else "(空引用)")
                continue

            ref_lower = ref.lower()
            matched = False
            for kw in verified_keywords:
                if len(kw) >= 6 and kw in ref_lower:
                    matched = True
                    break

            if matched:
                verified_refs.append(ref)
            else:
                suspicious_refs.append(ref)

        return {
            "verified_count": len(verified_refs),
            "suspicious_count": len(suspicious_refs),
            "verified_refs": verified_refs,
            "suspicious_refs": suspicious_refs,
            "references_replaced": False,
        }

    # ──────── 合规检查 ────────

    def _build_compliance_check(
        self,
        result_dict: Dict[str, Any],
        ref_check: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        all_hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """16 项合规检查（含 References / Evidence / Hypothesis / Result）"""
        chapters = result_dict.get("chapters", {})

        items = []
        for key, label in CHALLENGE_CUP_FIELDS:
            if key in ("paper_title",):
                value = result_dict.get("paper_title", "")
            elif key in ("paper_abstract",):
                value = result_dict.get("paper_abstract", "")
            elif key == "references":
                value = chapters.get("references", [])
            else:
                value = chapters.get(key, "")

            # ── References 专项 ──
            if key == "references":
                refs = chapters.get("references", [])
                has_real = any(
                    r and r != "暂无真实文献引用，需补充文献库" and not r.startswith("[待")
                    for r in refs
                )
                if not refs or not has_real:
                    status = "missing"
                    note = "缺少真实引用，需先导入文献库"
                elif ref_check.get("references_replaced"):
                    status = "human_review"
                    note = f"检测到 {ref_check.get('suspicious_count', 0)} 条虚构引用，已清除"
                elif ref_check.get("suspicious_count", 0) > 0:
                    status = "human_review"
                    note = f"{ref_check.get('suspicious_count', 0)} 条引用无法验证，需人工确认"
                else:
                    status = "completed"
                    note = f"{ref_check.get('verified_count', 0)} 条引用已通过文献库验证"
            else:
                if isinstance(value, str) and len(value.strip()) >= 20:
                    status = "completed"
                    note = None
                elif isinstance(value, str) and len(value.strip()) > 0:
                    status = "human_review"
                    note = "内容较短，建议补充"
                else:
                    status = "missing"
                    note = "该字段缺失"

            items.append({"key": key, "label": label, "status": status, "note": note})

        completed = sum(1 for i in items if i["status"] == "completed")
        missing = sum(1 for i in items if i["status"] == "missing")
        needs_review = sum(1 for i in items if i["status"] == "human_review")

        # ── 额外赛题指标 ──
        evidence_fact_count = len(literature_facts) if literature_facts else 0
        hypothesis_with_evidence = sum(
            1 for h in (all_hypotheses or [])
            if h.get("supporting_fact_ids") and len(h.get("supporting_fact_ids", [])) > 0
        )
        has_result = False
        result_type = "none"
        rf = chapters.get("results_feasibility", "")
        if isinstance(rf, str):
            rf_lower = rf.lower()
            if "actual" in rf_lower or "实际" in rf_lower:
                has_result = True
                result_type = "actual_result"
            elif "simulat" in rf_lower or "模拟" in rf_lower or "预期" in rf_lower:
                has_result = True
                result_type = "simulated_or_expected"

        return {
            "total_items": len(CHALLENGE_CUP_FIELDS),
            "completed": completed,
            "missing": missing,
            "human_review": needs_review,
            "references_verified": ref_check.get("verified_count", 0),
            "references_suspicious": ref_check.get("suspicious_count", 0),
            "references_replaced": ref_check.get("references_replaced", False),
            # ── 赛题专属指标 ──
            "evidence_fact_count": evidence_fact_count,
            "hypothesis_with_evidence_count": hypothesis_with_evidence,
            "has_actual_or_simulated_result": has_result,
            "result_type": result_type,
            "items": items,
        }

    # ──────── 运行摘要 ────────

    def _append_run_summary_to_report(
        self, result: Dict[str, Any], run_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            summary_content = self._build_run_summary_content(run_info)
            original = result.get("markdown_content", "")
            result["markdown_content"] = original + "\n" + summary_content
            return result
        except Exception as e:
            logger.error(f"添加运行摘要时出错: {e}", exc_info=True)
            return result

    def _build_run_summary_content(self, run_info: Dict[str, Any]) -> str:
        def fmt_time(ts):
            if isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return str(ts)
            elif isinstance(ts, datetime):
                return ts.strftime("%Y-%m-%d %H:%M:%S")
            return "N/A"

        def fmt_dur(ms):
            if not ms:
                return "N/A"
            s = ms // 1000
            m, s = divmod(s, 60)
            return f"{m}分{s}秒" if m else f"{s}秒"

        run_id = run_info.get("run_id", "N/A")
        summary = (
            "\n\n---\n\n## 运行摘要\n\n"
            f"| 项目 | 值 |\n|------|----|\n"
            f"| 运行 ID | {run_id} |\n"
            f"| 状态 | {run_info.get('status', '?')} |\n"
            f"| 开始 | {fmt_time(run_info.get('started_at'))} |\n"
            f"| 结束 | {fmt_time(run_info.get('completed_at'))} |\n"
            f"| 总耗时 | {fmt_dur(run_info.get('total_duration_ms', 0))} |\n"
        )
        return summary

    # ──────── 文件存储 ────────

    def _save_report_files(
        self, result: Dict[str, Any], project_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        report_id = str(uuid.uuid4())
        report_path = os.path.join(self.reports_dir, report_id)
        os.makedirs(report_path, exist_ok=True)

        md_file = os.path.join(report_path, "report.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(result.get("markdown_content", ""))

        json_file = os.path.join(report_path, "report_data.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        pdf_file = os.path.join(report_path, "report.pdf")
        pdf_result = export_markdown_to_pdf(
            markdown_content=result.get("markdown_content", ""),
            output_path=pdf_file,
            css_path=os.path.join(os.path.dirname(__file__), "report_style.css"),
        )

        logger.info(f"报告文件已保存到: {report_path}")
        return {
            "report_id": report_id,
            "report_path": report_path,
            "md_file": md_file,
            "json_file": json_file,
            "pdf_file": pdf_result.get("pdf_path"),
            "pdf_success": pdf_result.get("success", False),
            "warning": pdf_result.get("warning"),
        }


_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance