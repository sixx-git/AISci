# LaTeX 报告导出说明

## 概述

报告生成流程采用 **LaTeX 优先** 策略：

```
LLM 结构化章节 → report.tex + references.bib → XeLaTeX 编译 → report.pdf
```

模板位于项目根目录 `latex_template/`，基于 `scientific_plan_template.tex`（ICLR 中文样式 + ctex）。

Markdown / WeasyPrint 回退说明见 [backend/PDF_EXPORT_SETUP.md](./backend/PDF_EXPORT_SETUP.md)。

## 输出文件

每次 Pipeline 报告生成后，在 `backend/storage/reports/{report_id}/` 下写入：

| 文件 | 说明 |
|------|------|
| `report.tex` | 完整 LaTeX 源码 |
| `references.bib` | 参考文献 BibTeX |
| `report.pdf` | XeLaTeX 编译产物 |
| `report.md` | Markdown 预览（前端展示用） |
| `report_data.json` | 结构化数据（含 `latex_content`、`export_method`） |

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
LATEX_TEMPLATE_DIR=D:/Workplace/AISci/latex_template
XELATEX_COMMAND=xelatex
```

## 回退机制

若本机未安装 XeLaTeX 或编译失败，系统会 **自动回退** 到 Markdown → PDF，并在 `report_data.json` 的 `export_method` 字段标记为 `markdown_fallback`。

LaTeX 源码（`report.tex`）仍会正常生成，可手动编译：

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

## 相关文档

- [backend/PDF_EXPORT_SETUP.md](./backend/PDF_EXPORT_SETUP.md)
- [backend/prompts/report_generation.md](./backend/prompts/report_generation.md)
- [README.md](./README.md)
