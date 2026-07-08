"""
报告质量检查 Skill
参考能力：挑战杯 XH-202619 赛题规范
对最终 report_data.json 做赛题规范检查，输出评分和修正建议。
"""
import logging
import re
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

from app.core.report_fields import REPORT_SECTION_FIELDS

CHECK_FIELDS = REPORT_SECTION_FIELDS

Qwen_KEYWORDS = [
    re.compile(r"千问", re.IGNORECASE),
    re.compile(r"Qwen", re.IGNORECASE),
    re.compile(r"通义千问", re.IGNORECASE),
    re.compile(r"阿里云百炼", re.IGNORECASE),
    re.compile(r"bailian", re.IGNORECASE),
]

NON_QWEN_MODEL_PATTERNS = [
    re.compile(r"\bGPT-?4\b", re.IGNORECASE),
    re.compile(r"\bGPT-?3\.?5\b", re.IGNORECASE),
    re.compile(r"\bGPT-?o\b", re.IGNORECASE),
    re.compile(r"\bChatGPT\b", re.IGNORECASE),
    re.compile(r"\bClaude\b", re.IGNORECASE),
    re.compile(r"\bAnthropic\b", re.IGNORECASE),
    re.compile(r"\bGemini\b", re.IGNORECASE),
    re.compile(r"\bLlama\b", re.IGNORECASE),
    re.compile(r"\bLLaMA\b", re.IGNORECASE),
    re.compile(r"\bMistral\b", re.IGNORECASE),
    re.compile(r"\bPaLM\b", re.IGNORECASE),
    re.compile(r"\bFalcon\b", re.IGNORECASE),
]

UNKNOWN_AUTHOR_PATTERNS = [
    re.compile(r"unknown\s*(author|researcher|creator)", re.IGNORECASE),
    re.compile(r"未知作者", re.IGNORECASE),
    re.compile(r"anonymous", re.IGNORECASE),
    re.compile(r"anon\.", re.IGNORECASE),
]

PLACEHOLDER_PATTERNS = [
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"TBD", re.IGNORECASE),
    re.compile(r"to\s+be\s+(determined|added|filled)", re.IGNORECASE),
    re.compile(r"待(补充|填|定|加)", re.IGNORECASE),
]

LLM_FABRICATION_PATTERNS = [
    re.compile(r"\bViT\s+(Paper|Model|论文)\b", re.IGNORECASE),
    re.compile(r"\bCross-modal\s+(Paper|Model|论文)\b", re.IGNORECASE),
    re.compile(r"\bLLM\s*(自造|生成|hallucinat)", re.IGNORECASE),
]

FAKE_DATASET_PATTERNS = [
    re.compile(r"示例数据", re.IGNORECASE),
    re.compile(r"随机生成", re.IGNORECASE),
    re.compile(r"模拟数据", re.IGNORECASE),
    re.compile(r"dummy\s+data", re.IGNORECASE),
    re.compile(r"synthetic\s+data", re.IGNORECASE),
    re.compile(r"fabricated\s+data", re.IGNORECASE),
]


class ReportQualityCheckSkill(BaseSkill):
    """报告质量检查 Skill

    输入:
      - report_data: dict                 报告数据
      - references_verified: int          已验证引用数
      - has_real_data_plots: bool         是否有真实数据图表
      - plots: List[dict]                 图表列表（可选）
      - citation_grounding_output: dict   CitationGroundingSkill 输出

    输出 (SkillResult.data):
      - score: int                        评分 0-100
      - passed: bool                      是否通过
      - missing_fields: List[str]         缺失字段
      - warnings: List[str]               警告
      - critical_issues: List[str]        关键问题
      - recommendations: List[str]        建议
      - references_verified: int          已验证引用数
      - has_real_data_plots: bool         是否有真实数据图表
      - has_actual_or_simulated_results: bool  是否有实际或模拟结果
    """

    name = "ReportQualityCheck"
    description = "对报告数据做赛题规范检查，输出评分和修正建议"
    source_reference = "挑战杯 XH-202619 赛题规范"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        report_data = input_data.get("report_data", {})
        if not report_data:
            chapters = input_data.get("chapters", {})
            report_data = {
                "paper_title": input_data.get("paper_title", ""),
                "paper_abstract": input_data.get("paper_abstract", ""),
                "chapters": chapters,
            }

        references_verified = input_data.get("references_verified", 0)
        has_real_data_plots = input_data.get("has_real_data_plots", False)
        plots = input_data.get("plots", [])
        citation_output = input_data.get("citation_grounding_output", {})

        if isinstance(citation_output, dict):
            cg_data = citation_output.get("citation_grounding", {})
            if isinstance(cg_data, dict) and cg_data.get("data"):
                inner = cg_data["data"]
                if isinstance(inner.get("references_verified"), (int, float)):
                    references_verified = inner["references_verified"]

        chapters = report_data.get("chapters", {})
        has_actual_or_simulated = self._check_results_structure(chapters)

        missing_fields: List[str] = []
        warnings: List[str] = []
        critical_issues: List[str] = []
        recommendations: List[str] = []
        completed_fields = 0

        plots_with_source = 0
        plots_generated_from_real = 0
        plots_missing_source = []
        if isinstance(plots, list):
            for i, p in enumerate(plots):
                if isinstance(p, dict):
                    sid = p.get("source_dataset_id")
                    if sid:
                        plots_with_source += 1
                    else:
                        plots_missing_source.append(i)
                    if p.get("is_generated_from_real_data"):
                        plots_generated_from_real += 1
            if plots_missing_source:
                warnings.append(
                    f"plots 中有 {len(plots_missing_source)} 个缺少 source_dataset_id "
                    f"(索引: {plots_missing_source[:3]}{'...' if len(plots_missing_source) > 3 else ''})"
                )
            if plots_generated_from_real == 0 and len(plots) > 0:
                warnings.append(
                    "所有 plots 的 is_generated_from_real_data 均为 false，"
                    "建议基于真实数据生成图表"
                )
        if plots_generated_from_real > 0:
            has_real_data_plots = True

        for key, label in CHECK_FIELDS:
            value = self._extract_field_value(report_data, chapters, key)
            has_content = False

            if key == "references":
                if isinstance(value, list) and len(value) > 0:
                    has_real = any(
                        r and r != "暂无真实文献引用，需补充文献库" and not str(r).startswith("[待")
                        for r in value
                    )
                    if has_real:
                        completed_fields += 1
                        has_content = True
                        self._check_reference_quality(value, warnings, critical_issues)
                    else:
                        missing_fields.append(label)
                        critical_issues.append("References 缺失或无效，不符合赛题要求")
                else:
                    missing_fields.append(label)
                    critical_issues.append("References 缺失或无效，不符合赛题要求")
            elif key == "datasets":
                if isinstance(value, list) and len(value) > 0:
                    completed_fields += 1
                    has_content = True
                    self._check_datasets_structured(value, warnings, critical_issues)
                elif isinstance(value, str) and len(value.strip()) >= 20:
                    completed_fields += 1
                    has_content = True
                    self._check_datasets(value, warnings, critical_issues)
                else:
                    missing_fields.append(label)
            elif key == "source":
                if isinstance(value, list) and len(value) > 0:
                    completed_fields += 1
                    has_content = True
                elif isinstance(value, str) and len(value.strip()) >= 20:
                    completed_fields += 1
                    has_content = True
                else:
                    missing_fields.append(label)
            elif key == "target":
                if isinstance(value, dict) and len(value) > 0:
                    completed_fields += 1
                    has_content = True
                elif isinstance(value, str) and len(value.strip()) >= 20:
                    completed_fields += 1
                    has_content = True
                else:
                    missing_fields.append(label)
            elif key == "experiments":
                if isinstance(value, dict):
                    sub_fields = ["baselines", "metrics", "experimental_setup", "validation_protocol"]
                    sub_count = sum(1 for sf in sub_fields if value.get(sf))
                    if sub_count >= 2:
                        completed_fields += 1
                        has_content = True
                    elif isinstance(value.get("experimental_setup"), str) and len(value.get("experimental_setup", "").strip()) >= 20:
                        completed_fields += 1
                        has_content = True
                    else:
                        missing_fields.append(label)
                elif isinstance(value, str) and len(value.strip()) >= 20:
                    completed_fields += 1
                    has_content = True
                else:
                    missing_fields.append(label)
            elif key == "results":
                from app.services.report_compliance_service import assess_results_chapter

                merged = value
                if assess_results_chapter(merged) == "none":
                    merged = report_data.get("results") or chapters.get("results")
                level = assess_results_chapter(merged)
                if level == "complete":
                    completed_fields += 1
                    has_content = True
                elif level == "partial":
                    completed_fields += 1
                    has_content = True
                elif isinstance(merged, str) and len(merged.strip()) >= 20:
                    completed_fields += 1
                    has_content = True
                elif isinstance(merged, str) and len(merged.strip()) > 0:
                    warnings.append(f"{label} 内容较短，建议补充（当前 {len(merged.strip())} 字符）")
                else:
                    missing_fields.append(label)
            elif isinstance(value, str) and len(value.strip()) >= 20:
                completed_fields += 1
                has_content = True
            elif isinstance(value, str) and len(value.strip()) > 0:
                warnings.append(f"{label} 内容较短，建议补充（当前 {len(value.strip())} 字符）")
            else:
                missing_fields.append(label)

            if has_content:
                if key == "results":
                    self._check_results_field(value, chapters, warnings, critical_issues)

        self._check_unknown_patterns(report_data, chapters, warnings, critical_issues)
        self._check_non_qwen_models(report_data, chapters, critical_issues)

        if references_verified == 0:
            critical_issues.append("参考文献未验证，不符合赛题要求。请先导入 arXiv/BibTeX/PDF 文献。")
            recommendations.append("先导入文献库再生成报告，确保 References 可追溯")

        if not has_real_data_plots:
            warnings.append("当前报告缺少真实数据图表。请上传 CSV/Excel 等结构化数据集以启用图表生成。")

        if not references_verified and not has_real_data_plots:
            critical_issues.append("缺少真实引用且无真实数据图表，报告不符合赛题基本要求")

        total_fields = len(CHECK_FIELDS)
        score = int(completed_fields / total_fields * 60)
        if references_verified > 0:
            score += 15
        if has_real_data_plots:
            score += 10
        if not missing_fields:
            score += 10
        if has_actual_or_simulated:
            score += 5
        score -= len(critical_issues) * 5
        score = max(0, min(100, score))

        passed = score >= 60 and len(critical_issues) == 0

        result.data = {
            "score": score,
            "passed": passed,
            "missing_fields": missing_fields,
            "warnings": warnings,
            "critical_issues": critical_issues,
            "recommendations": recommendations,
            "references_verified": int(references_verified),
            "has_real_data_plots": has_real_data_plots,
            "has_actual_or_simulated_results": has_actual_or_simulated,
            "completed_fields": completed_fields,
            "total_fields": total_fields,
        }

        if critical_issues:
            result.add_warning(f"发现 {len(critical_issues)} 个关键问题，报告不符合赛题要求")

        if score < 60:
            result.add_warning(f"报告质量评分 {score}，低于及格线 60，建议补充文献、数据或实验结果后重新生成")

        return result

    # ────────────── Field Extraction ──────────────

    @staticmethod
    def _extract_field_value(
        report_data: dict, chapters: dict, key: str
    ) -> Any:
        if key == "paper_title":
            return report_data.get("paper_title", "")
        if key == "paper_abstract":
            return report_data.get("paper_abstract", "")
        if key in ("datasets", "source", "references"):
            structured = report_data.get(key)
            if structured is not None and (isinstance(structured, list) and len(structured) > 0):
                return structured
        if key == "target":
            structured = report_data.get(key)
            if isinstance(structured, dict) and len(structured) > 0:
                return structured
        if key == "experiments":
            structured = report_data.get(key)
            if isinstance(structured, dict) and len(structured) > 0:
                return structured
        if key == "results":
            top = report_data.get("results")
            if top is not None and top != "":
                return top
        return chapters.get(key, "")

    # ────────────── Results Structure Check ──────────────

    @staticmethod
    def _check_results_structure(chapters: dict) -> bool:
        from app.services.report_compliance_service import parse_chapter_value, _structured_item_count

        results_obj = parse_chapter_value(chapters.get("results"))
        if isinstance(results_obj, dict):
            has_actual = _structured_item_count(results_obj.get("actual_results")) > 0
            has_simulated = _structured_item_count(results_obj.get("simulated_results")) > 0
            return has_actual or has_simulated
        if isinstance(results_obj, str):
            rl = results_obj.lower()
            return any(
                kw in rl
                for kw in (
                    "actual_result", "actual results", "simulated_result", "simulated results",
                    "实际结果", "模拟结果", "合并 csv", "data_finder",
                )
            )
        return False

    # ────────────── Check Helpers ──────────────

    @staticmethod
    def _check_technical_details(
        value: Any, warnings: List[str], critical_issues: List[str],
    ) -> None:
        """Technical Details 聚焦科学方法即可，不再强制提及 Qwen/百炼。"""
        _ = (value, warnings, critical_issues)

    @staticmethod
    def _check_datasets(
        value: str, warnings: List[str], critical_issues: List[str],
    ) -> None:
        has_real_source = any(
            pat.search(value) for pat in [
                re.compile(r"https?://", re.IGNORECASE),
                re.compile(r"doi\s*:", re.IGNORECASE),
                re.compile(r"DOI\s*:", re.IGNORECASE),
                re.compile(r"数据集\s*[：:]", re.IGNORECASE),
                re.compile(r"公开数据", re.IGNORECASE),
                re.compile(r"拟采集", re.IGNORECASE),
                re.compile(r"将(收集|采集|获取)", re.IGNORECASE),
            ]
        )
        has_fake = any(pat.search(value) for pat in FAKE_DATASET_PATTERNS)
        if has_fake:
            critical_issues.append("Datasets 包含示例/模拟/随机数据，需替换为真实来源或标记拟采集")
        if not has_real_source:
            warnings.append("Datasets 缺少真实数据来源 URL 或拟采集说明")

    @staticmethod
    def _check_datasets_structured(
        datasets: List[Any], warnings: List[str], critical_issues: List[str],
    ) -> None:
        has_source = False
        for ds in datasets:
            if isinstance(ds, dict):
                url = ds.get("url") or ds.get("source_url") or ds.get("external_url")
                license_val = ds.get("license") or ds.get("licence")
                if url:
                    has_source = True
                if license_val:
                    has_source = True
            elif isinstance(ds, str) and len(ds.strip()) >= 10:
                has_source = True
        if not has_source:
            warnings.append("Datasets 缺少真实数据来源 URL 或许可证信息")

    @staticmethod
    def _check_results_field(
        value: Any, chapters: dict, warnings: List[str], critical_issues: List[str],
    ) -> None:
        results_obj = chapters.get("results", {})
        if isinstance(results_obj, dict):
            has_actual = bool(results_obj.get("actual_results"))
            has_simulated = bool(results_obj.get("simulated_results"))
            has_expected = bool(results_obj.get("expected_results"))
            has_limitations = bool(results_obj.get("limitations"))

            if not has_actual and not has_simulated and not has_expected:
                warnings.append("Results 未区分 actual/simulated/expected，建议明确标注结果类型")
            if has_expected and not (has_actual or has_simulated):
                warnings.append("Results 仅有预期结果，建议补充模拟验证或小样实验")
            if not has_limitations:
                warnings.append("Results 未注明局限性，建议补充")
            return

        text = str(value) if value else ""
        value_lower = text.lower()
        has_actual = "actual" in value_lower or "实际" in value_lower
        has_simulated = "simulat" in value_lower or "模拟" in value_lower
        has_expected = "expect" in value_lower or "预期" in value_lower

        if not any([has_actual, has_simulated, has_expected]):
            warnings.append("Results 未区分 actual/simulated/expected，建议明确标注结果类型")
        if has_expected and not (has_actual or has_simulated):
            warnings.append("Results 仅有预期结果，建议补充模拟验证或小样实验")

    @staticmethod
    def _check_reference_quality(
        references: List[Any], warnings: List[str], critical_issues: List[str],
    ) -> None:
        has_unknown = False
        has_placeholder = False
        has_fabrication = False
        for ref in references:
            ref_text = str(ref) if ref else ""
            if any(pat.search(ref_text) for pat in UNKNOWN_AUTHOR_PATTERNS):
                has_unknown = True
            if any(pat.search(ref_text) for pat in PLACEHOLDER_PATTERNS):
                has_placeholder = True
            if any(pat.search(ref_text) for pat in LLM_FABRICATION_PATTERNS):
                has_fabrication = True

        if has_unknown:
            critical_issues.append("References 存在 unknown/匿名作者，需替换为真实文献")
        if has_placeholder:
            critical_issues.append("References 存在 placeholder/待填项，需补全文献信息")
        if has_fabrication:
            critical_issues.append("References 存在 LLM 虚构引用模式（ViT Paper/Cross-modal Paper 等）")

    @staticmethod
    def _check_unknown_patterns(
        report_data: dict, chapters: dict,
        warnings: List[str], critical_issues: List[str],
    ) -> None:
        all_text_parts = [
            report_data.get("paper_title", ""),
            report_data.get("paper_abstract", ""),
        ]
        for key in ("problem_statement", "rationale", "technical_details",
                     "datasets", "source", "target", "methods", "experiments", "results"):
            val = chapters.get(key, "")
            all_text_parts.append(str(val) if not isinstance(val, str) else val)

        full_text = " ".join(all_text_parts)

        unknown_count = 0
        placeholder_count = 0
        fabrication_count = 0
        for pat in UNKNOWN_AUTHOR_PATTERNS:
            unknown_count += len(pat.findall(full_text))
        for pat in PLACEHOLDER_PATTERNS:
            placeholder_count += len(pat.findall(full_text))
        for pat in LLM_FABRICATION_PATTERNS:
            fabrication_count += len(pat.findall(full_text))

        if unknown_count > 0:
            warnings.append(f"报告正文中出现 {unknown_count} 处 unknown/未知/匿名作者标记")
        if placeholder_count > 0:
            warnings.append(f"报告正文中出现 {placeholder_count} 处 placeholder/待填项")
        if fabrication_count > 0:
            critical_issues.append("报告正文中存在 LLM 虚构引用模式（如 ViT Paper、Cross-modal Paper），需替换为真实文献")

    @staticmethod
    def _check_non_qwen_models(
        report_data: dict, chapters: dict, critical_issues: List[str],
    ) -> None:
        all_text_parts = [
            report_data.get("paper_title", ""),
            report_data.get("paper_abstract", ""),
        ]
        for key in ("technical_details", "methods", "experiments", "rationale"):
            val = chapters.get(key, "")
            all_text_parts.append(str(val) if not isinstance(val, str) else val)

        full_text = " ".join(all_text_parts)
        found_models = []
        for pat in NON_QWEN_MODEL_PATTERNS:
            matches = pat.findall(full_text)
            for m in matches:
                found_models.append(m)

        if found_models:
            unique_models = list(set(found_models))
            critical_issues.append(
                f"报告中出现非 Qwen 模型名: {', '.join(unique_models)}。"
                f"根据赛题要求，核心技术应基于 Qwen/千问和阿里云百炼。"
            )