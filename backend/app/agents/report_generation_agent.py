"""
报告生成智能体 (ReportGenerationAgent)
——生成《科学假设与研究计划》：结构化 chapters + latex_template 导出（report.tex / PDF）。
Markdown 预览由系统按模板中文章节自动生成，不再使用旧版英文编号格式。
"""
import logging
import json
import os
import re
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.services.latex_export_service import export_report_via_latex
from app.core.report_fields import REPORT_SECTION_FIELDS
from app.services.report_content_sanitizer import sanitize_report_result
from app.services.report_compliance_service import (
    chapter_has_experiments,
    chapter_has_results,
    evaluate_chapter_item_status,
)

CHINA_TZ = timezone(timedelta(hours=8))
from app.skills.literature.citation_grounding_skill import CitationGroundingSkill
from app.skills.report.report_quality_check_skill import ReportQualityCheckSkill
from app.skills.report.report_reviewer_skill import ReportReviewerSkill
from app.skills.report.proposal_logic_review_skill import ProposalLogicReviewSkill
from app.skills.evidence_reasoning.citation_integrity_check_skill import CitationIntegrityCheckSkill

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

CHALLENGE_CUP_12_FIELDS = REPORT_SECTION_FIELDS


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
        if isinstance(value, list):
            joined = "\n".join(str(x) for x in value if x is not None)
            return len(joined.strip())
        if isinstance(value, dict):
            return len(json.dumps(value, ensure_ascii=False))
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
        project_mode: str = "general",
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
                "markdown_content": "",
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

            logger.info(f"[报告生成] 步骤1: 调用 LLM 生成报告正文 (prompt_len={len(prompt)})")
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="report_generation",
                max_tokens=8192,
            )
            logger.info(f"[报告生成] 步骤1完成: LLM 已返回 (chapters_keys={list(result_dict.get('chapters', {}).keys())})")

            result_dict = self._enrich_report_with_data_context(result_dict, data_context or {})
            result_dict = self._inject_verified_bibliography(
                result_dict, citation_map, verified_references or [], literature_facts
            )
            if data_context and data_context.get("data_finder_results"):
                result_dict = self._enrich_report_with_data_finder(
                    result_dict, data_context["data_finder_results"]
                )

            result_dict = self._apply_evidence_chain_references(
                result_dict,
                all_hypotheses,
                verified_references=verified_references or [],
                citation_map=citation_map or [],
            )

            result_dict = self._backfill_chapters_from_pipeline(
                result_dict,
                experiment_design=experiment_design,
                data_context=data_context or {},
                small_validation=small_validation,
            )

            result = self._validate_and_normalize_result(
                result_dict, literature_facts, citation_map, all_hypotheses,
                novelty_review_skill_outputs, sanity_check_skill_outputs,
                evidence_facts or [], verified_references or [],
                experiment_design=experiment_design,
            )
            result = self._enrich_rationale_with_evidence_chains(result, all_hypotheses)
            if data_context and data_context.get("multimodal_evidence"):
                result = self._enrich_report_with_multimodal_evidence(result, data_context["multimodal_evidence"])
            logger.info(f"[报告生成] 步骤2完成: 结果校验/归一化 (has_ref={bool(result.get('chapters', {}).get('references'))})")

            result = sanitize_report_result(result, small_validation=small_validation)
            # 净化后若核心章节仍空，从问题理解/假设/实验设计回填，避免 PDF 出现空节
            result = self._backfill_core_chapters_from_context(
                result,
                problem_understanding=problem_understanding,
                final_hypothesis=final_hypothesis,
                knowledge_gaps=knowledge_gaps,
                experiment_design=experiment_design,
            )

            if pipeline_run_info:
                result["run_summary"] = self._build_run_summary_content(pipeline_run_info)

            file_info = self._save_report_files(result, project_info)
            result.update(file_info)
            logger.info(f"[报告生成] 步骤3完成: 报告文件保存 (pdf_success={file_info.get('pdf_success')})")

            # ── 生成报告图表 ──
            logger.info(f"[报告生成] 步骤4: 开始生成图表 (has_data={bool(multimodal_datasets or preliminary_analysis_skill_outputs)})")
            charts_data = self._run_chart_generation_sync(
                preliminary_analysis_skill_outputs,
                multimodal_datasets,
                result.get("report_id", ""),
                pipeline_run_info,
                small_validation=small_validation,
            )
            result["plots"] = charts_data.get("charts", [])
            result["chart_skill_outputs"] = charts_data.get("skill_outputs", {})
            logger.info(f"[报告生成] 步骤4完成: 图表生成 (charts_count={len(result['plots'])})")

            # 图表写入 result.plots，最终 Markdown 由 latex_template 结构统一生成

            # ── 用实验设计/数据配置回填 datasets/source/target（避免误报）──
            result = self._backfill_chapters_from_experiment(
                result, experiment_design, small_validation=small_validation
            )

            # ── 迭代科研叙事提炼（写入 sv，供讨论/摘要护栏使用）──
            iteration_narrative = None
            if small_validation and isinstance(small_validation, dict):
                try:
                    from app.skills.report.iteration_narrative_skill import IterationNarrativeSkill

                    iteration_narrative = IterationNarrativeSkill.build_narrative(
                        small_validation=small_validation,
                        hypothesis=str(small_validation.get("hypothesis") or ""),
                    )
                    small_validation = {
                        **small_validation,
                        "iteration_narrative": iteration_narrative,
                    }
                    if isinstance(result.get("skill_outputs"), dict):
                        result["skill_outputs"]["iteration_narrative"] = iteration_narrative
                    else:
                        result["skill_outputs"] = {"iteration_narrative": iteration_narrative}
                except Exception as exc:
                    logger.warning("IterationNarrativeSkill 跳过: %s", exc)

            # ── 丰富 Results 章节（区分 actual/simulated/expected）──
            result = self._enrich_results_with_categorized(
                result, small_validation, preliminary_analysis_skill_outputs
            )
            result = sanitize_report_result(result, small_validation=small_validation)

            modeling_charts = []
            if small_validation:
                actual = (small_validation.get("results") or {}).get("actual_results") or {}
                modeling_result = actual.get("modeling_result") or {}
                modeling_charts = modeling_result.get("charts") or []
            if modeling_charts:
                existing = result.get("plots") or []
                existing_ids = {p.get("plot_id") for p in existing}
                for chart in modeling_charts:
                    pid = chart.get("plot_id")
                    if pid and pid not in existing_ids:
                        existing.append(chart)
                        existing_ids.add(pid)
                result["plots"] = existing

            # ── P0: 绑定沙箱 experiment artifacts 图表 ──
            if small_validation:
                sandbox_plots = (small_validation.get("artifacts") or {}).get("plots") or []
                actual_sv = (small_validation.get("results") or {}).get("actual_results") or {}
                if not sandbox_plots:
                    sandbox_plots = actual_sv.get("sandbox_plots") or []
                existing = result.get("plots") or []
                existing_ids = {p.get("plot_id") for p in existing}
                for chart in sandbox_plots:
                    pid = chart.get("plot_id") or chart.get("title")
                    if pid and pid not in existing_ids:
                        chart = dict(chart)
                        chart.setdefault("is_generated_from_real_data", True)
                        chart.setdefault("source", "sandbox_execution")
                        existing.append(chart)
                        existing_ids.add(pid)
                result["plots"] = existing
                result["experiment_artifacts"] = small_validation.get("artifacts") or {}

            # ── 报告质量检查 ──
            logger.info(f"[报告生成] 步骤5: 开始质量检查")
            refs_for_qc = result.get("chapters", {}).get("references") or []
            if not isinstance(refs_for_qc, list):
                refs_for_qc = [refs_for_qc] if refs_for_qc else []
            compliance_before_qc = result.get("compliance_check") or {}
            refs_verified_for_qc = int(compliance_before_qc.get("references_verified") or 0)
            if refs_verified_for_qc == 0 and (citation_map or verified_references):
                from app.services.report_compliance_service import reconcile_reference_check

                ref_check_qc = reconcile_reference_check(
                    refs_for_qc,
                    citation_map,
                    verified_references,
                    evidence_facts or literature_facts,
                )
                refs_verified_for_qc = ref_check_qc.get("verified_count", 0)

            quality_check_output = self._run_quality_check_sync(
                result,
                verified_references,
                result.get("chart_skill_outputs", {}),
                references_verified=refs_verified_for_qc,
            )
            compliance = result.get("compliance_check", {})
            if isinstance(compliance, dict):
                compliance["report_quality_check"] = quality_check_output
                result["compliance_check"] = compliance
            if result.get("skill_outputs") and isinstance(result["skill_outputs"], dict):
                result["skill_outputs"]["report_quality_check"] = quality_check_output

            proposal_logic_output = self._run_proposal_logic_review_sync(
                result,
                problem_understanding,
                knowledge_gaps,
            )
            if result.get("skill_outputs") and isinstance(result["skill_outputs"], dict):
                result["skill_outputs"]["proposal_logic_review"] = proposal_logic_output
            if isinstance(result.get("compliance_check"), dict):
                result["compliance_check"]["proposal_logic_review"] = proposal_logic_output

            reviewer_output = self._run_report_reviewer_sync(
                result,
                result.get("skill_outputs", {}).get("citation_grounding", {}).get("data", {}),
                result.get("compliance_check", {}),
            )
            if result.get("skill_outputs") and isinstance(result["skill_outputs"], dict):
                result["skill_outputs"]["report_reviewer"] = reviewer_output
            if isinstance(result.get("compliance_check"), dict):
                result["compliance_check"]["report_reviewer"] = reviewer_output

            logger.info(f"[报告生成] 步骤5完成: 质量检查 (qc_success={quality_check_output.get('success') if isinstance(quality_check_output, dict) else False})")

            qc_data = quality_check_output.get("data", {})
            refs_verified_val = qc_data.get("references_verified", 0) if isinstance(qc_data, dict) else 0

            chapters = result.get("chapters", {})
            if refs_verified_val == 0:
                corpus_refs = chapters.get("references") or []
                has_corpus = bool(corpus_refs) and not any(
                    "缺少真实引用" in str(r) for r in corpus_refs
                )
                if not has_corpus:
                    if not chapters.get("references"):
                        chapters["references"] = []
                    placeholder_note = "缺少真实引用，需先导入 arXiv/BibTeX/PDF 文献。"
                    if placeholder_note not in chapters["references"]:
                        chapters["references"].insert(0, placeholder_note)

            result["chapters"] = chapters

            from app.services.report_compliance_service import refresh_compliance_metrics

            final_refs = chapters.get("references") or []
            if not isinstance(final_refs, list):
                final_refs = [final_refs] if final_refs else []
            result["compliance_check"] = refresh_compliance_metrics(
                result.get("compliance_check"),
                references=final_refs,
                citation_map=citation_map,
                verified_references=verified_references,
                literature_facts=evidence_facts or literature_facts,
                hypotheses=all_hypotheses,
                chapters=chapters,
                experiment_design=experiment_design if isinstance(experiment_design, dict) else None,
            )

            # ── 按 latex_template 导出 LaTeX/PDF ──
            result = sanitize_report_result(result, small_validation=small_validation)
            result = self._backfill_core_chapters_from_context(
                result,
                problem_understanding=problem_understanding,
                final_hypothesis=final_hypothesis,
                knowledge_gaps=knowledge_gaps,
                experiment_design=experiment_design,
            )
            result["markdown_content"] = ""
            export_info = self._export_report_pdf(
                result,
                project_info,
                citation_map,
                verified_references or [],
            )
            result.update(export_info)
            if citation_map:
                result["citation_map"] = citation_map
            if verified_references:
                result["verified_references"] = verified_references
            self._write_report_json(result)

            # ── 大家长 Agent 报告后专项检查 ──
            try:
                from app.agents.coordinator_agent import CoordinatorAgent
                coordinator = CoordinatorAgent(db=self.db)
                coordinator_result = result.get("compliance_check", {})
                reviewer_data = result.get("skill_outputs", {}).get("report_reviewer", {}).get("data", {})
                proposal_data = result.get("skill_outputs", {}).get("proposal_logic_review", {}).get("data", {})

                report_check_data = {
                    "quality_score": coordinator_result.get("score", 100),
                    "critical_issues": coordinator_result.get("critical_issues", []),
                    "missing_sections": coordinator_result.get("missing_fields", []),
                    "has_references": bool(result.get("verified_references", [])),
                    "refs_verified": coordinator_result.get("references_verified", 0),
                    "review_score": reviewer_data.get("review_score", 0),
                    "publish_ready": reviewer_data.get("publish_ready", False),
                    "weaknesses": reviewer_data.get("weaknesses", []),
                    "proposal_issues": proposal_data.get("issues", []),
                    "chapters": result.get("chapters", {}),
                }
                coordinator_decision = coordinator.check_report_post(report_check_data)
                result["coordinator_check"] = {
                    "decision": coordinator_decision,
                    "stage": "report_generation_post",
                    "timestamp": coordinator_decision.get("timestamp", ""),
                }
                logger.info(
                    f"[大家长] 报告后检查完成: severity={coordinator_decision.get('severity')} "
                    f"message={coordinator_decision.get('message', '')[:100]}"
                )
            except Exception as coord_err:
                logger.warning(f"[大家长] 报告后检查失败: {coord_err}")

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
        experiment_design: Optional[Dict[str, Any]] = None,
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

        target_val = chapters.get("target", "")
        if isinstance(target_val, dict):
            if target_val:
                chapters["target"] = "\n".join(
                    f"{k}: {v}" for k, v in target_val.items() if v not in (None, "", [], {})
                )
            else:
                chapters["target"] = ""
        elif target_val is None:
            chapters["target"] = ""
        else:
            chapters["target"] = str(target_val)

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
            text_note = str(results_val).strip()
            results_val = {
                "actual_results": [],
                "simulated_results": [],
                "expected_results": [text_note] if text_note else [],
                "limitations": [],
            }
            chapters["results"] = results_val
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
            corpus_refs = self._format_corpus_references(citation_map, verified_references or [])
            if corpus_refs:
                chapters["references"] = corpus_refs
                ref_check["references_replaced"] = True
                ref_check["verified_count"] = len(corpus_refs)
                ref_check["note"] = "已替换为文献库/检索到的可验证引用"
            else:
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
            experiment_design=experiment_design,
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
            from app.core.async_utils import run_coroutine_sync
            return run_coroutine_sync(_run())
        except Exception as e:
            logger.warning(f"CitationGroundingSkill 异常: {e}")
            return {}

    @staticmethod
    def _run_quality_check_sync(
        result_dict: Dict[str, Any],
        verified_references: Optional[List[Dict[str, Any]]],
        chart_skill_outputs: Dict[str, Any],
        references_verified: Optional[int] = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                has_real_plots = False
                charts = list(result_dict.get("plots") or [])
                sp_output = chart_skill_outputs.get("scientific_plot", {})
                if not charts and isinstance(sp_output, dict) and sp_output.get("data"):
                    charts = sp_output["data"].get("charts", [])
                if charts:
                    has_real_plots = any(c.get("is_generated_from_real_data") for c in charts)
                refs_verified_count = (
                    references_verified
                    if references_verified is not None
                    else len(verified_references or [])
                )

                qc_skill = ReportQualityCheckSkill()
                qc_result = await qc_skill.run(
                    input_data={
                        "report_data": result_dict,
                        "references_verified": refs_verified_count,
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
                return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

        try:
            from app.core.async_utils import run_coroutine_sync
            return run_coroutine_sync(asyncio.wait_for(_run(), timeout=180))
        except asyncio.TimeoutError:
            logger.warning("ReportQualityCheckSkill 超时 (180s)")
            return {"success": False, "data": {}, "error": "timeout after 180s", "warnings": [], "errors": ["timeout after 180s"]}
        except Exception as e:
            logger.warning(f"ReportQualityCheckSkill 异常: {e}")
            return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

    @staticmethod
    def _run_proposal_logic_review_sync(
        result_dict: Dict[str, Any],
        problem_understanding: Optional[Dict[str, Any]] = None,
        knowledge_gaps: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                skill = ProposalLogicReviewSkill()
                skill_result = await skill.run(
                    input_data={
                        "report_data": result_dict,
                        "problem_understanding": problem_understanding or {},
                        "knowledge_gaps": knowledge_gaps or {},
                    },
                    context={"stage": "report_generation"},
                )
                return {
                    "success": skill_result.success,
                    "data": skill_result.data,
                    "warnings": skill_result.warnings,
                    "errors": skill_result.errors,
                }
            except Exception as e:
                logger.warning(f"ProposalLogicReviewSkill 失败: {e}")
                return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

        try:
            from app.core.async_utils import run_coroutine_sync
            return run_coroutine_sync(asyncio.wait_for(_run(), timeout=120))
        except asyncio.TimeoutError:
            logger.warning("ProposalLogicReviewSkill 超时 (120s)")
            return {"success": False, "data": {}, "error": "timeout after 120s", "warnings": [], "errors": ["timeout after 120s"]}
        except Exception as e:
            logger.warning(f"ProposalLogicReviewSkill 异常: {e}")
            return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

    @staticmethod
    def _run_report_reviewer_sync(
        result_dict: Dict[str, Any],
        citation_grounding: Optional[Dict[str, Any]] = None,
        compliance_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                reviewer = ReportReviewerSkill()
                reviewer_result = await reviewer.run(
                    input_data={
                        "report_data": result_dict,
                        "citation_grounding": citation_grounding or {},
                        "compliance_metrics": compliance_metrics or {},
                        "pipeline_context": result_dict.get("pipeline_context") or {},
                    },
                    context={"stage": "report_generation"},
                )
                return {
                    "success": reviewer_result.success,
                    "data": reviewer_result.data,
                    "warnings": reviewer_result.warnings,
                    "errors": reviewer_result.errors,
                }
            except Exception as e:
                logger.warning(f"ReportReviewerSkill 失败: {e}")
                return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

        try:
            from app.core.async_utils import run_coroutine_sync
            return run_coroutine_sync(asyncio.wait_for(_run(), timeout=180))
        except asyncio.TimeoutError:
            logger.warning("ReportReviewerSkill 超时 (180s)")
            return {"success": False, "data": {}, "error": "timeout after 180s", "warnings": [], "errors": ["timeout after 180s"]}
        except Exception as e:
            logger.warning(f"ReportReviewerSkill 异常: {e}")
            return {"success": False, "data": {}, "error": str(e), "warnings": [], "errors": [str(e)]}

    @staticmethod
    def _run_citation_integrity_sync(
        supporting_evidence: list,
        counter_evidence: list,
        citation_map: list,
        facts: list,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            try:
                skill = CitationIntegrityCheckSkill()
                skill_result = await skill.run(
                    input_data={
                        "supporting_evidence": supporting_evidence,
                        "counter_evidence": counter_evidence,
                        "citation_map": citation_map,
                        "facts": facts,
                    },
                    context={"stage": "report_generation"},
                )
                return {
                    "success": skill_result.success,
                    "data": skill_result.data,
                    "warnings": skill_result.warnings,
                    "errors": skill_result.errors,
                }
            except Exception as e:
                logger.warning(f"CitationIntegrityCheckSkill 失败: {e}")
                return {"success": False, "error": str(e)}

        try:
            from app.core.async_utils import run_coroutine_sync
            return run_coroutine_sync(_run())
        except Exception as e:
            logger.warning(f"CitationIntegrityCheckSkill 异常: {e}")
            return {}

    @staticmethod
    def _enrich_rationale_with_evidence_chains(
        result: Dict[str, Any],
        all_hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        primary = None
        for h in all_hypotheses or []:
            chain = h.get("evidence_chain")
            if chain and (chain.get("supporting_evidence") or chain.get("counter_evidence")):
                primary = chain
                break

        if not primary:
            return result

        rationale_parts = [chapters.get("rationale", "")] if chapters.get("rationale") else []
        rationale_parts.append("\n\n### 支持证据归纳\n")
        for ev in primary.get("supporting_evidence", [])[:5]:
            rationale_parts.append(
                f"- [{ev.get('stance', 'support')}] {ev.get('claim', '')[:200]} "
                f"(来源: {ev.get('source_title', '未知')}, 相关度={ev.get('relevance_score', 0)})\n"
            )

        rationale_parts.append("\n### 反对证据复核\n")
        counter = primary.get("counter_evidence", [])
        if counter:
            for ev in counter[:3]:
                rationale_parts.append(
                    f"- [{ev.get('stance', 'refute')}] {ev.get('claim', '')[:200]} "
                    f"(来源: {ev.get('source_title', '未知')})\n"
                )
        else:
            reason = primary.get("counter_evidence_empty_reason") or "文献不足，未检索到可验证反例"
            rationale_parts.append(f"- {reason}\n")

        rationale_parts.append("\n### 假设修正过程\n")
        for rev in primary.get("revision_history", [])[:3]:
            rationale_parts.append(
                f"- 第 {rev.get('round', '?')} 轮: {rev.get('revision_reason', '')}\n"
                f"  变更: {', '.join(rev.get('what_changed', []))}\n"
            )

        rationale_parts.append("\n### 最终假设形成逻辑\n")
        rationale_parts.append(
            f"综合 {primary.get('support_count', 0)} 条支持与 {primary.get('counter_count', 0)} 条反对证据，"
            f"证据平衡分={primary.get('evidence_balance_score', 0)}，"
            f"形成最终假设：{primary.get('final_version', '')[:300]}\n"
        )

        chapters["rationale"] = "".join(rationale_parts)
        result["chapters"] = chapters
        return result

    @staticmethod
    def _format_corpus_references(
        citation_map: List[Dict[str, Any]],
        verified_references: List[Dict[str, Any]],
    ) -> List[str]:
        """统一为 GB/T 7714 风格文本行（与合规/导出回填同一出口）。"""
        from app.services.latex_export_service import format_reference_items_as_gbt7714_lines

        return format_reference_items_as_gbt7714_lines(citation_map, verified_references)

    def _inject_verified_bibliography(
        self,
        result: Dict[str, Any],
        citation_map: List[Dict[str, Any]],
        verified_references: List[Dict[str, Any]],
        literature_facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        corpus_refs = self._format_corpus_references(citation_map, verified_references)
        existing = chapters.get("references") or []
        if not isinstance(existing, list):
            existing = [existing] if existing else []

        if corpus_refs:
            chapters["references"] = corpus_refs
            result["chapters"] = chapters

        source_text = chapters.get("source", "") or ""
        if isinstance(source_text, list):
            source_text = "\n".join(str(x) for x in source_text)
        if literature_facts:
            source_text += "\n\n【文献库抽取事实】\n"
            for fact in literature_facts[:8]:
                if not isinstance(fact, dict):
                    continue
                title = fact.get("source_paper_title") or fact.get("source_title") or "未知文献"
                snippet = (fact.get("fact") or fact.get("quote_text") or "").strip()
                if snippet:
                    source_text += f"- {title}: {snippet[:220]}\n"
        if citation_map:
            source_text += "\n\n【已检索/入库文献】\n"
            for cit in citation_map[:10]:
                if not isinstance(cit, dict):
                    continue
                title = cit.get("title") or cit.get("paper_title") or ""
                if title:
                    source_text += f"- {title}\n"
        chapters["source"] = source_text.strip()
        result["chapters"] = chapters
        return result

    @staticmethod
    def _enrich_report_with_data_context(
        result: Dict[str, Any],
        data_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not data_context:
            return result
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        datasets_text = chapters.get("datasets") or ""
        if isinstance(datasets_text, list):
            datasets_text = "\n".join(str(x) for x in datasets_text)

        project_datasets = data_context.get("datasets") or []
        if project_datasets:
            datasets_text += "\n\n【项目已上传数据集】\n"
            for ds in project_datasets[:10]:
                if not isinstance(ds, dict):
                    continue
                datasets_text += (
                    f"- {ds.get('filename', 'dataset')}: "
                    f"{ds.get('n_rows', 0)} 行 × {ds.get('n_columns', 0)} 列, "
                    f"类型={ds.get('data_type', 'unknown')}, 来源={ds.get('source_type', 'upload')}\n"
                )

        recommended = data_context.get("recommended_datasets") or []
        if recommended:
            datasets_text += "\n\n【推荐外部数据库/数据集】\n"
            for cand in recommended[:12]:
                if not isinstance(cand, dict):
                    continue
                name = cand.get("dataset_name") or cand.get("name") or "未命名数据集"
                platform = cand.get("source_platform") or cand.get("catalog_source") or ""
                desc = (cand.get("description") or "")[:160]
                status = cand.get("user_upload_status") or cand.get("availability") or ""
                datasets_text += f"- {name} ({platform}) [{status}]: {desc}\n"

        uploaded_ext = data_context.get("uploaded_external_datasets") or []
        if uploaded_ext:
            datasets_text += "\n\n【用户已上传的外部数据】\n"
            for item in uploaded_ext:
                datasets_text += f"- {item.get('dataset_name') or item.get('filename')}\n"

        if datasets_text.strip():
            chapters["datasets"] = datasets_text.strip()

        result["chapters"] = chapters
        return result

    @staticmethod
    def _enrich_report_with_data_finder(
        result: Dict[str, Any],
        data_finder_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        tables = data_finder_results.get("extracted_tables") or []
        provenance = data_finder_results.get("provenance") or []
        merged = data_finder_results.get("merged") or {}
        data_spec = data_finder_results.get("data_spec") or {}
        figures = data_finder_results.get("figures") or []
        coverage = data_finder_results.get("coverage_report") or {}
        spec_cov = coverage.get("data_spec_coverage") or {}

        datasets_raw = chapters.get("datasets") or ""
        if isinstance(datasets_raw, list):
            datasets_text = "\n".join(str(x) for x in datasets_raw if x is not None)
        elif isinstance(datasets_raw, dict):
            datasets_text = json.dumps(datasets_raw, ensure_ascii=False)
        else:
            datasets_text = str(datasets_raw)
        needs_df_block = "【多源数据查找与整合】" not in datasets_text
        if needs_df_block:
            datasets_text += "\n\n【多源数据查找与整合】\n"
            if data_spec:
                datasets_text += (
                    f"DataSpec 场景={data_spec.get('scenario', 'general')}；"
                    f"实体字段={', '.join(data_spec.get('entities_of_interest') or []) or '—'}；"
                    f"目标变量={', '.join(data_spec.get('target_variables') or []) or '—'}。\n"
                )
            if tables:
                pdf_tables = [
                    t for t in tables
                    if (t.get("extraction_method") or "") not in (
                        "fits_data", "fits_catalog", "user_upload", "user_upload_external",
                    )
                ]
                upload_tables = [
                    t for t in tables
                    if (t.get("extraction_method") or "") in (
                        "fits_data", "fits_catalog", "user_upload", "user_upload_external",
                    )
                ]
                if pdf_tables:
                    datasets_text += f"从 {len(pdf_tables)} 个 PDF/文献表格抽取 CSV；"
                    for t in pdf_tables[:5]:
                        datasets_text += (
                            f"\n- {t.get('source_title', '')} Table page {t.get('page')} "
                            f"({t.get('table_id', '')}, quality={t.get('quality_score')})"
                        )
                if upload_tables:
                    datasets_text += f"\n用户上传/天文 FITS 解析表 {len(upload_tables)} 个："
                    for t in upload_tables[:6]:
                        datasets_text += (
                            f"\n- {t.get('source_title', t.get('caption', ''))[:120]} "
                            f"({t.get('table_id', '')}, rows={t.get('row_count', '?')}, "
                            f"method={t.get('extraction_method', '')})"
                        )
                if not pdf_tables and not upload_tables:
                    datasets_text += "未抽取到结构化表格。"
            else:
                datasets_text += "未从 PDF 抽取到结构化表格。"
            if merged.get("merged_csv_path") or merged.get("cleaned_csv_path"):
                row_count = merged.get("row_count", 0)
                cleaned = "（已清洗）" if merged.get("cleaned_csv_path") else ""
                datasets_text += f"\n已合并 CSV：{row_count} 行{cleaned}。"
            if coverage.get("completeness_score") is not None:
                datasets_text += (
                    f"\n数据发现完备性得分：{coverage.get('completeness_score')}/100。"
                )
            if spec_cov.get("data_spec_score") is not None:
                datasets_text += (
                    f" DataSpec 字段覆盖率：{spec_cov.get('data_spec_score')}/100"
                    f"（实体命中 {len(spec_cov.get('entities_hit') or [])}/"
                    f"{len(spec_cov.get('entities_requested') or [])}，"
                    f"目标变量命中 {len(spec_cov.get('targets_hit') or [])}/"
                    f"{len(spec_cov.get('targets_requested') or [])}）。"
                )
            gaps = coverage.get("gaps") or []
            if gaps:
                datasets_text += f" 待补充：{'; '.join(gaps[:3])}"
        chapters["datasets"] = datasets_text

        source_raw = chapters.get("source") or ""
        source_text = source_raw if isinstance(source_raw, str) else str(source_raw)
        if needs_df_block and "【数据来源与抽取依据】" not in source_text:
            source_text += "\n\n【数据来源与抽取依据】\n"
            for p in provenance[:8]:
                cite = p.get("data_citation_id") or p.get("record_id") or ""
                cite_tag = f" cite={cite}" if cite else ""
                source_text += (
                    f"- [{p.get('source_type')}] {p.get('source_title')} "
                    f"page={p.get('page')} {p.get('table_or_figure')} "
                    f"method={p.get('extraction_method')} confidence={p.get('confidence')}{cite_tag}\n"
                )

            manifests = []
            for fig in figures[:6]:
                manifest = fig.get("extraction_manifest") or {}
                if not manifest:
                    continue
                ident = manifest.get("identification") or {}
                extr = manifest.get("extraction") or {}
                valid = manifest.get("validation") or {}
                fig_id = manifest.get("figure_id") or fig.get("figure_id", "")
                lims = extr.get("limitations") or []
                lim_note = f"；限制: {lims[0]}" if lims else ""
                manifests.append(
                    f"- Fig {ident.get('figure_number', '?')} ({fig_id}): "
                    f"tier={extr.get('tier', '?')}, method={extr.get('method', '?')}, "
                    f"confidence={extr.get('confidence', '?')}, "
                    f"status={valid.get('status', 'pending')}{lim_note}"
                )
            if manifests:
                source_text += "\n【图表 extraction manifest】\n" + "\n".join(manifests) + "\n"
        chapters["source"] = source_text

        results_val = chapters.get("results") or {}
        if not isinstance(results_val, dict):
            text_note = str(results_val).strip()
            results_val = {
                "actual_results": [],
                "simulated_results": [],
                "expected_results": [text_note] if text_note else [],
                "limitations": [],
            }
        else:
            for key in ("actual_results", "simulated_results", "expected_results", "limitations"):
                raw = results_val.get(key)
                if raw is None or raw == "":
                    results_val[key] = []
                elif isinstance(raw, str):
                    results_val[key] = [raw] if raw.strip() else []
                elif not isinstance(raw, list):
                    results_val[key] = [str(raw)]
        csv_used = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
        if csv_used:
            cleaning = merged.get("cleaning_report") or {}
            clean_note = ""
            if cleaning.get("rows_before") is not None:
                clean_note = (
                    f"；清洗 {cleaning.get('rows_before')}→{cleaning.get('rows_after')} 行"
                )
            cols = merged.get("columns") or []
            col_note = f"，字段={', '.join(str(c) for c in cols[:8])}" if cols else ""
            merge_note = (
                f"【整合数据集】data_finder 合并 CSV：{merged.get('row_count', 0)} 行"
                f"{col_note}{clean_note}。"
            )
            upload_tables = [
                t for t in tables
                if (t.get("extraction_method") or "") in ("fits_data", "user_upload", "user_upload_external")
            ]
            if upload_tables:
                t0 = upload_tables[0]
                merge_note += (
                    f" 含用户上传解析表 {t0.get('source_title', '')[:80]}"
                    f"（{t0.get('row_count', '?')} 行，{t0.get('extraction_method', '')}）。"
                )
            sim = list(results_val.get("simulated_results") or [])
            if merge_note not in sim:
                sim.append(merge_note)
            results_val["simulated_results"] = sim
            if not (results_val.get("actual_results") or []):
                exp_note = (
                    "小样验证未执行；上列为已上传/合并数据的描述性统计，"
                    "可基于合并 CSV 做轨道衰减或光谱切片相关分析。"
                )
                exp = list(results_val.get("expected_results") or [])
                if exp_note not in exp:
                    exp.append(exp_note)
                results_val["expected_results"] = exp
        chapters["results"] = results_val
        result["chapters"] = chapters
        result["data_finder_summary"] = {
            "tables_count": len(tables),
            "merged_rows": merged.get("row_count", 0),
            "provenance_count": len(provenance),
            "completeness_score": coverage.get("completeness_score"),
            "data_spec_score": spec_cov.get("data_spec_score"),
            "figures_with_manifest": spec_cov.get("figures_with_manifest")
            or sum(1 for f in figures if f.get("extraction_manifest")),
            "has_cleaned_csv": bool(merged.get("cleaned_csv_path")),
            "bundle_ready": bool((data_finder_results.get("analysis_bundle") or {}).get("ready")),
        }
        return result

    @staticmethod
    def _backfill_core_chapters_from_context(
        result: Dict[str, Any],
        *,
        problem_understanding: Optional[Dict[str, Any]] = None,
        final_hypothesis: Optional[Dict[str, Any]] = None,
        knowledge_gaps: Optional[Any] = None,
        experiment_design: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """当 problem_statement / rationale / technical_details 为空时，从上游阶段回填。

        典型场景：LLM 漏写，或正文含「多智能体」等科研词曾被过度净化清空。
        """
        chapters = result.get("chapters")
        if not isinstance(chapters, dict):
            return result
        chapters = dict(chapters)
        pu = problem_understanding if isinstance(problem_understanding, dict) else {}
        fh = final_hypothesis if isinstance(final_hypothesis, dict) else {}
        ed = experiment_design if isinstance(experiment_design, dict) else {}

        def _needs(key: str, min_len: int = 20) -> bool:
            return len(str(chapters.get(key) or "").strip()) < min_len

        def _join_parts(parts: List[str]) -> str:
            seen: set = set()
            out: List[str] = []
            for p in parts:
                s = str(p or "").strip()
                if not s or s in seen:
                    continue
                seen.add(s)
                out.append(s)
            return "\n\n".join(out)

        if _needs("problem_statement"):
            parts: List[str] = []
            for key in ("problem_statement", "main_contradiction", "phenomenon_contradiction"):
                val = str(pu.get(key) or "").strip()
                if val:
                    label = {
                        "problem_statement": "研究问题",
                        "main_contradiction": "主要矛盾",
                        "phenomenon_contradiction": "矛盾来源",
                    }[key]
                    parts.append(f"**{label}。** {val}" if key != "problem_statement" else val)
            ro = pu.get("research_object") or {}
            if isinstance(ro, dict) and any(str(ro.get(k) or "").strip() for k in ("internal", "external", "boundary")):
                def _trim(s: str) -> str:
                    return str(s or "—").strip().rstrip("。；;,.，")

                parts.append(
                    "**研究对象拆解。** "
                    f"内部：{_trim(ro.get('internal'))}；"
                    f"外部：{_trim(ro.get('external'))}；"
                    f"边界：{_trim(ro.get('boundary'))}。"
                )
            scope = str(pu.get("scope_boundary") or "").strip()
            if scope:
                parts.append(f"**研究范围。** {scope}")
            hyp = str(fh.get("hypothesis") or ed.get("hypothesis") or "").strip()
            if hyp:
                parts.append(f"**待检验科学假设。** {hyp}")
            filled = _join_parts(parts)
            if filled:
                chapters["problem_statement"] = filled

        if _needs("rationale"):
            parts = []
            sig = str(pu.get("research_significance") or "").strip()
            if sig:
                parts.append(f"**科研价值。** {sig}")
            notes = str(pu.get("decomposition_notes") or "").strip()
            if notes:
                parts.append(f"**机制说明。** {notes}")
            # 知识空白
            gaps = knowledge_gaps
            gap_items: List[str] = []
            if isinstance(gaps, dict):
                for g in (gaps.get("gaps") or gaps.get("knowledge_gaps") or [])[:5]:
                    if isinstance(g, dict):
                        desc = str(g.get("description") or g.get("gap") or g.get("title") or "").strip()
                    else:
                        desc = str(g or "").strip()
                    if desc:
                        gap_items.append(desc)
            elif isinstance(gaps, list):
                for g in gaps[:5]:
                    if isinstance(g, dict):
                        desc = str(g.get("description") or g.get("gap") or g.get("title") or "").strip()
                    else:
                        desc = str(g or "").strip()
                    if desc:
                        gap_items.append(desc)
            if gap_items:
                parts.append("**知识空白。**\n" + "\n".join(f"- {g}" for g in gap_items))
            hyp = str(fh.get("hypothesis") or ed.get("hypothesis") or "").strip()
            hyp_r = str(fh.get("rationale") or "").strip()
            if hyp:
                parts.append(f"**科学假设。** {hyp}")
            if hyp_r:
                parts.append(f"**假设依据。** {hyp_r}")
            domain = str(pu.get("research_domain") or "").strip()
            if domain:
                parts.append(f"**所属领域。** {domain}")
            filled = _join_parts(parts)
            if filled:
                chapters["rationale"] = filled

        if _needs("technical_details"):
            parts = []
            methods = str(ed.get("methods") or ed.get("experimental_steps") or chapters.get("methods") or "").strip()
            if methods:
                # 去掉仅有边界声明的极短 methods
                if len(methods) >= 40:
                    parts.append(methods)
            constraints = pu.get("constraints") or []
            if isinstance(constraints, list) and constraints:
                c_lines = [str(c).strip() for c in constraints if str(c).strip()]
                if c_lines:
                    parts.append("**约束条件。**\n" + "\n".join(f"- {c}" for c in c_lines[:8]))
            expected = pu.get("expected_output") or []
            if isinstance(expected, list) and expected:
                e_lines = [str(c).strip() for c in expected if str(c).strip()]
                if e_lines:
                    parts.append("**预期技术产出。**\n" + "\n".join(f"- {c}" for c in e_lines[:8]))
            keywords = pu.get("keywords") or []
            if isinstance(keywords, list) and keywords:
                parts.append("**关键词。** " + "、".join(str(k).strip() for k in keywords[:12] if str(k).strip()))
            filled = _join_parts(parts)
            if filled:
                chapters["technical_details"] = filled

        # experiments：若结构字段空但 setup 含标签，拆分
        exp = chapters.get("experiments")
        if isinstance(exp, dict):
            try:
                from app.services.latex_export_service import _normalize_experiments_dict

                chapters["experiments"] = _normalize_experiments_dict(exp)
            except Exception:
                logger.warning("experiments 章节归一化失败", exc_info=True)

        result["chapters"] = chapters
        return result

    @staticmethod
    def _backfill_chapters_from_pipeline(
        result: Dict[str, Any],
        *,
        experiment_design: Optional[Dict[str, Any]] = None,
        data_context: Optional[Dict[str, Any]] = None,
        small_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """用实验设计 / 数据上下文 / 小样验证回填 LLM 未写的 target、results 等章节。"""
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        ed = experiment_design if isinstance(experiment_design, dict) else {}
        ctx = data_context if isinstance(data_context, dict) else {}
        sv = small_validation if isinstance(small_validation, dict) else {}

        def _needs_text(val: Any, min_len: int = 10) -> bool:
            if val is None:
                return True
            if isinstance(val, dict):
                return not any(str(v).strip() for v in val.values() if v not in (None, [], {}))
            return len(str(val).strip()) < min_len

        if _needs_text(chapters.get("target")):
            target_parts: List[str] = []
            ed_target = (ed.get("target_data") or "").strip()
            if ed_target:
                target_parts.append(ed_target)
            df = ctx.get("data_finder_results") if isinstance(ctx.get("data_finder_results"), dict) else {}
            spec = df.get("data_spec") if isinstance(df.get("data_spec"), dict) else {}
            tvars = spec.get("target_variables") or []
            if tvars:
                target_parts.append("目标变量: " + ", ".join(str(x) for x in tvars[:10]))
            for cand in (ctx.get("target_candidates") or [])[:8]:
                if isinstance(cand, str) and cand.strip():
                    target_parts.append(f"候选目标列: {cand.strip()}")
                elif isinstance(cand, dict):
                    name = cand.get("name") or cand.get("column") or ""
                    if name:
                        target_parts.append(f"候选目标列: {name}")
            if target_parts:
                chapters["target"] = "\n".join(dict.fromkeys(target_parts))

        if _needs_text(chapters.get("source")):
            src = (ed.get("source_data") or "").strip()
            if src:
                chapters["source"] = src

        exp = chapters.get("experiments")
        if isinstance(exp, dict) and not any(
            exp.get(k) for k in ("baselines", "metrics", "experimental_setup", "validation_protocol")
        ):
            chapters["experiments"] = {
                "baselines": [b.strip() for b in (ed.get("baselines") or "").split("\n") if b.strip()],
                "metrics": [m.strip() for m in (ed.get("metrics") or "").split("\n") if m.strip()],
                "experimental_setup": (ed.get("experimental_steps") or ed.get("methods") or "")[:2000],
                "ablation_study": [],
                "validation_protocol": (ed.get("limitations") or "")[:800],
            }
        elif _needs_text(exp if isinstance(exp, str) else ""):
            exp_parts = [
                p for p in (
                    ed.get("experimental_steps"),
                    ed.get("baselines"),
                    ed.get("metrics"),
                ) if isinstance(p, str) and p.strip()
            ]
            if exp_parts:
                chapters["experiments"] = "\n\n".join(exp_parts)

        res = chapters.get("results")
        sv_results = sv.get("results") if isinstance(sv.get("results"), dict) else {}
        if not sv_results and isinstance(res, dict):
            empty_results = not any(
                (res.get(k) or []) for k in ("actual_results", "simulated_results", "expected_results")
            )
            if empty_results:
                expected = (ed.get("expected_results") or "").strip()
                if expected:
                    chapters["results"] = {
                        "actual_results": [],
                        "simulated_results": [],
                        "expected_results": [expected],
                        "limitations": [
                            x.strip()
                            for x in (ed.get("limitations") or "").split("\n")
                            if x.strip()
                        ][:5],
                    }
                elif not sv:
                    chapters["results"] = {
                        "actual_results": [],
                        "simulated_results": [],
                        "expected_results": [
                            "小样验证尚未执行（可能因数据未就绪或可执行性 Gate 跳过）。"
                            "请上传至少 1 个数据集后重新运行 Pipeline，或在工作流中手动触发小样验证。"
                        ],
                        "limitations": [],
                    }

        result["chapters"] = chapters
        return result

    @staticmethod
    def _enrich_report_with_multimodal_evidence(
        result: Dict[str, Any],
        multimodal_evidence: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        chapters = result.get("chapters", {}) if isinstance(result.get("chapters"), dict) else {}
        if not multimodal_evidence:
            return result

        by_modality: Dict[str, List[Dict[str, Any]]] = {}
        for ev in multimodal_evidence:
            mod = ev.get("modality") or "unknown"
            by_modality.setdefault(mod, []).append(ev)

        rationale = chapters.get("rationale") or ""
        rationale += "\n\n### 多模态证据（上传资产）\n"
        for mod, items in by_modality.items():
            rationale += f"\n**{mod}** ({len(items)} 条):\n"
            for ev in items[:4]:
                rationale += (
                    f"- [{ev.get('fact_id', '?')}] { (ev.get('fact_text') or '')[:200]}"
                    f" (来源: {ev.get('source_file', '?')}, confidence={ev.get('confidence', '?')})\n"
                )
        chapters["rationale"] = rationale

        refs = chapters.get("references") or ""
        refs += "\n\n【多模态来源标注】\n"
        seen = set()
        for ev in multimodal_evidence[:10]:
            src = ev.get("source_file") or ev.get("source_paper_title")
            mod = ev.get("modality", "?")
            key = f"{src}:{mod}"
            if key in seen:
                continue
            seen.add(key)
            refs += f"- [{mod}] {src}\n"
        chapters["references"] = refs

        results = chapters.get("results") or {}
        if not isinstance(results, dict):
            text_note = str(results).strip()
            results = {
                "actual_results": [],
                "simulated_results": [],
                "expected_results": [text_note] if text_note else [],
                "limitations": [],
            }
        if any(ev.get("modality") == "image" for ev in multimodal_evidence):
            note = (
                "【图表数据说明】部分结论引用上传图像/VLM 解析结果；"
                "图像识别方式：Qwen-VL 或规则降级（见 multimodal metadata）。"
            )
            sim = list(results.get("simulated_results") or [])
            if note not in sim:
                sim.append(note)
            results["simulated_results"] = sim
        chapters["results"] = results
        result["chapters"] = chapters
        result["multimodal_evidence_summary"] = {
            "total": len(multimodal_evidence),
            "by_modality": {k: len(v) for k, v in by_modality.items()},
        }
        return result

    @staticmethod
    def _apply_evidence_chain_references(
        result: Dict[str, Any],
        all_hypotheses: List[Dict[str, Any]],
        verified_references: Optional[List[Dict[str, Any]]] = None,
        citation_map: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """证据链仅在书目为空/占位时回填；已有可验证 GB/T 书目时不整表覆盖。"""
        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        existing = chapters.get("references") or []
        if not isinstance(existing, list):
            existing = [existing] if existing else []
        has_real_bib = any(
            isinstance(r, str)
            and r.strip()
            and not any(
                m in r
                for m in ("证据链不足", "暂无真实文献", "禁止虚构", "缺少真实引用", "需补充文献")
            )
            for r in existing
        )
        if has_real_bib:
            return result

        allowed_dois = set()
        for item in list(verified_references or []) + list(citation_map or []):
            if not isinstance(item, dict):
                continue
            doi = str(item.get("doi") or "").strip().lower()
            if doi:
                allowed_dois.add(doi)

        refs: List[str] = []
        seen = set()
        has_chain = False

        for h in all_hypotheses or []:
            chain = h.get("evidence_chain") or {}
            if not chain:
                continue
            has_chain = True
            for ev in (chain.get("supporting_evidence") or []) + (chain.get("counter_evidence") or []):
                title = (ev.get("source_title") or "").strip()
                if not title or title.lower() in {"文献不确定点", "unknown", "placeholder"}:
                    continue
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                year = ev.get("year") or ""
                doi = str(ev.get("doi") or "").strip()
                line = title
                if year:
                    line += f" ({year})"
                # 仅附加已在 verified/citation_map 中出现的 DOI，禁止证据链凭空写入 DOI
                if doi and doi.lower() in allowed_dois:
                    line += f". DOI: {doi}"
                refs.append(line)

        if has_chain:
            if refs:
                chapters["references"] = refs
            else:
                chapters["references"] = [
                    "证据链不足，需要补充 BibTeX/PDF 文献；当前无可验证 References，禁止虚构引用"
                ]
            result["chapters"] = chapters

        return result

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
        experiment_design: Optional[Dict[str, Any]] = None,
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
                if key in ("experiments", "results"):
                    status, note = evaluate_chapter_item_status(
                        key,
                        value,
                        experiment_design=experiment_design if key == "experiments" else None,
                    )
                elif isinstance(value, str) and len(value.strip()) >= 20:
                    status = "completed"
                    note = None
                elif isinstance(value, str) and len(value.strip()) > 0:
                    status = "human_review"
                    note = "内容较短，建议补充"
                elif isinstance(value, list) and len(value) > 0:
                    status = "completed"
                    note = None
                elif isinstance(value, dict) and self._has_text(value, min_len=1):
                    status = "completed"
                    note = None
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

        from app.services.report_compliance_service import assess_result_type

        has_result, result_type = assess_result_type(chapters.get("results", ""))
        # 顶层 results 结构化字段（enrichment 写入）
        structured = result_dict.get("results") if isinstance(result_dict.get("results"), dict) else {}
        if result_type not in ("actual_result", "simulated_result") and structured:
            s_has, s_type = assess_result_type(structured)
            if s_has and s_type in ("actual_result", "simulated_result"):
                has_result, result_type = s_has, s_type

        ed = experiment_design if isinstance(experiment_design, dict) else {}
        has_datasets = bool(
            self._has_text(chapters.get("datasets"), min_len=10)
            or self._has_text(ed.get("datasets"), min_len=10)
        )
        has_source = bool(
            self._has_text(chapters.get("source"), min_len=10)
            or self._has_text(ed.get("source_data"), min_len=10)
        )
        has_target = bool(
            self._has_text(chapters.get("target"), min_len=10)
            or self._has_text(ed.get("target_data"), min_len=10)
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
        has_experiments = chapter_has_experiments(
            chapters.get("experiments"),
            experiment_design,
        )
        has_results = chapter_has_results(chapters.get("results"))
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
        if not isinstance(hr_data, dict):
            return None
        # 兼容旧结构 hypothesis_novelty_review.data.novelty_score
        direct = (hr_data.get("data") or {}).get("novelty_score")
        if direct is not None:
            try:
                return float(direct)
            except (TypeError, ValueError):
                pass
        # 现行结构：hypothesis_{i}.data.novelty_score
        scores: List[float] = []
        for key, entry in hr_data.items():
            if not str(key).startswith("hypothesis_") or not isinstance(entry, dict):
                continue
            data = entry.get("data") or {}
            score = data.get("novelty_score") or data.get("overall_novelty")
            if score is None:
                continue
            try:
                scores.append(float(score))
            except (TypeError, ValueError):
                continue
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)

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
        pipeline_run_info: Optional[Dict[str, Any]] = None,
        small_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.services.report_plot_service import (
            collect_sandbox_plots_from_validation,
            dedupe_report_plots,
            prepare_plots_for_persistence,
        )

        sandbox_plots = collect_sandbox_plots_from_validation(small_validation)
        if sandbox_plots:
            synced = prepare_plots_for_persistence(
                sandbox_plots,
                report_file_id=report_id or None,
                keep_base64=True,
            )
            charts = dedupe_report_plots(synced)
            logger.info("[报告生成] 使用沙箱/ pilot 实验图 %d 张", len(charts))
            return {
                "charts": charts,
                "skill_outputs": {
                    "report_chart_generation": {
                        "success": True,
                        "data": {"charts": charts, "total_charts": len(charts)},
                        "warnings": [],
                        "source": "sandbox_execution",
                    }
                },
            }

        # 无沙箱实验产出时，不再用 PreliminaryAnalysis 描述统计图冒充实验结果
        del preliminary_analysis_skill_outputs, multimodal_datasets
        warning = (
            "小样验证未产出沙箱实验图或指标；"
            "请先完成沙箱脚本（metrics.json + plots/*.png）或 pilot 对比分析。"
        )
        logger.warning("[报告生成] %s", warning)
        return {
            "charts": [],
            "skill_outputs": {
                "report_chart_generation": {
                    "success": True,
                    "data": {"charts": [], "total_charts": 0},
                    "warnings": [warning],
                    "source": "none",
                }
            },
        }

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

        json_file = os.path.join(report_path, "report_data.json")
        pdf_file = os.path.join(report_path, "report.pdf")
        tex_file = os.path.join(report_path, "report.tex")

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"报告文件已保存到: {report_path}")
        return {
            "report_id": report_id,
            "report_path": report_path,
            "json_file": json_file,
            "tex_file": tex_file,
            "pdf_file": pdf_file,
            "pdf_success": False,
        }

    @staticmethod
    def _write_report_json(result: Dict[str, Any]) -> None:
        json_file = result.get("json_file", "")
        if not json_file:
            return
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"更新 JSON 报告失败: {e}")

    def _export_report_pdf(
        self,
        result: Dict[str, Any],
        project_info: Dict[str, Any],
        citation_map: List[Dict[str, Any]],
        verified_references: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        report_path = result.get("report_path", "")
        if not report_path:
            return {
                "pdf_success": False,
                "warning": "缺少 report_path，无法导出 PDF",
            }

        export_result = export_report_via_latex(
            result=result,
            output_dir=report_path,
            project_info=project_info,
            citation_map=citation_map,
            verified_references=verified_references,
        )

        info = {
            "latex_content": export_result.get("latex_content", ""),
            "tex_file": export_result.get("tex_file"),
            "bib_file": export_result.get("bib_file"),
            "pdf_file": export_result.get("pdf_path") or result.get("pdf_file"),
            "pdf_success": export_result.get("pdf_success", False),
            "export_method": export_result.get("export_method"),
            "warning": export_result.get("warning"),
        }
        if export_result.get("pdf_success"):
            logger.info(
                f"报告 PDF 已生成 (method={info.get('export_method')}, path={info.get('pdf_file')})"
            )
        else:
            logger.warning(f"报告 PDF 生成失败: {info.get('warning')}")
        return info

    @staticmethod
    def _backfill_chapters_from_experiment(
        result: Dict[str, Any],
        experiment_design: Optional[Dict[str, Any]],
        small_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """章节为空时，用实验设计/数据绑定信息回填，避免合规误报。"""
        from app.services.report_content_sanitizer import method_boundary_note

        ed = experiment_design if isinstance(experiment_design, dict) else {}
        chapters = result.get("chapters") if isinstance(result.get("chapters"), dict) else {}
        chapters = dict(chapters)

        def _empty(key: str) -> bool:
            val = chapters.get(key)
            if val is None:
                return True
            if isinstance(val, str):
                return len(val.strip()) < 10
            if isinstance(val, (list, dict)):
                return len(val) == 0
            return False

        if _empty("datasets") and ed.get("datasets"):
            chapters["datasets"] = str(ed.get("datasets")).strip()
        if _empty("source") and ed.get("source_data"):
            chapters["source"] = str(ed.get("source_data")).strip()
        if _empty("target") and ed.get("target_data"):
            chapters["target"] = str(ed.get("target_data")).strip()

        boundary = str(ed.get("method_boundary") or "").strip() or method_boundary_note(
            small_validation, ed
        )
        for key in ("methods", "experiments"):
            val = chapters.get(key)
            text = ""
            if isinstance(val, str):
                text = val
            elif isinstance(val, dict):
                text = "\n".join(f"{k}: {v}" for k, v in val.items() if v)
            if boundary and "验证边界" not in text and "代理实验" not in text:
                if _empty(key):
                    chapters[key] = f"【验证边界】{boundary}"
                elif isinstance(val, str):
                    chapters[key] = f"{val.rstrip()}\n\n【验证边界】{boundary}"
                elif isinstance(val, dict):
                    chapters[key] = {**val, "method_boundary": boundary}

        result["chapters"] = chapters
        return result

    @staticmethod
    def _build_paper_style_discussion(
        *,
        hypothesis: str,
        metrics: Dict[str, Any],
        plots: List[Any],
        successful_iters: List[Dict[str, Any]],
        failed_iters: List[Dict[str, Any]],
        progress: Dict[str, Any],
        partial_run: bool,
        modeling_result: Optional[Dict[str, Any]],
        actual_summary: str,
        existing_results: Any,
        small_validation: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于已有实验证据生成论文风格的「结果分析与讨论」（不编造数值）。"""
        from app.services.report_content_sanitizer import (
            clean_iteration_summary,
            evidence_flags_from_small_validation,
            filter_report_metrics,
            format_metric_label,
            humanize_error_message,
        )

        lines: List[str] = ["### 结果分析与讨论\n"]
        sv = small_validation if isinstance(small_validation, dict) else {}
        narr = sv.get("iteration_narrative") if isinstance(sv.get("iteration_narrative"), dict) else {}
        brief = sv.get("narrative_brief") if isinstance(sv.get("narrative_brief"), dict) else {}
        verdict = str(
            (narr or {}).get("evidence_verdict")
            or (brief or {}).get("evidence_verdict")
            or ""
        ).strip()

        # 优先嵌入叙事 skill 的 story_arc
        story = str((narr or {}).get("story_arc") or "").strip()
        if story:
            lines.append("**迭代演化叙事。** ")
            lines.append(story + "\n")
        neg_para = str((narr or {}).get("negative_or_partial_results_paragraph") or "").strip()
        if neg_para:
            lines.append("**阶段性/负向证据定位。** ")
            lines.append(neg_para + "\n")

        hyp = (hypothesis or "").strip()
        filtered = filter_report_metrics(metrics if isinstance(metrics, dict) else {})
        metric_items = list(filtered.items())[:10]
        plot_n = len(plots) if isinstance(plots, list) else 0
        flags = evidence_flags_from_small_validation(
            sv
            if sv
            else {
                "sandbox_execution": {
                    "partial_run": partial_run,
                    "metrics": metrics,
                    "iteration_progress": progress,
                },
                "results": {
                    "actual_results": {
                        "failed_iterations": failed_iters,
                        "summary": actual_summary,
                    }
                },
            }
        )
        if verdict:
            flags = {**flags, "evidence_verdict": verdict}
        findings: List[str] = []
        for r in successful_iters[:6]:
            if not isinstance(r, dict):
                continue
            for f in (r.get("findings") or [])[:3]:
                if f and str(f).strip():
                    findings.append(clean_iteration_summary(f))
            summ = clean_iteration_summary(r.get("summary") or "")
            if summ:
                findings.append(summ[:220])
        # 去重保序
        seen_f: set[str] = set()
        uniq_findings: List[str] = []
        for f in findings:
            if f not in seen_f:
                seen_f.add(f)
                uniq_findings.append(f)
        findings = uniq_findings[:8]

        # —— 主要发现 ——
        lines.append("**主要发现。** ")
        if flags.get("trivial_solution"):
            lines.append(
                "观测到准确率接近满分且基线与主模型同量级（或特征重要性近零），"
                "提示可能存在平凡解、标签泄漏或无效分裂，不宜解读为强支持证据。"
            )
        elif flags.get("poor_performance"):
            lines.append(
                "分类主指标处于偏低水平（如准确率/F1显著低于可用阈值），"
                "且诊断图提示类别可分性不足；结果应解读为方法边界与协议需修正，"
                "而非对假设的正向支持。"
            )
        elif flags.get("negative_fit"):
            lines.append(
                "拟合指标（如决定系数）为负或未达可用水平，表明当前协议下模型解释力不足。"
            )
        if metric_items or plot_n or findings:
            parts = []
            if metric_items:
                metric_txt = "；".join(f"{format_metric_label(k)}={v}" for k, v in metric_items[:6])
                parts.append(f"已观测到关键指标（{metric_txt}）")
            if plot_n:
                parts.append(f"并形成 {plot_n} 张实验图供对照")
            if findings:
                # 截断到完整句，避免 n_test_samples= 半截
                cleaned_f = []
                for f in findings[:4]:
                    ff = str(f).strip()
                    ff = re.sub(r"(显著高于|显著优于)", "高于", ff)
                    ff = re.sub(r"验证了([^，。；]{0,40}优势)", r"提示了\1（尚待独立复验）", ff)
                    # 去掉不完整的尾部键值
                    ff = re.sub(r"[|；]\s*[A-Za-z0-9_]+=\s*$", "", ff)
                    ff = re.sub(r"[|；]\s*数据:.*$", "", ff)
                    if len(ff) > 280:
                        cut = ff[:280]
                        sp = max(cut.rfind("。"), cut.rfind("；"), cut.rfind(";"))
                        ff = cut[: sp + 1] if sp > 80 else cut.rstrip("，,;；") + "…"
                    cleaned_f.append(ff)
                parts.append("迭代分析指出：" + "；".join(cleaned_f))
            lines.append("".join(parts) + "。")
            lines.append(
                "上述结果来自已执行轮次的记录，用于说明当前设置下的可观测行为，"
                "而非对总体分布的统计推断。\n"
            )
        elif failed_iters:
            lines.append(
                "本阶段尚未形成稳定的正向指标，但失败轮次提供了可复核的负向证据，"
                "有助于界定方法边界。\n"
            )
        else:
            lines.append("当前缺少可引用的实测指标或图表，本节仅能作方法可行性层面的讨论。\n")

        # —— 与假设对照 ——
        lines.append("\n**与科学假设的对照。** ")
        if hyp:
            lines.append(f"目标假设可概括为：「{hyp[:280]}」。")
        else:
            lines.append("报告输入中未给出完整假设文本。")
        lines.append(
            "需注意：本节多为可执行代理实验（如表格学习），用于检验可操作推论，"
            "并不等同于对领域终极问题的完整证明。"
        )
        if flags.get("trivial_solution") or flags.get("negative_fit") or flags.get("poor_performance"):
            lines.append(
                "结合否定性/平凡性或低性能信号，当前更宜将结果解读为方法边界提示或协议需修正，"
                "而非假设已被证实。"
            )
        elif metric_items and not failed_iters:
            lines.append(
                "现有正向指标与实验图表明，在当前数据与协议下假设具有一定可检验性；"
                "但尚不足以在未声明显著性检验的前提下宣称假设已被证实或证伪。"
            )
        elif metric_items and failed_iters:
            lines.append(
                "同时存在正向观测与失败轮次：说明假设在部分条件下可被探测，"
                "但验证管线或数据设定仍不稳定，结论应限定为阶段性支持而非最终确认。"
            )
        elif failed_iters and not metric_items:
            lines.append(
                "以失败轮次为主的证据更支持如下解读：在现行方法/数据配置下，"
                "假设难以被可靠验证，或该方法对该假设不适用；宜调整协议、特征或评价口径后再验。"
            )
        else:
            lines.append("因实测证据不足，暂不能对假设给出支持或否定判断。")
        lines.append("\n")

        # —— 反例含义 ——
        if failed_iters:
            lines.append("\n**失败轮次与反例含义。** ")
            detail_bits = []
            for r in failed_iters[:5]:
                if not isinstance(r, dict):
                    continue
                n = r.get("iteration_number", "?")
                err = humanize_error_message(r.get("error_message") or "")
                issues = r.get("identified_issues") or r.get("weaknesses") or []
                issue_txt = "；".join(str(x) for x in issues[:3]) if isinstance(issues, list) else ""
                bit = f"第{n}轮"
                if err:
                    bit += f"出现「{err[:160]}」"
                if issue_txt:
                    bit += f"（问题：{issue_txt[:160]}）"
                detail_bits.append(bit)
            if detail_bits:
                lines.append("具体而言，" + "；".join(detail_bits) + "。")
            lines.append(
                "将这些失败如实写入，相当于论文中的 negative result / failure case："
                "它们约束了方法的适用范围，避免把偶然成功外推为一般结论。\n"
            )

        # —— 建模结果（若有）——
        if modeling_result and isinstance(modeling_result, dict):
            lines.append("\n**建模评估的含义。** ")
            lines.append(
                f"任务类型为 {modeling_result.get('task_type', 'unknown')}，"
                f"目标变量为 {modeling_result.get('target_column', '-')}，"
                f"相对较优模型为 {modeling_result.get('best_model', '-')}。"
            )
            if modeling_result.get("is_pilot_validation"):
                lines.append("该评估属 pilot validation，只宜作为可行性旁证。")
            lines.append("\n")

        # —— 局限与后续 ——
        lines.append("\n**局限与后续工作。** ")
        lims = []
        if flags.get("smoke"):
            lims.append("当前为 smoke/小样本可行性验证，证据层级较弱")
        if partial_run:
            cur = progress.get("current_iteration")
            mx = progress.get("max_iterations")
            ran = progress.get("ran_rounds")
            n_ok = len(successful_iters) if isinstance(successful_iters, list) else 0
            shown = ran or (n_ok if n_ok > 0 else cur)
            lims.append(
                f"实验未跑满计划轮次（约 {shown or '?'}/{mx or '?'}），结论仅为阶段性结果"
            )
        if failed_iters:
            lims.append("存在执行失败或协议不匹配，需先修复数据/脚本再谈效应量")
        if flags.get("trivial_solution"):
            lims.append("存在平凡解风险，需检查标签分布、特征泄漏与评价口径")
        if flags.get("poor_performance"):
            lims.append("主分类指标偏低，动态与固定策略差异有限，尚不足以支持效率/稳定性提升主张")
        if not metric_items:
            lims.append("正向定量指标不足，尚难给出可重复的效应描述")
        if plot_n == 0:
            lims.append("缺少可复核实验图时，读者难以独立核对趋势")
        if not lims:
            lims.append("样本与协议覆盖范围仍有限，外推需谨慎")
        lines.append("；".join(lims) + "。")
        next_exps = (narr or {}).get("next_experiments") if isinstance(narr, dict) else None
        if isinstance(next_exps, list) and next_exps:
            clean_next = []
            for x in next_exps[:4]:
                s = clean_iteration_summary(str(x).strip())
                s = s.replace("['", "").replace("']", "").replace("', '", "；")
                s = re.sub(r"[；;]{2,}", "；", s).strip("；;，, ")
                if len(s) < 12:
                    continue
                if s:
                    clean_next.append(s[:180])
            if clean_next:
                lines.append("后续可检验步骤：" + "；".join(clean_next) + "。")
            else:
                lines.append(
                    "后续建议：（1）在固定协议下补齐关键轮次与对照；（2）对失败根因做消融或诊断实验；"
                    "（3）明确主指标、不确定性与可重复脚本，再形成更强的支持/否定结论。"
                )
        else:
            lines.append(
                "后续建议：（1）在固定协议下补齐关键轮次与对照；（2）对失败根因做消融或诊断实验；"
                "（3）明确主指标、不确定性与可重复脚本，再形成更强的支持/否定结论。"
            )
        # 边界声明：若讨论前文或 methods 已出现则不再重复粘贴
        boundary_n = str((narr or {}).get("method_boundary") or "").strip()
        already_has_boundary = any(
            "最小代理实验" in (ln or "") or "验证边界" in (ln or "") for ln in lines
        )
        if boundary_n and not already_has_boundary:
            lines.append(boundary_n)
        lines.append("\n")

        cleaned_summary = clean_iteration_summary(actual_summary)
        if cleaned_summary:
            lines.append(f"\n> 实验侧摘要：{cleaned_summary[:400]}\n")

        # 若 LLM 原文已含讨论段落，摘出作为补充论述（避免丢弃）
        if isinstance(existing_results, str) and "结果分析与讨论" in existing_results:
            idx = existing_results.find("结果分析与讨论")
            tail = existing_results[idx: idx + 1200].strip()
            if len(tail) > 60:
                lines.append("\n**模型生成的补充论述（需与上文实测对齐）。**\n\n")
                lines.append(tail[:800] + ("…\n" if len(tail) > 800 else "\n"))

        text = "\n".join(lines) + "\n"
        # 否定/不确定证据下剔除过度正面措辞
        if verdict in {"contradicted", "inconclusive", "blocked"} or (
            flags.get("has_failures") and not metric_items
        ):
            try:
                from app.skills.report.iteration_narrative_skill import IterationNarrativeSkill

                text = IterationNarrativeSkill.strip_overclaim(text, verdict or "inconclusive")
            except Exception:
                logger.warning("过度声明剥离失败 verdict=%s", verdict, exc_info=True)
        try:
            from app.services.report_content_sanitizer import (
                collapse_method_boundary_duplicates,
                dedupe_repeated_sentences,
            )

            text = collapse_method_boundary_duplicates(dedupe_repeated_sentences(text))
        except Exception:
            logger.warning("results 章节去重净化失败", exc_info=True)
        return text

    @staticmethod
    def _enrich_results_with_categorized(
        result: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]],
        preliminary_analysis_skill_outputs: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sv = dict(small_validation or {})
        if sv and not isinstance(sv.get("iteration_narrative"), dict):
            try:
                from app.skills.report.iteration_narrative_skill import IterationNarrativeSkill

                sv["iteration_narrative"] = IterationNarrativeSkill.build_narrative(
                    small_validation=sv,
                    hypothesis=str(sv.get("hypothesis") or ""),
                )
            except Exception:
                logger.warning("iteration narrative 构建失败", exc_info=True)
        sv_results = sv.get("results", {}) if isinstance(sv.get("results"), dict) else {}
        # 兼容：sandbox_execution 在 sv 顶层（迭代实验 synthesize）
        top_sandbox = sv.get("sandbox_execution") if isinstance(sv.get("sandbox_execution"), dict) else {}

        if not sv_results and not top_sandbox and not (sv.get("artifacts") or {}).get("plots"):
            return result

        pa_so = preliminary_analysis_skill_outputs or {}
        pa_data = pa_so.get("preliminary_analysis", {}).get("data", {})
        _ = pa_data  # 保留参数供后续扩展

        actual = sv_results.get("actual_results", {})
        if not isinstance(actual, dict):
            actual = {}
        sandbox_exec = actual.get("sandbox_execution") or top_sandbox or {}
        if not isinstance(sandbox_exec, dict):
            sandbox_exec = {}
        metrics = (
            sandbox_exec.get("metrics")
            or actual.get("sandbox_metrics")
            or (sv.get("artifacts") or {}).get("metrics")
            or {}
        )
        from app.services.report_content_sanitizer import (
            clean_iteration_summary,
            filter_report_metrics,
            format_metric_label,
            humanize_error_message,
        )

        metrics = filter_report_metrics(metrics if isinstance(metrics, dict) else {})
        plots = (
            sandbox_exec.get("plots")
            or actual.get("sandbox_plots")
            or (sv.get("artifacts") or {}).get("plots")
            or []
        )
        sandbox_success = bool(
            sandbox_exec.get("success")
            or (isinstance(metrics, dict) and metrics)
            or (isinstance(plots, list) and plots)
        )
        failed_iters = (
            actual.get("failed_iterations")
            or actual.get("counterexamples")
            or (actual.get("iteration_evidence") or {}).get("failed_rounds")
            or []
        )
        if not isinstance(failed_iters, list):
            failed_iters = []
        successful_iters = actual.get("successful_iterations") or (
            (actual.get("iteration_evidence") or {}).get("successful_rounds") or []
        )
        if not isinstance(successful_iters, list):
            successful_iters = []
        progress = (
            sandbox_exec.get("iteration_progress")
            or (actual.get("iteration_evidence") or {}).get("progress")
            or {}
        )
        has_negative = bool(failed_iters)
        has_usable_evidence = sandbox_success or has_negative or bool(successful_iters)
        partial_run = bool(
            sandbox_exec.get("partial_run")
            or sandbox_exec.get("sandbox_incomplete")
            or (progress and not progress.get("completed_full_plan"))
        )

        if sandbox_success and "sandbox_execution" not in actual:
            actual = {
                **actual,
                "sandbox_execution": {
                    **sandbox_exec,
                    "success": True,
                    "metrics": metrics if isinstance(metrics, dict) else {},
                    "plots": plots if isinstance(plots, list) else [],
                },
                "sandbox_metrics": metrics if isinstance(metrics, dict) else {},
                "sandbox_plots": plots if isinstance(plots, list) else [],
                "data_source": actual.get("data_source") or "sandbox_execution",
            }

        if has_usable_evidence:
            result_type_summary = (
                "has_actual_results"
                if sandbox_success
                else ("has_negative_evidence" if has_negative else sv_results.get("result_type_summary", "none"))
            )
        else:
            result_type_summary = sv_results.get("result_type_summary", "none")

        result["results"] = {
            "actual_results": actual,
            "simulated_results": sv_results.get("simulated_results", {}),
            "expected_results": sv_results.get("expected_results", {}),
            "result_type_summary": result_type_summary,
            "warnings": sv_results.get("warnings", []),
        }

        chapters = result.get("chapters", {})
        if not isinstance(chapters, dict):
            return result

        existing_results = chapters.get("results", "")
        modeling_result = actual.get("modeling_result")
        has_modeling = isinstance(modeling_result, dict) and bool(modeling_result)
        has_summary_stats = bool(actual.get("summary_statistics"))
        simulated = sv_results.get("simulated_results", {})
        has_simulated = (
            not sandbox_success
            and not has_negative
            and isinstance(simulated, dict)
            and bool(simulated.get("data"))
        )
        # 无实测/建模/模拟时不写空的 Actual Results 小节，保留 LLM 的 Expected Results
        if not (has_usable_evidence or has_modeling or has_summary_stats or has_simulated):
            from app.services.report_content_sanitizer import strip_empty_actual_results_section

            if isinstance(existing_results, str):
                chapters["results"] = strip_empty_actual_results_section(existing_results)
            elif isinstance(existing_results, dict):
                actual_payload = existing_results.get("actual_results")
                if actual_payload in (None, "", [], {}):
                    existing_results = {
                        k: v for k, v in existing_results.items() if k != "actual_results"
                    }
                    chapters["results"] = existing_results
            result["chapters"] = chapters
            return result

        enriched = ""
        # 仅在确有可写入内容时输出实际分析结果（未跑满轮次也可）
        if has_usable_evidence or has_modeling or has_summary_stats:
            enriched += "### 实际分析结果\n\n"

            if partial_run and (sandbox_success or has_negative or successful_iters):
                cur = progress.get("current_iteration")
                mx = progress.get("max_iterations")
                ran = progress.get("ran_rounds")
                n_ok = len(successful_iters) if isinstance(successful_iters, list) else 0
                shown = ran or (n_ok if n_ok > 0 else cur)
                if shown is not None or mx is not None:
                    enriched += (
                        f"> **阶段性结果**：实验计划 {mx or '?'} 轮，当前已完成约 {shown or '?'} 轮；"
                        "以下基于已完成轮次，不要求跑满全部轮次即可写入报告。\n\n"
                    )

            if sandbox_success:
                enriched += "### 初步实验验证\n\n"
                enriched += "- 执行状态: 成功（含部分成功轮次）\n" if partial_run else "- 执行状态: 成功\n"
                if sandbox_exec.get("duration_ms"):
                    enriched += f"- 耗时: {sandbox_exec.get('duration_ms')} ms\n"
                if isinstance(metrics, dict) and metrics:
                    enriched += "- 实测指标:\n"
                    skip_keys = {"overall_score", "overall score", "run_scope", "run_mode"}
                    for k, v in list(metrics.items())[:16]:
                        if str(k).lower().replace(" ", "_") in skip_keys or str(k) in skip_keys:
                            continue
                        if v is None or v == "":
                            continue
                        enriched += f"  - {format_metric_label(k)}: {v}\n"
                if isinstance(plots, list) and plots:
                    enriched += f"- 实验图表: {len(plots)} 张\n"
                    enriched += "\n#### 图题与核心读图要点\n\n"
                    for i, pl in enumerate(plots[:6], 1):
                        if not isinstance(pl, dict):
                            continue
                        title = str(pl.get("title") or pl.get("plot_id") or f"图{i}").strip()
                        kind = str(pl.get("chart_kind") or "").strip()
                        note = ""
                        if "混淆" in title or "confusion" in title.lower():
                            note = "关注对角线强度及有利/不利类别是否可分。"
                        elif "阶段" in title or "phase" in title.lower() or "前半" in title:
                            note = "对比任务前/后半段准确率，检验长期策略建模是否成立。"
                        elif "对比" in title or "comparison" in title.lower() or "柱" in title:
                            note = "对照主模型与基线的准确率/F1差距及其方向。"
                        elif kind == "diagnostic_counterexample":
                            note = "失败/反例诊断图，仅用于界定方法边界，不作成功证据。"
                        else:
                            note = "结合对应指标解读趋势，勿脱离数值单独外推。"
                        enriched += f"{i}. **{title}** — {note}\n"
                enriched += "\n"
                enriched += "> 以下结果以迭代实验验证为准；模拟/预期结果仅作参考。\n\n"
            elif successful_iters and not sandbox_success:
                enriched += "### 初步实验验证\n\n"
                enriched += f"- 已记录成功/部分轮次: {len(successful_iters)} 轮\n"
                for r in successful_iters[:5]:
                    if not isinstance(r, dict):
                        continue
                    enriched += (
                        f"- 第 {r.get('iteration_number', '?')} 轮"
                        f"（{r.get('status', 'partial')}）"
                    )
                    summ = clean_iteration_summary(r.get("summary") or "")
                    if summ:
                        enriched += f": {summ[:200]}"
                    enriched += "\n"
                enriched += "\n"

            if has_negative:
                enriched += "### 失败轮次与反例证据\n\n"
                enriched += (
                    "以下轮次未成功或未达成功标准，可作为「当前方法难以充分验证该假设」的反例；"
                    "应如实写局限，勿编造成功指标。\n\n"
                )
                for r in failed_iters[:8]:
                    if not isinstance(r, dict):
                        continue
                    n = r.get("iteration_number", "?")
                    enriched += f"- **第 {n} 轮**（{r.get('status') or 'failed'}）\n"
                    err = humanize_error_message(r.get("error_message") or "")
                    if err:
                        enriched += f"  - 错误/失败信息: {err[:400]}\n"
                    summ = clean_iteration_summary(
                        r.get("summary") or r.get("overall_assessment") or ""
                    )
                    if summ:
                        enriched += f"  - 分析摘要: {summ[:300]}\n"
                    issues = r.get("identified_issues") or r.get("weaknesses") or []
                    if isinstance(issues, list) and issues:
                        enriched += f"  - 问题: {'; '.join(str(x) for x in issues[:4])}\n"
                    if r.get("chart_count"):
                        enriched += f"  - 关联图表: {r.get('chart_count')} 张\n"
                note = (actual.get("iteration_evidence") or {}).get("counterexample_note") or ""
                if note:
                    enriched += f"\n> {note}\n\n"
                else:
                    enriched += "\n"

            if has_modeling:
                enriched += "### 数据建模评估\n\n"
                if modeling_result.get("is_pilot_validation") or actual.get("validation_scope") == "pilot_validation":
                    enriched += "> **小样本可行性验证**：样本量较小，本节结果仅用于可行性验证，不得夸大为最终结论。\n\n"
                enriched += f"- 任务类型: {modeling_result.get('task_type', 'unknown')}\n"
                enriched += f"- 目标变量: {modeling_result.get('target_column', '-')}\n"
                enriched += f"- 最佳模型: {modeling_result.get('best_model', '-')}\n"
                best_metrics = {}
                for model in modeling_result.get("models", []):
                    if model.get("model_name") == modeling_result.get("best_model"):
                        best_metrics = model.get("metrics", {})
                        break
                if best_metrics:
                    enriched += "- 最佳模型指标:\n"
                    for key, val in best_metrics.items():
                        if key == "confusion_matrix":
                            continue
                        enriched += f"  - {format_metric_label(key)}: {val}\n"
                enriched += "\n"

            if not sandbox_success and not has_negative and has_summary_stats:
                enriched += "- 基于真实数据的统计分析已完成\n"
                enriched += f"- 分析数据源数量: {actual.get('n_datasets_analyzed', 0)}\n"
                enriched += f"- 数据来源: {actual.get('data_source', 'unknown')}\n\n"

        if has_simulated:
            enriched += "### 模拟结果\n\n"
            enriched += "- 模拟数据已生成\n"
            enriched += f"- 说明: {simulated.get('note', '基于假设参数的模拟数据')}\n\n"

        # 论文式结果分析与讨论（仅在有实测/建模时；基于已注入证据，不编造数值）
        if has_usable_evidence or has_modeling:
            discussion_md = ReportGenerationAgent._build_paper_style_discussion(
                hypothesis=str(sv.get("hypothesis") or actual.get("hypothesis") or ""),
                metrics=metrics if isinstance(metrics, dict) else {},
                plots=plots if isinstance(plots, list) else [],
                successful_iters=successful_iters,
                failed_iters=failed_iters,
                progress=progress if isinstance(progress, dict) else {},
                partial_run=partial_run,
                modeling_result=modeling_result if isinstance(modeling_result, dict) else None,
                actual_summary=str(actual.get("summary") or ""),
                existing_results=existing_results,
                small_validation=sv,
            )
            enriched += discussion_md
            if isinstance(result.get("results"), dict):
                result["results"]["discussion"] = discussion_md

        # 保留 LLM 原文作为补充（若非空且不是纯占位；已含讨论标题则不再整段重复）
        if isinstance(existing_results, str) and len(existing_results.strip()) >= 40:
            if (
                "Experiment Run" not in existing_results
                and "初步实验验证" not in existing_results
                and "实测指标" not in existing_results
                and "结果分析与讨论" not in existing_results
            ):
                enriched += "### 报告叙述补充\n\n"
                enriched += existing_results.strip() + "\n"

        chapters["results"] = enriched
        result["chapters"] = chapters
        return result


_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance