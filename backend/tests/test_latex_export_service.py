"""
LaTeX 报告导出服务测试
"""
import tempfile
import unittest
from pathlib import Path

from app.services.latex_export_service import (
    _build_references_bib,
    build_latex_document,
    copy_template_assets,
    escape_latex,
    export_report_via_latex,
    get_latex_template_dir,
    parse_reference_line_to_item,
)


class TestLatexExportService(unittest.TestCase):
    def test_escape_latex_special_chars(self):
        text = "100% & $x_1$ #tag {brace} ~ ^ \\alpha"
        escaped = escape_latex(text)
        self.assertIn(r"\%", escaped)
        self.assertIn(r"\&", escaped)
        self.assertIn("$x_1$", escaped)
        self.assertIn(r"\#", escaped)
        self.assertIn(r"\alpha", escaped)

    def test_escape_latex_promotes_inline_math_commands(self):
        text = "Planck CMB 提供 H\\_0, \\Omega\\_m, w 等参数"
        escaped = escape_latex(text)
        self.assertIn("$H_0$", escaped)
        self.assertIn(r"\Omega", escaped)
        self.assertIn("$", escaped)

    def test_build_latex_document_contains_sections(self):
        result = {
            "title": "科学假设与研究计划",
            "paper_title": "基于模拟验证的科学假设研究",
            "paper_abstract": "摘要内容。",
            "chapters": {
                "problem_statement": "待研究问题内容",
                "rationale": "解决思路",
                "technical_details": "技术手段",
                "datasets": "数据集说明",
                "source": "历史数据",
                "target": "目标数据",
                "methods": "方法论",
                "experiments": "实验设计",
                "results": "实验结果",
                "references": [],
            },
        }
        tex = build_latex_document(result)
        self.assertIn("\\section{待研究问题}", tex)
        self.assertIn("\\section{解决思路}", tex)
        self.assertIn("\\begin{abstract}", tex)
        self.assertNotIn("Paper Title", tex)

    def test_export_report_via_latex_writes_tex_and_assets(self):
        result = {
            "title": "测试报告",
            "paper_title": "LaTeX 导出测试",
            "paper_abstract": "摘要内容。",
            "chapters": {
                "problem_statement": "问题",
                "rationale": "思路",
                "technical_details": "技术",
                "datasets": "数据集",
                "source": "源",
                "target": "目标",
                "methods": "方法",
                "experiments": "实验",
                "results": "结果",
                "references": [],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            export_result = export_report_via_latex(
                result=result,
                output_dir=tmp,
                project_info={"title": "测试"},
            )

            tex_path = Path(export_result["tex_file"])
            self.assertTrue(tex_path.exists())
            self.assertGreater(len(export_result["latex_content"]), 100)
            self.assertTrue((Path(tmp) / "iclr2024_conference.sty").exists())
            self.assertTrue((Path(tmp) / "report.tex").exists())
            self.assertEqual(export_result.get("export_method"), "latex")

    def test_copy_template_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_template_assets(Path(tmp), get_latex_template_dir())
            self.assertTrue((Path(tmp) / "natbib.sty").exists())

    def test_merge_report_extra_metadata_includes_pdf_fields(self):
        from app.services.report_service import merge_report_extra_metadata

        extra = merge_report_extra_metadata(
            {"completed": 9},
            {"pdf_success": True, "export_method": "latex", "plots": [{"plot_id": "p1"}]},
        )
        self.assertTrue(extra["pdf_success"])
        self.assertEqual(extra["export_method"], "latex")
        self.assertEqual(len(extra["plots"]), 1)
        self.assertEqual(extra["completed"], 9)

    def test_sanitize_clears_llm_markdown_when_chapters_present(self):
        from app.services.report_content_sanitizer import sanitize_report_result

        result = sanitize_report_result(
            {
                "markdown_content": "## 1. Paper Title\n\n旧版 Markdown",
                "chapters": {"problem_statement": "待研究问题内容"},
            }
        )
        self.assertEqual(result["markdown_content"], "")
        self.assertIn("待研究问题", result["chapters"]["problem_statement"])

    def test_parse_reference_line_to_item(self):
        line = "Smith, J. Dark energy in N-body simulations (2021). DOI: 10.1234/example"
        parsed = parse_reference_line_to_item(line)
        self.assertIn("Dark energy", parsed["title"])
        self.assertEqual(parsed["year"], "2021")
        self.assertEqual(parsed["doi"], "10.1234/example")
        self.assertIn("Smith", parsed["authors"])

    def test_build_references_bib_no_duplicate_misc(self):
        citation_map = [{
            "title": "Planetary orbit stability",
            "authors": "Alice, Bob",
            "year": "2020",
            "doi": "10.5555/test",
        }]
        chapters = {
            "references": [
                "Alice, Bob. Planetary orbit stability (2020). DOI: 10.5555/test",
            ],
        }
        bib, keys = _build_references_bib(chapters, citation_map=citation_map)
        self.assertEqual(len(keys), 1)
        self.assertIn("author = {Alice and Bob}", bib)
        self.assertNotIn("@misc", bib)

    def test_build_references_bib_parses_plain_reference_lines(self):
        chapters = {
            "references": [
                "Wang, L. Cosmological N-body simulation datasets (2019). https://arxiv.org/abs/1901.00001",
            ],
        }
        bib, keys = _build_references_bib(chapters)
        self.assertEqual(len(keys), 1)
        self.assertIn("Cosmological N-body", bib)
        self.assertIn("author = {Wang, L}", bib)


if __name__ == "__main__":
    unittest.main()
