# PDF / LaTeX 报告导出说明

> **推荐路径**：LaTeX 模板 → XeLaTeX 编译 PDF。详见 [LATEX_EXPORT_SETUP.md](../LATEX_EXPORT_SETUP.md)。

## 概述

PDF 导出优先级：

1. **LaTeX（推荐）** — 使用 `latex_template/scientific_plan_template.tex`，XeLaTeX + BibTeX 编译
2. **Markdown 回退** — Playwright Chromium 或 WeasyPrint 将 Markdown 转为 PDF

## LaTeX 依赖

请安装 TeX Live / MiKTeX，并确保 `xelatex`、`bibtex` 可用。未安装时仍会生成 `report.tex`，PDF 将尝试 Markdown 回退。

## Markdown 回退依赖

### 1. Python 依赖

```bash
pip install weasyprint markdown
```

`requirements.txt` 中已包含 `weasyprint` 依赖。

### 2. 系统依赖

#### Windows

Windows 通常不需要额外的系统依赖，WeasyPrint 会自动使用 Windows 自带的字体。

#### macOS

```bash
brew install pango libffi
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get install -y \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info
```

### 3. 中文字体

Windows 和 macOS 自带中文字体，无需额外配置。Linux 需要安装：

```bash
sudo apt-get install -y fonts-wqy-microhei fonts-wqy-zenhei
```

## API 使用

报告生成后，通过以下接口下载：

```
# 下载 Markdown
GET /api/v1/reports/{report_id}/download/md

# 下载 PDF
GET /api/v1/reports/{report_id}/download/pdf
```

前端在 [ExportActions](frontend/src/components/ExportActions.tsx) 组件中提供 Markdown 和 PDF 导出按钮。

## 故障排除

### 1. PDF 生成失败但 Markdown 正常

系统会自动保留 Markdown 文件，PDF 生成失败不影响其他功能。

### 2. 中文显示乱码

检查系统是否安装了中文字体。

### 3. WeasyPrint 报错 "no library called cairo"

安装缺失的系统依赖（见上方系统依赖安装部分）。

### 4. Windows 安装问题

如遇到 WeasyPrint 安装问题，可参考 [WeasyPrint Windows 安装指南](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)。