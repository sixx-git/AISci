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

            # ── 重新保存 JSON（含 plots），保持 MD/PDF/JSON 一致性 ──
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
                chapters[ch] = [] if ch == "references" else ""

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

        compliance = self._build_compliance_check(
            result_dict, ref_check, literature_facts, all_hypotheses,
            novelty_review_skill_outputs, sanity_check_skill_outputs,
            evidence_facts or [], verified_references or [],
        )
        result_dict["compliance_check"] = compliance
        result_dict["skill_outputs"] = skill_outputs

        return result_dict

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
            chapters.get("datasets", "") and len(chapters.get("datasets", "").strip()) >= 10
        )
        has_source = bool(
            chapters.get("source", "") and len(chapters.get("source", "").strip()) >= 10
        )
        has_target = bool(
            chapters.get("target", "") and len(chapters.get("target", "").strip()) >= 10
        )
        has_paper_title = bool(
            result_dict.get("paper_title", "") and len(result_dict["paper_title"].strip()) >= 5
        )
        has_paper_abstract = bool(
            result_dict.get("paper_abstract", "") and len(result_dict["paper_abstract"].strip()) >= 20
        )
        has_methods = bool(
            chapters.get("methods", "") and len(chapters.get("methods", "").strip()) >= 10
        )
        has_experiments = bool(
            chapters.get("experiments", "") and len(chapters.get("experiments", "").strip()) >= 10
        )
        has_results = bool(
            chapters.get("results", "") and len(chapters.get("results", "").strip()) >= 10
        )
        has_references = bool(
            chapters.get("references", []) and len(chapters.get("references", [])) > 0
        )
        has_rationale = bool(
            chapters.get("rationale", "") and len(chapters.get("rationale", "").strip()) >= 20
        )
        has_technical_details = bool(
            chapters.get("technical_details", "") and len(chapters.get("technical_details", "").strip()) >= 10
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
                chapters.get("problem_statement", "") and len(chapters.get("problem_statement", "").strip()) >= 20
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
                outputs["charts"] = chart_result.data.get("charts", [])
                outputs["skill_outputs"] = {
                    "report_chart_generation": {
                        "success": chart_result.success,
                        "data": chart_result.data,
                        "warnings": chart_result.warnings,
                        "errors": chart_result.errors,
                    }
                }
            except Exception as e:
                logger.warning(f"ReportChartGenerationSkill 失败: {e}")
                outputs["skill_outputs"] = {"report_chart_generation": {"success": False, "error": str(e)}}

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


_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance