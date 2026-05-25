# PDF 导出功能安装说明

## 概述

本功能使用 **WeasyPrint** 库将 Markdown 格式的研究报告转换为 PDF 文件，支持中文字体渲染。

## 依赖安装

### 1. 安装 Python 依赖

```bash
# 使用 pip
pip install weasyprint markdown

# 或者使用 poetry
poetry add weasyprint markdown
```

### 2. 安装系统依赖 (根据操作系统)

#### Windows

Windows 通常不需要额外的系统依赖，WeasyPrint 会自动使用 Windows 自带的字体。

#### macOS

```bash
# 使用 Homebrew
brew install pango libffi
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info
```

#### Linux (CentOS/RHEL)

```bash
sudo yum install -y \
    python3-cffi \
    cairo \
    pango \
    gdk-pixbuf2 \
    libffi-devel
```

### 3. 中文字体支持

确保系统有中文字体可用：

#### Windows

Windows 自带中文字体（如微软雅黑、宋体），无需额外配置。

#### macOS

macOS 自带 PingFang SC 等中文字体，无需额外配置。

#### Linux

可以安装以下字体：

```bash
# Ubuntu/Debian
sudo apt-get install -y fonts-wqy-microhei fonts-wqy-zenhei

# 或者安装 Google Noto 字体
sudo apt-get install -y fonts-noto-cjk
```

## 验证安装

### 1. 验证 WeasyPrint 安装

```python
python -c "import weasyprint; print('WeasyPrint 版本:', weasyprint.__version__)"
```

### 2. 验证 Markdown 安装

```python
python -c "import markdown; print('Markdown 版本:', markdown.__version__)"
```

## 目录结构

```
backend/
├── storage/
│   └── reports/
│       └── {report_id}/
│           ├── report.md
│           ├── report.pdf
│           └── report_data.json
├── app/
│   └── agents/
│       ├── report_generation_agent.py
│       └── report_style.css
```

## API 使用

### 生成报告

```
POST /api/reports/generate

Request:
{
  "project_id": "proj-123",
  "project_info": {...},
  "problem_understanding": {...},
  "literature_facts": [...],
  "citation_map": [...],
  "knowledge_gaps": {...},
  "final_hypothesis": {...},
  "experiment_design": {...},
  "small_validation": {...}
}

Response:
{
  "code": 200,
  "message": "研究报告生成完成",
  "data": {
    "report": {
      "title": "科学假设与研究计划",
      "paper_title": "...",
      "paper_abstract": "...",
      "markdown_content": "...",
      "chapters": {...},
      "report_id": "550e8400-e29b-41d4-a716-446655440000",
      "pdf_download_url": "http://localhost:8000/api/reports/download/550e8400-e29b-41d4-a716-446655440000/pdf",
      "md_download_url": "http://localhost:8000/api/reports/download/550e8400-e29b-41d4-a716-446655440000/md",
      "pdf_success": true
    },
    "summary": "..."
  }
}
```

### 下载报告

```
# 下载 PDF
GET /api/reports/download/{report_id}/pdf

# 下载 Markdown
GET /api/reports/download/{report_id}/md
```

## 故障排除

### 1. PDF 生成失败但 Markdown 正常

这种情况下，系统会自动保留 Markdown 文件，可以通过 Markdown 下载地址获取报告。

### 2. 中文显示乱码

检查系统是否安装了中文字体，`report_style.css` 中已配置了中文字体回退。

### 3. WeasyPrint 报错 "no library called cairo"

安装缺失的系统依赖（见上方系统依赖安装部分）。

### 4. 端口配置

如果 API_BASE_URL 需要配置，可以在 settings 中添加：

```python
# app/core/config.py
class Settings:
    # ... 其他配置
    API_BASE_URL: str = "http://localhost:8000"
```

## 自定义样式

编辑 `app/agents/report_style.css` 来自定义 PDF 样式：

- 字体
- 页面边距
- 标题样式
- 表格样式
- 代码块样式

## 架构说明

1. **ReportGenerationAgent** - 核心智能体，生成 Markdown 并尝试导出 PDF
2. **report_style.css** - PDF 样式文件，支持中文
3. **API 接口** - 提供生成和下载功能
4. **错误处理** - PDF 生成失败时保留 Markdown 文件作为备选方案

## 测试

运行单元测试：

```bash
cd backend
python -m pytest tests/test_report_generation_agent.py -v
```
