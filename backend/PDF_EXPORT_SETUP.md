# LaTeX 报告导出说明

## 概述

报告生成流程采用 **LaTeX 优先** 策略：

```
LLM 结构化章节 → report.tex + references.bib → XeLaTeX 编译 → report.pdf
```

模板位于项目根目录 `latex_template/`，基于 `scientific_plan_template.tex`（ICLR 中文样式 + ctex）。

若编译失败，自动回退 Markdown → PDF（Playwright / WeasyPrint），详见 [PDF_EXPORT_SETUP.md](./PDF_EXPORT_SETUP.md)。

## 输出文件

每次 Pipeline 报告生成后，在 `backend/storage/reports/{report_id}/` 下写入：

| 文件 | 说明 |
|------|------|
| `report.tex` | 完整 LaTeX 源码 |
| `references.bib` | 参考文献 BibTeX（来自 citation_map / 文献库） |
| `report.pdf` | XeLaTeX 编译产物（或回退 PDF） |
| `report.md` | Markdown 预览（前端展示用） |
| `report_data.json` | 结构化数据（含 `latex_content`、`export_method`、`quality_check`） |

`export_method` 取值示例：`latex` / `markdown_fallback`。

## 安装 XeLaTeX（推荐）

### Windows

安装 [TeX Live](https://tug.org/texlive/) 或 [MiKTeX](https://miktex.org/)，确保 `xelatex` 和 `bibtex` 在 PATH 中。

### macOS

```bash
brew install --cask mactex
```

### Linux

```bash
sudo apt-get install texlive-xetex texlive-lang-chinese texlive-latex-extra
```

验证：

```bash
xelatex --version
bibtex --version
```

## 环境变量（可选）

```env
# 自定义模板目录（默认 ../latex_template）
LATEX_TEMPLATE_DIR=D:/Workplace/AISci/latex_template

# 自定义 xelatex 命令名或路径
XELATEX_COMMAND=xelatex
```

## 回退机制

若本机未安装 XeLaTeX 或编译失败：

1. 系统尝试 Markdown → PDF 回退
2. `report.tex` 仍会生成，可手动编译：

```bash
cd backend/storage/reports/{report_id}
xelatex report.tex
bibtex report
xelatex report.tex
xelatex report.tex
```

## API 下载

```http
GET /api/v1/reports/{report_id}/download/tex
GET /api/v1/reports/{report_id}/download/pdf
GET /api/v1/reports/{report_id}/download/md
```

前端 [ExportActions](../frontend/src/components/ExportActions.tsx) 提供导出按钮。

## 报告质量与溯源

- `ReportQualityCheckSkill` 检查 12 字段与 References 真实性
- 报告生成输入含 Data Finder **provenance** 与假设 **supporting_fact_ids**
- 禁止在 References 中写入无法在 citation_map 中验证的条目

## 相关文档

- [PDF_EXPORT_SETUP.md](./PDF_EXPORT_SETUP.md)
- [backend/README.md](./README.md)
- [prompts/report_generation.md](./prompts/report_generation.md)
