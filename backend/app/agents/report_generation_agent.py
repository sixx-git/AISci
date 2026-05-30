"""
报告生成智能体 (ReportGenerationAgent)
——面向挑战杯 XH-202619 赛题，生成《科学假设与研究计划》Markdown + PDF。
严格按 12 个标准化字段输出。
"""
import logging
import json
import os
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.services.pdf_export_service import export_markdown_to_pdf

CHINA_TZ = timezone(timedelta(hours=8))
from app.skills.literature.citation_grounding_skill import CitationGroundingSkill
from app.skills.report.report_chart_generation_skill import ReportChartGenerationSkill
from app.skills.report.scientific_plot_skill import ScientificPlotSkill
from app.skills.report.report_quality_check_skill import ReportQualityCheckSkill

logger = logging.getLogger(__name__)

REPORT_CHAPTERS = [
    "problem_statement",
    "rationale",
    "technical_details",
    "datasets",
    "source",
    "target",
    "methods",
    "experiments",
    "results",
]

CHALLENGE_CUP_12_FIELDS = [
    ("paper_title", "1. Paper Title"),
    ("paper_abstract", "2. Paper Abstract"),
    ("problem_statement", "3. Problem Statement"),
    ("rationale", "4. Rationale"),
    ("technical_details", "5. Technical Details"),
    ("datasets", "6. Datasets"),
    ("source", "7. Source"),
    ("target", "8. Target"),
    ("methods", "9. Methods"),
    ("experiments", "10. Experiments"),
    ("results", "11. Results"),
    ("references", "12. References"),
]


class ReportGenerationAgent:
    """面向挑战杯赛题的科技报告生成智能体"""

    def __init__(self):
        self.reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "..", "storage", "reports"
        )
        os.makedirs(self.reports_dir, exist_ok=True)

    @staticmethod
    def _str_len(value) -> int:
        """安全获取内容的字符串长度，兼容 str / list / dict 类型"""
        if isinstance(value, str):
            return len(value.strip())
        if isinstance(value, (list, dict)):
            return len(value)
        if value is None:
            return 0
        return len(str(value).strip())

    @staticmethod
    def _has_text(value, min_len: int = 1) -> bool:
        """安全判断内容是否有足够长度的非空文本"""
        return ReportGenerationAgent._str_len(value) >= min_len

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
        novelty_review_skill_outputs: Optional[Dict[str, Any]] = None,
        sanity_check_skill_outputs: Optional[Dict[str, Any]] = None,
        evidence_facts: Optional[List[Dict[str, Any]]] = None,
        verified_references: Optional[List[Dict[str, Any]]] = None,
        preliminary_analysis_skill_outputs: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
        data_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            logger.info(f"开始生成研究报告，项目: {project_info.get('title', 'Unknown')}")

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
                evidence_facts or [],
                verified_references or [],
                data_context,
            )

            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "report_generation", formatted_input
            )

            schema_example = {
                "title": "科学假设与研究计划",
                "paper_title": "基于文献挖掘的科学假设与验证计划",
                "paper_abstract": "本文围绕... 通过文献挖掘提取关键事实...",
                "markdown_content": "# 科学假设与研究计划\n\n## 1. Paper Title\n...",
                "chapters": {
                    "problem_statement": "...",
                    "rationale": "...",
                    "technical_details": "...",
                    "datasets": "...",
                    "source": "...",
                    "target": "...",
                    "methods": "...",
                    "experiments": "...",
                    "results": "...",
                    "references": [],
                },
            }

            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="report_generation",
            )

            result = self._validate_and_normalize_result(
                result_dict, literature_facts, citation_map, all_hypotheses,
                novelty_review_skill_outputs, sanity_check_skill_outputs,
                evidence_facts or [], verified_references or [],
            )

            if pipeline_run_info:
                result = self._append_run_summary_to_report(result, pipeline_run_info)

            file_info = self._save_report_files(result, project_info)
            result.update(file_info)

            # ── 生成报告图表 ──
            charts_data = self._run_chart_generation_sync(
                preliminary_analysis_skill_outputs,
                multimodal_datasets,
                result.get("report_id", ""),
            )
            result["plots"] = charts_data.get("charts", [])
            result["chart_skill_outputs"] = charts_data.get("skill_outputs", {})

            # ── 嵌入图表到 markdown ──
            result["markdown_content"] = self._embed_charts_in_markdown(
                result.get("markdown_content", ""),
                result.get("plots", []),
            )

            # ── 丰富 Results 章节（区分 actual/simulated/expected）──
            result = self._enrich_results_with_categorized(
                result, small_validation, preliminary_analysis_skill_outputs
            )

            # ── 报告质量检查 ──
            quality_check_output = self._run_quality_check_sync(
                result,
                verified_references,
                result.get("chart_skill_outputs", {}),
            )
            compliance = result.get("compliance_check", {})
            if isinstance(compliance, dict):
                compliance["report_quality_check"] = quality_check_output
                result["compliance_check"] = compliance
            if result.get("skill_outputs") and isinstance(result["skill_outputs"], dict):
                result["skill_outputs"]["report_quality_check"] = quality_check_output

            qc_data = quality_check_output.get("data", {})
            refs_verified_val = qc_data.get("references_verified", 0) if isinstance(qc_data, dict) else 0
            has_real_plots = qc_data.get("has_real_data_plots", False) if isinstance(qc_data, dict) else False

            chapters = result.get("chapters", {})
            if refs_verified_val == 0:
                if not chapters.get("references"):
                    chapters["references"] = []
                placeholder_note = "缺少真实引用，需先导入 arXiv/BibTeX/PDF 文献。"
                if placeholder_note not in chapters["references"]:
                    chapters["references"].insert(0, placeholder_note)
                markdown = result.get("markdown_content", "")
                if "缺少真实引用" not in markdown:
                    warning_section = (
                        "\n\n---\n\n## ⚠️ 参考文献提醒\n\n"
                        "**缺少真实引用，需先导入 arXiv/BibTeX/PDF 文献。**\n\n"
                        "当前报告参考文献均由 LLM 自行生成，未在文献库中找到可验证的真实文献。"
                        "请前往文献库导入真实文献后重新生成报告。\n"
                    )
                    result["markdown_content"] = markdown + warning_section

            if not has_real_plots:
                markdown = result.get("markdown_content", "")
                if "缺少真实数据图表" not in markdown:
                    plot_warning = (
                        "\n\n---\n\n## ⚠️ 图表数据提醒\n\n"
                        "**当前缺少真实数据图表。**\n\n"
                        "请上传 CSV/Excel 等结构化数据集以启用数据驱动图表生成。"
                        "所有图表均需标记 is_generated_from_real_data=true 以确保数据可追溯。\n"
                    )
                    result["markdown_content"] = markdown + plot_warning

            result["chapters"] = chapters

            # ── 重新保存 PDF & JSON（含 plots），保持 MD/PDF/JSON 一致性 ──
            pdf_result_enriched = export_markdown_to_pdf(
                markdown_content=result.get("markdown_content", ""),
                output_path=result.get("pdf_file", ""),
                css_path=os.path.join(os.path.dirname(__file__), "report_style.css"),
            )
            result["pdf_success"] = pdf_result_enriched.get("success", False)
            self._update_json_with_plots(result)

            logger.info("研究报告生成完成")
            return result

        except Exception as e:
            logger.error(f"生成报告时出错: {e}", exc_info=True)
            raise

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
        evidence_facts: List[Dict[str, Any]] = None,
        verified_references: List[Dict[str, Any]] = None,
        data_context: Optional[Dict[str, Any]] = None,
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
            "evidence_facts": json.dumps(evidence_facts, ensure_ascii=False, indent=2),
            "verified_references": json.dumps(verified_references, ensure_ascii=False, indent=2),
            "data_context": json.dumps(data_context, ensure_ascii=False, indent=2) if data_context else "{}",
        }

    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        all_hypotheses: List[Dict[str, Any]],
        novelty_review_skill_outputs: Optional[Dict[str, Any]] = None,
        sanity_check_skill_outputs: Optional[Dict[str, Any]] = None,
        evidence_facts: List[Dict[str, Any]] = None,
        verified_references: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        for field in ["title", "paper_title", "paper_abstract", "markdown_content"]:
            if field not in result_dict:
                result_dict[field] = ""

        if "chapters" not in result_dict or not isinstance(result_dict["chapters"], dict):
            result_dict["chapters"] = {}

        chapters = result_dict["chapters"]
        for ch in REPORT_CHAPTERS:
            if ch not in chapters:
                if ch == "references":
                    chapters[ch] = []
                elif ch == "datasets":
                    chapters[ch] = []
                elif ch == "source":
                    chapters[ch] = []
                elif ch == "target":
                    chapters[ch] = {}
                elif ch == "experiments":
                    chapters[ch] = {
                        "baselines": [],
                        "metrics": [],
                        "experimental_setup": "",
                        "ablation_study": [],
                        "validation_protocol": "",
                    }
                elif ch == "results":
                    chapters[ch] = {
                        "actual_results": [],
                        "simulated_results": [],
                        "expected_results": [],
                        "limitations": [],
                    }
                else:
                    chapters[ch] = ""

        chapters["datasets"] = self._normalize_to_list(chapters.get("datasets", []))
        chapters["source"] = self._normalize_to_list(chapters.get("source", []))

        target_val = chapters.get("target", {})
        if not isinstance(target_val, dict):
            chapters["target"] = {}

        experiments_val = chapters.get("experiments", {})
        if not isinstance(experiments_val, dict):
            chapters["experiments"] = {
                "baselines": [],
                "metrics": [],
                "experimental_setup": str(experiments_val) if experiments_val else "",
                "ablation_study": [],
                "validation_protocol": "",
            }
        else:
            for exp_key, exp_default in [
                ("baselines", []), ("metrics", []),
                ("experimental_setup", ""), ("ablation_study", []),
                ("validation_protocol", ""),
            ]:
                if exp_key not in experiments_val:
                    experiments_val[exp_key] = exp_default
            chapters["experiments"] = experiments_val

        results_val = chapters.get("results", {})
        if not isinstance(results_val, dict):
            chapters["results"] = {
                "actual_results": [],
                "simulated_results": [],
                "expected_results": [],
                "limitations": [],
            }
        else:
            for res_key, res_default in [
                ("actual_results", []), ("simulated_results", []),
                ("expected_results", []), ("limitations", []),
            ]:
                if res_key not in results_val:
                    results_val[res_key] = res_default
            chapters["results"] = results_val

        refs = chapters.get("references", [])
        if not isinstance(refs, list):
            refs = [refs] if refs else []
            chapters["references"] = refs

        ref_check = self._validate_references(refs, literature_facts, citation_map, verified_references or [])

        skill_outputs = self._run_citation_grounding_sync(
            refs, citation_map, literature_facts, verified_references
        )

        if ref_check["suspicious_count"] > 0 and ref_check["verified_count"] == 0:
            logger.warning(f"参考文献全不可验证: {ref_check['suspicious_count']} 条可疑")
            chapters["references"] = []
            ref_check["references_replaced"] = True

        result_dict["evidence_facts"] = evidence_facts or []
        result_dict["plots"] = result_dict.get("plots", [])
        if "compliance_check" not in result_dict:
            result_dict["compliance_check"] = {}
        if "skill_outputs" not in result_dict:
            result_dict["skill_outputs"] = {}

        compliance = self._build_compliance_check(
            result_dict, ref_check, literature_facts, all_hypotheses,
            novelty_review_skill_outputs, sanity_check_skill_outputs,
            evidence_facts or [], verified_references or [],
        )
        result_dict["compliance_check"] = compliance
        result_dict["skill_outputs"] = skill_outputs

        result_dict["chapters"] = chapters
        return result_dict

    @staticmethod
    def _normalize_to_list(value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            return [value]
        return []

    def _validate_references(
        self,
        references: List[str],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        verified_references: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not references:
            return {
                "verified_count": 0,
                "suspicious_count": 0,
                "verified_refs": [],
                "suspicious_refs": [],
                "references_replaced": False,
                "note": "暂无文献引用",
            }

        verified_keywords = set()
        for cit in (citation_map or []):
            for key in ("paper_title", "title", "authors", "doi", "external_id", "source_url"):
                val = cit.get(key, "")
                if isinstance(val, str) and len(val.strip()) >= 5:
                    verified_keywords.add(val.strip().lower())
            authors = cit.get("authors", "")
            if isinstance(authors, str) and "," in authors:
                for a in authors.split(","):
                    a = a.strip()
                    if len(a) >= 3:
                        verified_keywords.add(a.lower())

        for vr in (verified_references or []):
            for key in ("title", "authors", "doi", "external_id"):
                val = vr.get(key, "")
                if isinstance(val, str) and len(val.strip()) >= 5:
                    verified_keywords.add(val.strip().lower())

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

    @staticmethod
    def _run_citation_grounding_sync(
        references: list,
        citation_map: list,
        literature_facts: list,
        verified_references: list = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                skill = CitationGroundingSkill()
                skill_result = await skill.run(
                    input_data={
                        "references": references,
                        "citation_map": citation_map,
                        "literature_facts": literature_facts,
                        "verified_references": verified_references or [],
                    },
                    context={"stage": "report_generation"},
                )
                return {
                    "citation_grounding": {
                        "success": skill_result.success,
                        "data": skill_result.data,
                        "warnings": skill_result.warnings,
                        "errors": skill_result.errors,
                    }
                }
            except Exception as e:
                logger.warning(f"CitationGroundingSkill 失败: {e}")
                return {"citation_grounding": {"success": False, "error": str(e)}}

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"CitationGroundingSkill 异常: {e}")
            return {}

    @staticmethod
    def _run_quality_check_sync(
        result_dict: Dict[str, Any],
        verified_references: Optional[List[Dict[str, Any]]],
        chart_skill_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                has_real_plots = False
                charts = []
                sp_output = chart_skill_outputs.get("scientific_plot", {})
                if isinstance(sp_output, dict) and sp_output.get("data"):
                    charts = sp_output["data"].get("charts", [])
                    has_real_plots = any(
                        c.get("is_generated_from_real_data") for c in charts
                    )
                references_verified = len(verified_references or [])

                qc_skill = ReportQualityCheckSkill()
                qc_result = await qc_skill.run(
                    input_data={
                        "report_data": result_dict,
                        "references_verified": references_verified,
                        "has_real_data_plots": has_real_plots,
                        "plots": charts,
                    },
                    context={"stage": "report_generation"},
                )
                return {
                    "success": qc_result.success,
                    "data": qc_result.data,
                    "warnings": qc_result.warnings,
                    "errors": qc_result.errors,
                }
            except Exception as e:
                logger.warning(f"ReportQualityCheckSkill 失败: {e}")
                return {"success": False, "error": str(e)}

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"ReportQualityCheckSkill 异常: {e}")
            return {}

    def _build_compliance_check(
        self,
        result_dict: Dict[str, Any],
        ref_check: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        all_hypotheses: List[Dict[str, Any]],
        novelty_review_skill_outputs: Optional[Dict[str, Any]] = None,
        sanity_check_skill_outputs: Optional[Dict[str, Any]] = None,
        evidence_facts: List[Dict[str, Any]] = None,
        verified_references: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        chapters = result_dict.get("chapters", {})

        items = []
        for key, label in CHALLENGE_CUP_12_FIELDS:
            if key in ("paper_title",):
                value = result_dict.get("paper_title", "")
            elif key in ("paper_abstract",):
                value = result_dict.get("paper_abstract", "")
            elif key == "references":
                value = chapters.get("references", [])
            else:
                value = chapters.get(key, "")

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

        evidence_fact_count = len(evidence_facts or literature_facts or [])
        hypothesis_with_evidence = sum(
            1 for h in (all_hypotheses or [])
            if h.get("supporting_fact_ids") and len(h.get("supporting_fact_ids", [])) > 0
        )

        has_result = False
        result_type = "none"
        rf = chapters.get("results", "")
        if isinstance(rf, str):
            rf_lower = rf.lower()
            if "actual_result" in rf_lower or "actual results" in rf_lower or "实际结果" in rf_lower:
                has_result = True
                result_type = "actual_result"
            elif "simulated_result" in rf_lower or "simulated results" in rf_lower or "模拟结果" in rf_lower:
                has_result = True
                result_type = "simulated_result"
            elif "expected_result" in rf_lower or "expected results" in rf_lower or "预期结果" in rf_lower:
                has_result = True
                result_type = "expected_result"
            elif len(rf.strip()) >= 50:
                has_result = True
                if "simulat" in rf_lower or "模拟" in rf_lower:
                    result_type = "simulated_result"
                elif "expect" in rf_lower or "预期" in rf_lower:
                    result_type = "expected_result"

        has_datasets = bool(
            self._has_text(chapters.get("datasets"), min_len=10)
        )
        has_source = bool(
            self._has_text(chapters.get("source"), min_len=10)
        )
        has_target = bool(
            self._has_text(chapters.get("target"), min_len=10)
        )
        has_paper_title = bool(
            self._has_text(result_dict.get("paper_title"), min_len=5)
        )
        has_paper_abstract = bool(
            self._has_text(result_dict.get("paper_abstract"), min_len=20)
        )
        has_methods = bool(
            self._has_text(chapters.get("methods"), min_len=10)
        )
        has_experiments = bool(
            self._has_text(chapters.get("experiments"), min_len=10)
        )
        has_results = bool(
            self._has_text(chapters.get("results"), min_len=10)
        )
        has_references = bool(
            chapters.get("references", []) and len(chapters.get("references", [])) > 0
        )
        has_rationale = bool(
            self._has_text(chapters.get("rationale"), min_len=20)
        )
        has_technical_details = bool(
            self._has_text(chapters.get("technical_details"), min_len=10)
        )

        warnings = []
        critical_issues = []

        if not has_references:
            critical_issues.append("参考文献缺失或未验证，不符合赛题要求")
        if not has_datasets:
            warnings.append("数据集来源不足，请补充真实或合规数据来源")
        if result_type in ("expected_result", "none") and not has_result:
            warnings.append("当前仅有预期结果，建议补充公式推导、模拟验证或小样实验")
        if not has_source:
            warnings.append("缺少真实历史数据来源（Source），需补充数据源")
        if not has_target:
            warnings.append("缺少目标数据特征描述（Target），需补充")

        novelty_score = self._aggregate_novelty_score(novelty_review_skill_outputs)
        experiment_sanity = self._aggregate_sanity_check(sanity_check_skill_outputs)

        return {
            "total_items": len(CHALLENGE_CUP_12_FIELDS),
            "completed": completed,
            "missing": missing,
            "human_review": needs_review,
            "references_verified": ref_check.get("verified_count", 0),
            "references_suspicious": ref_check.get("suspicious_count", 0),
            "references_replaced": ref_check.get("references_replaced", False),
            "evidence_fact_count": evidence_fact_count,
            "hypothesis_with_evidence_count": hypothesis_with_evidence,
            "has_actual_or_simulated_result": has_result,
            "result_type": result_type,
            "novelty_score": novelty_score,
            "experiment_sanity_check": experiment_sanity,
            "has_problem_statement": bool(
                self._has_text(chapters.get("problem_statement"), min_len=20)
            ),
            "has_rationale": has_rationale,
            "has_technical_details": has_technical_details,
            "has_datasets": has_datasets,
            "has_source": has_source,
            "has_target": has_target,
            "has_paper_title": has_paper_title,
            "has_paper_abstract": has_paper_abstract,
            "has_methods": has_methods,
            "has_experiments": has_experiments,
            "has_results": has_results,
            "has_references": has_references,
            "warnings": warnings,
            "critical_issues": critical_issues,
            "items": items,
        }

    @staticmethod
    def _aggregate_novelty_score(
        novelty_outputs: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        if not novelty_outputs:
            return None
        hr_data = novelty_outputs.get("hypothesis_novelty_review", {})
        if isinstance(hr_data, dict):
            return hr_data.get("data", {}).get("novelty_score")
        return None

    @staticmethod
    def _aggregate_sanity_check(
        sanity_outputs: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not sanity_outputs:
            return None
        sc_data = sanity_outputs.get("experiment_sanity_check", {})
        if isinstance(sc_data, dict):
            data = sc_data.get("data")
            if data:
                return data
            return {
                "executable": sc_data.get("executable"),
                "missing_items": sc_data.get("missing_items", []),
                "weak_points": sc_data.get("weak_points", []),
                "recommendations": sc_data.get("recommendations", []),
            }
        return None

    @staticmethod
    def _run_chart_generation_sync(
        preliminary_analysis_skill_outputs: Optional[Dict[str, Any]],
        multimodal_datasets: Optional[List[Dict[str, Any]]],
        report_id: str,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            outputs: Dict[str, Any] = {"charts": [], "skill_outputs": {}}
            plot_specs = []
            data_rows = []

            if preliminary_analysis_skill_outputs:
                pa_data = preliminary_analysis_skill_outputs.get("preliminary_analysis", {})
                if isinstance(pa_data, dict) and pa_data.get("data"):
                    pa_inner = pa_data["data"]
                    plot_specs = pa_inner.get("plots", [])
                    data_rows = pa_inner.get("sample_data_rows", [])
                    if not data_rows:
                        data_rows = pa_inner.get("feature_vectors", [])

            if not data_rows and multimodal_datasets:
                for ds in multimodal_datasets:
                    sample_rows = ds.get("sample_data", []) or ds.get("preview", [])
                    if sample_rows:
                        data_rows.extend(sample_rows[:200])
                        break

            if not data_rows:
                outputs["skill_outputs"] = {
                    "report_chart_generation": {
                        "success": True,
                        "data": {"charts": [], "total_charts": 0},
                        "warnings": ["无真实数据，未生成图表"],
                    }
                }
                return outputs

            if not plot_specs:
                return outputs

            try:
                sci_plot_skill = ScientificPlotSkill()
                sci_result = await sci_plot_skill.run(
                    input_data={
                        "plot_specs": plot_specs,
                        "data": data_rows,
                        "output_dir": "",
                        "format": "both",
                        "dpi": 150,
                        "figure_size": (10, 6),
                    },
                    context={"stage": "report_generation"},
                )
                sci_charts = sci_result.data.get("charts", [])
                if sci_charts:
                    outputs.setdefault("charts", [])
                    existing_ids = {c.get("plot_id", "") for c in outputs["charts"]}
                    for ch in sci_charts:
                        pid = ch.get("plot_id", "")
                        if pid not in existing_ids:
                            outputs["charts"].append(ch)
                            existing_ids.add(pid)
                outputs["skill_outputs"]["scientific_plot"] = {
                    "success": sci_result.success,
                    "data": sci_result.data,
                    "warnings": sci_result.warnings,
                    "errors": sci_result.errors,
                }
            except Exception as e:
                logger.warning(f"ScientificPlotSkill 失败: {e}")
                outputs["skill_outputs"]["scientific_plot"] = {"success": False, "error": str(e)}

            try:
                chart_skill = ReportChartGenerationSkill()
                chart_result = await chart_skill.run(
                    input_data={
                        "plot_specs": plot_specs,
                        "data": data_rows,
                        "output_dir": "",
                        "format": "both",
                        "dpi": 150,
                        "figure_size": (10, 6),
                    },
                    context={"stage": "report_generation"},
                )
                rc_charts = chart_result.data.get("charts", [])
                if rc_charts:
                    outputs.setdefault("charts", [])
                    existing_ids = {c.get("plot_id", "") for c in outputs["charts"]}
                    for ch in rc_charts:
                        pid = ch.get("plot_id", "")
                        if pid not in existing_ids:
                            outputs["charts"].append(ch)
                            existing_ids.add(pid)
                outputs["skill_outputs"]["report_chart_generation"] = {
                    "success": chart_result.success,
                    "data": chart_result.data,
                    "warnings": chart_result.warnings,
                    "errors": chart_result.errors,
                }
            except Exception as e:
                logger.warning(f"ReportChartGenerationSkill 失败: {e}")
                outputs["skill_outputs"]["report_chart_generation"] = {"success": False, "error": str(e)}

            return outputs

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"ChartGeneration 异常: {e}")
            return {"charts": [], "skill_outputs": {}}

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
                    dt_cn = dt.astimezone(CHINA_TZ)
                    return dt_cn.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return str(ts)
            elif isinstance(ts, datetime):
                if ts.tzinfo:
                    dt_cn = ts.astimezone(CHINA_TZ)
                else:
                    dt_cn = ts
                return dt_cn.strftime("%Y-%m-%d %H:%M:%S")
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

    @staticmethod
    def _update_json_with_plots(result: Dict[str, Any]):
        json_file = result.get("json_file", "")
        if not json_file or not os.path.exists(json_file):
            return
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["plots"] = result.get("plots", [])
            data["chart_skill_outputs"] = result.get("chart_skill_outputs", {})
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"更新 JSON plots 失败: {e}")

    @staticmethod
    def _embed_charts_in_markdown(
        markdown_content: str,
        plots: List[Dict[str, Any]],
    ) -> str:
        if not plots:
            return markdown_content

        figures_section = "\n\n---\n\n## Figures\n\n"

        for i, plot in enumerate(plots):
            pid = plot.get("plot_id", f"chart_{i}")
            title = plot.get("title", f"Chart {i + 1}")
            desc = plot.get("description", "")
            chart_type = plot.get("type", "")
            is_real = plot.get("is_generated_from_real_data", False)
            source_id = plot.get("source_dataset_id", "")
            markdown_embed = plot.get("markdown_embed", "")
            base64 = plot.get("base64", "")
            url = plot.get("url", "")

            figures_section += f"### {title}\n\n"
            if desc:
                figures_section += f"{desc}\n\n"

            if markdown_embed:
                figures_section += f"{markdown_embed}\n\n"

            if source_id:
                figures_section += f"- **数据来源**: `{source_id}`\n"
            if is_real:
                figures_section += f"- **数据真实性**: 基于真实数据生成\n"
            else:
                figures_section += f"- **数据真实性**: ⚠️ 非真实数据\n"
            if chart_type:
                figures_section += f"- **图表类型**: {chart_type}\n"

            if not markdown_embed:
                if base64:
                    figures_section += f"  (Base64 编码图片，见 JSON report_data.plots[{i}])\n\n"
                elif url:
                    figures_section += f"  (图片 URL: {url})\n\n"
                else:
                    figures_section += f"  (图表数据不可用)\n\n"

            figures_section += "\n"

        if markdown_content.strip():
            return markdown_content.rstrip() + "\n" + figures_section
        return figures_section

    @staticmethod
    def _enrich_results_with_categorized(
        result: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]],
        preliminary_analysis_skill_outputs: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sv = small_validation or {}
        sv_results = sv.get("results", {})

        if not sv_results or not isinstance(sv_results, dict):
            return result

        pa_so = preliminary_analysis_skill_outputs or {}
        pa_data = pa_so.get("preliminary_analysis", {}).get("data", {})

        result["results"] = {
            "actual_results": sv_results.get("actual_results", {}),
            "simulated_results": sv_results.get("simulated_results", {}),
            "expected_results": sv_results.get("expected_results", {}),
            "result_type_summary": sv_results.get("result_type_summary", "none"),
            "warnings": sv_results.get("warnings", []),
        }

        chapters = result.get("chapters", {})
        if isinstance(chapters, dict):
            existing_results = chapters.get("results", "")
            if not existing_results or len(str(existing_results).strip()) < 50:
                result_type = sv_results.get("result_type_summary", "none")
                enriched = "## 11. Results\n\n"

                actual = sv_results.get("actual_results", {})
                if actual and isinstance(actual, dict) and actual.get("summary_statistics"):
                    enriched += "### Actual Results（实际分析结果）\n\n"
                    enriched += f"- 基于真实数据的统计分析已完成\n"
                    enriched += f"- 分析数据源数量: {actual.get('n_datasets_analyzed', 0)}\n"
                    if actual.get("correlations"):
                        enriched += f"- 检测到 {len(actual.get('correlations', []))} 对相关性\n"
                    if actual.get("anomalies"):
                        enriched += f"- 发现 {len(actual.get('anomalies', []))} 个异常数据点\n"
                    enriched += f"- 数据来源: {actual.get('data_source', 'unknown')}\n\n"

                simulated = sv_results.get("simulated_results", {})
                if simulated and isinstance(simulated, dict) and simulated.get("data"):
                    enriched += "### Simulated Results（模拟结果）\n\n"
                    enriched += f"- 模拟数据已生成\n"
                    if simulated.get("assumptions"):
                        enriched += f"- 模拟假设: {simulated.get('assumptions', '')[:200]}\n"
                    enriched += f"- 说明: {simulated.get('note', 'LLM 生成的模拟数据')}\n\n"

                expected = sv_results.get("expected_results", {})
                if expected and isinstance(expected, dict) and expected.get("hypothesis"):
                    enriched += "### Expected Results（预期结果）\n\n"
                    enriched += f"- 假设: {expected.get('hypothesis', '')[:200]}\n"
                    if expected.get("expected_outcome"):
                        enriched += f"- 预期结果: {expected.get('expected_outcome')}\n"
                    if expected.get("target_variable"):
                        enriched += f"- 目标变量: {expected.get('target_variable')}\n"
                    enriched += f"- 说明: {expected.get('note', '预期结果，需通过实验验证')}\n\n"

                if result_type == "none":
                    enriched += "⚠️ 当前缺少真实数据，未生成实际分析结果。请上传数据集以启用数据驱动分析。\n"

                chapters["results"] = enriched

        result["chapters"] = chapters
        return result


_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance