"""
LaTeX 报告导出服务测试
"""
import tempfile
import unittest
from pathlib import Path

from app.services.latex_export_service import (
    build_latex_document,
    copy_template_assets,
    escape_latex,
    export_report_via_latex,
    get_latex_template_dir,
)


class TestLatexExportService(unittest.TestCase):
    def test_escape_latex_special_chars(self):
        text = "100% & $x_1$ #tag {brace} ~ ^ \\alpha"
        escaped = escape_latex(text)
        self.assertIn(r"\%", escaped)
        self.assertIn(r"\&", escaped)
        self.assertIn(r"\_", escaped)
        self.assertIn(r"\alpha", escaped)

    def test_build_latex_document_contains_sections(self):
        result = {
            "title": "科学假设与研究计划",
            "paper_title": "基于多模态数据的科学假设生成研究",
            "paper_abstract": "本文提出一种结合文献与数据的假设生成方法。",
            "chapters": {
                "problem_statement": "当前领域存在数据与文献割裂的问题。",
                "rationale": "通过联合建模提升假设可验证性。",
                "technical_details": "采用 Qwen 大模型与 FAISS 向量检索。",
                "datasets": ["ChestX-ray14", "MIMIC-III"],
                "source": "历史公开数据集",
                "target": {"modality": "影像", "label": "疾病分类"},
                "methods": "Pipeline 八阶段自动生成。",
                "experiments": {
                    "baselines": ["仅文献", "仅数据"],
                    "metrics": ["AUC", "F1"],
                    "experimental_setup": "三组对照实验",
                },
                "results": {
                    "expected_results": "预期 AUC 提升 5%",
                },
                "references": ["He, K., et al. (2016). Deep Residual Learning."],
            },
        }

        latex = build_latex_document(
            result=result,
            project_info={"title": "测试项目", "research_domain": "医学 AI"},
            template_dir=get_latex_template_dir(),
        )

        self.assertIn("\\documentclass{article}", latex)
        self.assertIn("\\usepackage[UTF8,fontset=fandol]{ctex}", latex)
        self.assertIn("\\section{待研究问题}", latex)
        self.assertIn("\\section{解决思路}", latex)
        self.assertIn("\\section{实验设计}", latex)
        self.assertIn("\\section{实验结果}", latex)
        self.assertIn("\\bibliographystyle{iclr2024_conference}", latex)
        self.assertIn("\\label{fig:workflow}", latex)
        self.assertIn("\\toprule", latex)
        self.assertIn("\\bibliography{references}", latex)
        self.assertIn("基于多模态数据的科学假设生成研究", latex)

    def test_export_report_via_latex_writes_tex_and_assets(self):
        result = {
            "title": "测试报告",
            "paper_title": "LaTeX 导出测试",
            "paper_abstract": "摘要内容。",
            "markdown_content": "# 测试\n\nMarkdown 回退内容。",
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
                fallback_markdown_pdf=False,
            )

            tex_path = Path(export_result["tex_file"])
            self.assertTrue(tex_path.exists())
            self.assertGreater(len(export_result["latex_content"]), 100)
            self.assertTrue((Path(tmp) / "iclr2024_conference.sty").exists())
            self.assertTrue((Path(tmp) / "report.tex").exists())

    def test_copy_template_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_template_assets(Path(tmp), get_latex_template_dir())
            self.assertTrue((Path(tmp) / "natbib.sty").exists())


if __name__ == "__main__":
    unittest.main()
