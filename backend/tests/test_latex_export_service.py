"""
LaTeX 报告导出服务测试
"""
import tempfile
import unittest
from pathlib import Path

from app.services.latex_export_service import (
    _build_figures_section,
    _build_references_bib,
    _build_thebibliography_section,
    _collect_bibliography_items,
    _format_chapter_body,
    _format_reference_gbt7714,
    build_latex_document,
    clean_reference_text,
    copy_template_assets,
    escape_latex,
    export_report_via_latex,
    format_reference_items_as_gbt7714_lines,
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

    def test_escape_latex_does_not_double_subscript_column_names(self):
        text = "字段含 temperature_K, k_W_per_mK, sigma_S_per_m, seebeck_uV_per_K"
        escaped = escape_latex(text)
        self.assertNotIn("$k_W_per_mK$", escaped)
        self.assertNotIn("$S_per_m$", escaped)
        # 列名以下划线转义保留在正文，避免 Double subscript
        self.assertIn(r"k\_W\_per\_mK", escaped)

    def test_escape_ensuremath_lambda_not_broken(self):
        """文献摘要常见 \\ensuremath{\\Lambda}，不得变成 \\ensuremath{$\\Lambda$\\}。"""
        text = (
            "Einstein's cosmological constant, \\ensuremath{\\Lambda}; "
            "today the concept is dark energy."
        )
        escaped = escape_latex(text)
        self.assertNotIn(r"\ensuremath{$", escaped)
        self.assertNotIn(r"$\}", escaped)
        self.assertIn(r"$\Lambda$", escaped)
        # 已含 $ 的 ensuremath 也应归一
        escaped2 = escape_latex(r"constant \ensuremath{$\Lambda$} today")
        self.assertEqual(escaped2.count(r"\ensuremath"), 0)
        self.assertIn(r"$\Lambda$", escaped2)

    def test_prepare_figure_files_uses_existing_figures_dir(self):
        from app.services.latex_export_service import _prepare_figure_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fig_dir = root / "figures"
            fig_dir.mkdir()
            png = fig_dir / "iter_demo.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
            prepared = _prepare_figure_files(
                [{"plot_id": "iter_demo", "title": "Demo chart", "path": str(root / "missing.png")}],
                root,
            )
            self.assertEqual(len(prepared), 1)
            self.assertEqual(prepared[0]["relative_path"], "figures/iter_demo.png")

    def test_escape_windows_path_not_treated_as_commands(self):
        text = r"数据集路径：D:\浏览器\allgaps，共 5000 条"
        escaped = escape_latex(text)
        self.assertNotIn(r"\allgaps", escaped)
        self.assertNotIn(r"\浏", escaped)
        self.assertIn("D:/浏览器/allgaps", escaped)

    def test_escape_users_path_segment(self):
        text = r"C:\Users\demo\data.csv"
        escaped = escape_latex(text)
        self.assertIn("C:/Users/demo/data.csv", escaped)
        self.assertNotIn(r"\Users", escaped)

    def test_format_chapter_body_bullet_list_and_windows_path(self):
        text = "- 实验采用本地目录（路径：D:\\浏览器\\allgaps）\n- 共 5000 条样本"
        body = _format_chapter_body(text)
        self.assertIn(r"\begin{itemize}", body)
        self.assertIn(r"\item", body)
        self.assertIn("D:/浏览器/allgaps", body)
        self.assertNotIn(r"\allgaps", body)

    def test_format_chapter_body_prose_not_itemize(self):
        """多行散文不得整段变成 itemize（避免每行一个圆点）。"""
        text = (
            "**主要发现。**\n"
            "已观测到关键指标并形成实验图。\n"
            "**局限与后续工作。**\n"
            "当前为 smoke 验证，证据层级较弱。"
        )
        body = _format_chapter_body(text)
        self.assertNotIn(r"\begin{itemize}", body)
        self.assertNotIn(r"\item", body)
        self.assertIn(r"\textbf{主要发现。}", body)
        self.assertIn("证据层级较弱", body)

    def test_format_chapter_body_mixed_list_and_prose(self):
        text = (
            "- 执行状态: 成功\n"
            "- 沙箱图表: 3 张\n"
            "#### 图题与核心读图要点\n"
            "1. **混淆矩阵** — 关注对角线。\n"
            "2. **折线图** — 对比前后半段。\n"
            "> 以下结果以沙箱验证为准。"
        )
        body = _format_chapter_body(text)
        self.assertIn(r"\begin{itemize}", body)
        self.assertIn(r"\begin{enumerate}", body)
        self.assertIn(r"\paragraph{图题与核心读图要点}", body)
        self.assertIn(r"\textit{", body)
        # 编号读图要点不应再被塞进 itemize
        self.assertNotIn(r"\item 1.", body)

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

    def test_format_reference_gbt7714_chinese_book(self):
        line = _format_reference_gbt7714(
            {
                "authors": ["姜启源", "谢金星", "叶俊"],
                "title": "数学模型",
                "publisher_location": "北京",
                "publisher": "高等教育出版社",
                "year": "2018",
            }
        )
        self.assertIn("姜启源", line)
        self.assertIn("数学模型[M]", line)
        self.assertNotIn("{[M]}", line)
        self.assertIn("北京: 高等教育出版社", line)
        self.assertIn("2018", line)

    def test_build_thebibliography_section(self):
        block = _build_thebibliography_section(
            [
                {
                    "authors": "Smith, J.",
                    "title": "Planetary orbit stability",
                    "journal": "ApJ",
                    "year": "2020",
                    "doi": "10.5555/test",
                }
            ]
        )
        self.assertIn("\\begin{thebibliography}", block)
        self.assertIn("\\bibitem{ref1}", block)
        self.assertIn("Planetary orbit stability", block)
        self.assertNotIn("\\bibliography{references}", block)

    def test_build_latex_document_uses_thebibliography(self):
        result = {
            "title": "测试",
            "paper_title": "测试论文",
            "paper_abstract": "摘要。",
            "chapters": {
                "problem_statement": "问题",
                "rationale": "思路",
                "technical_details": "技术",
                "datasets": "数据",
                "source": "源",
                "target": "目标",
                "methods": "方法",
                "experiments": "实验",
                "results": "结果",
                "references": [
                    "Smith, J. Planetary stability (2020). DOI: 10.5555/test",
                ],
            },
        }
        tex = build_latex_document(result)
        self.assertIn("\\begin{thebibliography}", tex)
        self.assertIn("\\bibitem{ref1}", tex)
        self.assertNotIn("\\bibliography{references}", tex)

    def test_figures_section_avoids_figure_h_and_uses_compact_layout(self):
        """7.3 图表用 minipage+captionof，避免 figure[H] 导致页末大片留白。"""
        charts = [
            {
                "relative_path": "figures/a.png",
                "title": "图A",
                "label": "fig:a",
            },
            {
                "relative_path": "figures/b.png",
                "title": "图B",
                "label": "fig:b",
            },
            {
                "relative_path": "figures/c.png",
                "title": "图C",
                "label": "fig:c",
            },
        ]
        tex = _build_figures_section(charts)
        self.assertIn("实验图表", tex)
        self.assertIn(r"\captionof{figure}", tex)
        self.assertIn(r"0.30\textheight", tex)
        self.assertNotIn(r"\begin{figure}[H]", tex)
        self.assertIn(r"\begin{minipage}", tex)

    def test_clean_reference_text_strips_html_and_dup_markers(self):
        self.assertEqual(clean_reference_text("<i>Planck</i> 2018 results"), "Planck 2018 results")
        self.assertEqual(clean_reference_text("Title{[J]}{[J]}"), "Title[J]")
        self.assertEqual(clean_reference_text("Title[J][J]"), "Title[J]")

    def test_format_gbt7714_strips_html_title(self):
        line = _format_reference_gbt7714(
            {
                "authors": "Planck Collaboration",
                "title": "<i>Planck</i> 2018 results. VI. Cosmological parameters",
                "journal": "Astron. Astrophys.",
                "year": "2020",
            }
        )
        self.assertNotIn("<i>", line)
        self.assertIn("Planck 2018 results", line)
        self.assertIn("[J]", line)
        self.assertNotIn("{[J]}", line)

    def test_collect_bibliography_skips_chapter_reparse_when_structured(self):
        chapters = {
            "references": [
                "Planck Collaboration. <i>Planck</i> 2018 results{[J]}{[J]}. Astron. Astrophys., 2020.",
                "Another garbled line{[J]}",
            ]
        }
        citation_map = [
            {
                "authors": "Planck Collaboration",
                "title": "<i>Planck</i> 2018 results. VI. Cosmological parameters",
                "journal": "Astron. Astrophys.",
                "year": "2020",
                "doi": "10.1051/0004-6361/201833910",
            }
        ]
        items = _collect_bibliography_items(chapters, citation_map=citation_map)
        self.assertEqual(len(items), 1)
        self.assertNotIn("<i>", items[0].get("title", ""))
        block = _build_thebibliography_section(items)
        self.assertEqual(block.count(r"\bibitem{ref"), 1)
        self.assertNotIn(r"\{[J]\}", block)

    def test_unified_gbt7714_formatter_matches_export(self):
        from app.services.report_compliance_service import format_corpus_reference_lines

        verified = [
            {
                "authors": ["姜启源", "谢金星", "叶俊"],
                "title": "数学模型及其应用方法导论",
                "publisher_location": "北京",
                "publisher": "高等教育出版社",
                "year": "2018",
            }
        ]
        a = format_reference_items_as_gbt7714_lines(verified_references=verified)
        b = format_corpus_reference_lines([], verified)
        self.assertEqual(a, b)
        self.assertTrue(a and "数学模型及其应用方法导论[M]" in a[0])


if __name__ == "__main__":
    unittest.main()
