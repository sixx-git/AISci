"""
报告质量检查 Skill
参考能力：挑战杯 XH-202619 赛题规范
——对 report_data.json 做赛题规范检查，输出评分和修正建议。
"""
import logging
import re
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

CHECK_FIELDS = [
    ("paper_title", "Paper Title"),
    ("paper_abstract", "Paper Abstract"),
    ("problem_statement", "Problem Statement"),
    ("rationale", "Rationale"),
    ("technical_details", "Technical Details"),
    ("datasets", "Datasets"),
    ("source", "Source"),
    ("target", "Target"),
    ("methods", "Methods"),
    ("experiments", "Experiments"),
    ("results", "Results"),
    ("references", "References"),
]

Qwen_KEYWORDS = [
    re.compile(r"千问", re.IGNORECASE),
    re.compile(r"Qwen", re.IGNORECASE),
    re.compile(r"通义千问", re.IGNORECASE),
    re.compile(r"阿里云百炼", re.IGNORECASE),
    re.compile(r"bailian", re.IGNORECASE),
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
      - report_data: dict                 报告数据 (report_data.json)
      - references_verified: int          已验证引用数
      - has_real_data_plots: bool         是否有真实数据图表
      - citation_grounding_output: dict   CitationGroundingSkill 输出

    输出 (SkillResult.data):
      - score: int                        评分 0-100
      - missing_fields: List[str]         缺失字段
      - warnings: List[str]               警告
      - critical_issues: List[str]        关键问题
      - recommendations: List[str]        建议
      - references_verified: int          已验证引用数
      - has_real_data_plots: bool         是否有真实数据图表
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
        citation_output = input_data.get("citation_grounding_output", {})

        if isinstance(citation_output, dict):
            cg_data = citation_output.get("citation_grounding", {})
            if isinstance(cg_data, dict) and cg_data.get("data"):
                inner = cg_data["data"]
                if isinstance(inner.get("references_verified"), (int, float)):
                    references_verified = inner["references_verified"]

        chapters = report_data.get("chapters", {})

        missing_fields: List[str] = []
        warnings: List[str] = []
        critical_issues: List[str] = []
        recommendations: List[str] = []
        completed_fields = 0

        for key, label in CHECK_FIELDS:
            if key == "paper_title":
                value = report_data.get("paper_title", "")
            elif key == "paper_abstract":
                value = report_data.get("paper_abstract", "")
            elif key == "references":
                value = chapters.get("references", [])
            else:
                value = chapters.get(key, "")

            if key == "references":
                if isinstance(value, list) and len(value) > 0:
                    ref_text = " ".join(str(r) for r in value)
                    has_real = any(
                        r and r != "暂无真实文献引用，需补充文献库" and not r.startswith("[待")
                        for r in value
                    )
                    if has_real:
                        completed_fields += 1
                        self._check_reference_quality(value, warnings, critical_issues)
                    else:
                        missing_fields.append(label)
                        critical_issues.append(f"References 缺失或无效，不符合赛题要求")
                else:
                    missing_fields.append(label)
                    critical_issues.append(f"References 缺失或无效，不符合赛题要求")
            elif isinstance(value, str) and len(value.strip()) >= 20:
                completed_fields += 1
                if key == "technical_details":
                    self._check_technical_details(value, warnings, critical_issues)
                if key == "datasets":
                    self._check_datasets(value, warnings, critical_issues)
                if key == "results":
                    self._check_results(value, warnings, critical_issues)
            elif isinstance(value, str) and len(value.strip()) > 0:
                warnings.append(f"{label} 内容较短，建议补充（当前 {len(value.strip())} 字符）")
            else:
                missing_fields.append(label)

        self._check_unknown_patterns(report_data, chapters, warnings, critical_issues)

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
        score -= len(critical_issues) * 5
        score = max(0, min(100, score))

        result.data = {
            "score": score,
            "missing_fields": missing_fields,
            "warnings": warnings,
            "critical_issues": critical_issues,
            "recommendations": recommendations,
            "references_verified": int(references_verified),
            "has_real_data_plots": has_real_data_plots,
            "completed_fields": completed_fields,
            "total_fields": total_fields,
        }

        if critical_issues:
            result.add_warning(f"发现 {len(critical_issues)} 个关键问题，报告不符合赛题要求")

        if score < 60:
            result.add_warning(f"报告质量评分 {score}，低于及格线 60，建议整改后重新生成")

        return result

    # ────────────── Check Helpers ──────────────

    @staticmethod
    def _check_technical_details(
        value: str, warnings: List[str], critical_issues: List[str],
    ) -> None:
        has_qwen = any(pat.search(value) for pat in Qwen_KEYWORDS)
        if not has_qwen:
            critical_issues.append("Technical Details 未明确提及 Qwen/千问 和阿里云百炼")

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
    def _check_results(
        value: str, warnings: List[str], critical_issues: List[str],
    ) -> None:
        value_lower = value.lower()
        has_actual = "actual" in value_lower or "实际" in value_lower
        has_simulated = "simulat" in value_lower or "模拟" in value_lower
        has_expected = "expect" in value_lower or "预期" in value_lower

        if not any([has_actual, has_simulated, has_expected]):
            warnings.append("Results 未区分 actual/simulated/expected，建议明确标注结果类型")
        if has_expected and not (has_actual or has_simulated):
            warnings.append("Results 仅有预期结果，建议补充模拟验证或小样实验")

    @staticmethod
    def _check_reference_quality(
        references: List[str], warnings: List[str], critical_issues: List[str],
    ) -> None:
        has_unknown = False
        has_placeholder = False
        for ref in references:
            ref_text = str(ref) if ref else ""
            if any(pat.search(ref_text) for pat in UNKNOWN_AUTHOR_PATTERNS):
                has_unknown = True
            if any(pat.search(ref_text) for pat in PLACEHOLDER_PATTERNS):
                has_placeholder = True

        if has_unknown:
            critical_issues.append("References 存在 unknown/匿名作者，需替换为真实文献")
        if has_placeholder:
            critical_issues.append("References 存在 placeholder/待填项，需补全文献信息")

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
            if isinstance(val, str):
                all_text_parts.append(val)

        full_text = " ".join(all_text_parts)

        unknown_count = 0
        placeholder_count = 0
        for pat in UNKNOWN_AUTHOR_PATTERNS:
            unknown_count += len(pat.findall(full_text))
        for pat in PLACEHOLDER_PATTERNS:
            placeholder_count += len(pat.findall(full_text))

        if unknown_count > 0:
            warnings.append(f"报告正文中出现 {unknown_count} 处 unknown/未知/匿名作者标记")
        if placeholder_count > 0:
            warnings.append(f"报告正文中出现 {placeholder_count} 处 placeholder/待填项")