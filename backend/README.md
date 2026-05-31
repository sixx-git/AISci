# AI Scientist Backend

基于 FastAPI 的后端服务，包含 8 个智能体（Agent）、14 个科研 Skill 和 8 阶段 Pipeline。

## 目录结构

```
backend/
├── app/
│   ├── api/              # API 路由层
│   │   ├── projects.py   # 项目管理 API
│   │   ├── research.py   # 研究功能 API
│   │   ├── agents.py     # 智能体接口 API
│   │   ├── pipeline.py   # Pipeline 运行 API
│   │   ├── reports.py    # 报告生成与下载 API
│   │   ├── chat.py       # 对话功能 API
│   │   ├── documents.py  # 文档管理 API
│   │   ├── datasets.py   # 数据集 API
│   │   ├── literature.py # 文献检索 API
│   │   ├── vector_search.py # 向量检索 API
│   │   ├── v1.py         # v1 路由整合
│   │   └── diagnose.py   # 诊断接口
│   ├── agents/           # 8 个智能体（独立类 + Prompt + JSON Schema）
│   │   ├── problem_understanding_agent.py
│   │   ├── literature_mining_agent.py
│   │   ├── knowledge_gap_agent.py
│   │   ├── hypothesis_generation_agent.py
│   │   ├── hypothesis_review_agent.py
│   │   ├── experiment_design_agent.py
│   │   ├── small_validation_agent.py
│   │   └── report_generation_agent.py
│   ├── core/             # 核心配置
│   │   ├── config.py     # 配置管理（.env 加载）
│   │   └── database.py   # 数据库配置
│   ├── models/           # SQLAlchemy 数据模型
│   │   ├── project.py    # 项目模型
│   │   ├── core.py       # 核心模型（Pipeline / RunLog / Evidence 等）
│   │   ├── pipeline.py   # Pipeline 运行模型
│   │   ├── chat.py       # 对话模型
│   │   └── research.py   # 研究模型
│   ├── schemas/          # Pydantic 请求/响应 Schema
│   │   ├── common.py     # 通用响应格式
│   │   ├── project.py    # 项目相关 schemas
│   │   ├── research.py   # 研究相关 schemas
│   │   ├── chat.py       # 对话相关 schemas
│   │   └── documents.py  # 文档相关 schemas
│   ├── services/         # 业务逻辑层
│   │   ├── project_service.py   # 项目服务
│   │   ├── research_service.py  # 研究服务
│   │   ├── chat_service.py      # 对话服务
│   │   ├── document_service.py  # 文档服务
│   │   ├── pipeline_service.py  # Pipeline 服务
│   │   ├── llm_service.py       # LLM 服务（Qwen 客户端）
│   │   └── vector_service.py    # 向量检索服务
│   ├── skills/           # 14 个科研 Skill（工具层）
│   │   ├── literature/   # 论文搜索、引用验证、PDF 证据提取
│   │   ├── data/         # 数据清洗、数据集发现、多模态
│   │   ├── report/       # 图表生成、质量检查
│   │   ├── reasoning/    # 新颖性审查、问题对齐
│   │   └── experiment/   # 实验合理性检查
│   └── main.py           # FastAPI 入口 + /health + /health/llm
├── prompts/              # 8 个 Markdown Prompt 模板
├── tests/                # pytest 测试
├── data/                 # arXiv fallback 数据
├── storage/              # 运行时数据（FAISS 索引、报告、上传文件）
└── README.md
```

## 快速开始

### 1. 环境要求

- Python 3.10 / 3.11 / 3.12（推荐）
- 暂不建议 Python 3.13：部分依赖（SQLAlchemy、FAISS、sentence-transformers）可能存在兼容问题

### 2. 安装依赖

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
```

### 3. 配置环境变量

在项目根目录复制 `.env.example` 为 `backend/.env`：

```env
# 千问 API（必需，或开启 USE_MOCK_LLM）
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

# Mock LLM 模式（无需真实 API Key）
USE_MOCK_LLM=false

# 数据库（默认 SQLite，零配置）
DATABASE_URL=sqlite:///./data/aiscientist.db

# 向量存储
VECTOR_STORE_PATH=./storage/faiss_index
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# 文件上传
UPLOAD_DIR=./storage/uploads
ALLOWED_EXTENSIONS=txt,pdf,docx,md,csv
```

### 4. 启动服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问：
- API 文档 (Swagger): http://localhost:8000/docs
- API 文档 (ReDoc): http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health
- LLM 诊断: http://localhost:8000/health/llm

## 智能体架构

| Agent | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| ProblemUnderstanding | 研究问题文本 | 问题陈述、领域、关键词、边界 | 将模糊问题转化为可研究的结构化描述 |
| LiteratureMining | project_id + 研究问题 | 科学事实 + 证据列表 + 引用映射 | FAISS 检索 → Qwen 提取事实，每条绑定 chunk_id |
| KnowledgeGap | 文献事实 + 不确定点 | 知识缺口、矛盾、研究机会 | 发现文献中的空白和可研究方向 |
| HypothesisGeneration | 知识缺口 + 文献证据 | 候选假设 + 对齐评分 + 数据证据 | 基于缺口生成可验证假设 |
| HypothesisReview | 候选假设 + 文献上下文 | 新颖性评分、可行性评估 | 评估假设质量和原创性 |
| ExperimentDesign | 通过审查的假设 + 多模态数据 | 实验方案 + 指标 + 基线 | 为每个假设设计验证实验 |
| SmallValidation | 实验设计 + 数据集 | 验证结果 + 量化指标 | 小样本快速验证假设可行性 |
| ReportGeneration | 全流程中间产物 | 12 字段最终报告 + 合规检查 | 聚合所有阶段输出，生成完整报告 |

每个 Agent 的特点：
- 独立类 — 可单独实例化和测试
- Prompt 模板 — `backend/prompts/*.md`，独立于代码，方便调优
- JSON Schema 约束 — Pydantic 模型确保输出类型安全
- 来源绑定 — 所有事实和引用 traceable 到原始文献

## Pipeline（一键运行）

```bash
POST /api/v1/pipeline/run
```

8 个阶段顺序执行，每个阶段记录：

```
StageExecution
├── input_data        # 该阶段输入
├── output_data       # 该阶段输出
├── prompt_used       # Prompt 原文
├── model_parameters  # temperature / model / version
├── token_count       # Token 用量
├── duration_ms       # 耗时
└── CallLog           # 每次 Qwen API 调用独立记录
```

## 报告质量检查

`ReportQualityCheckSkill` 对最终报告做以下检查：

- 12 字段完整性（Paper Title → References）
- Technical Details 是否明确 Qwen/千问和阿里云百炼
- References 是否包含 unknown / placeholder 等虚构引用
- Results 是否区分 actual / simulated / expected
- Datasets 是否有真实来源或标记拟采集
- 图表是否有 `source_dataset_id` 和 `is_generated_from_real_data`
- 是否出现 GPT-4 / Claude / Llama 等非 Qwen 模型表述

## 报告导出

支持 Markdown 和 PDF 两种格式导出：

```
GET /api/v1/reports/{report_id}/download/md   # 下载 Markdown
GET /api/v1/reports/{report_id}/download/pdf  # 下载 PDF
```

## 统一响应格式

所有 API 接口使用统一的响应格式：

### 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": "2024-01-01T00:00:00"
}
```

### 分页响应

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  },
  "timestamp": "2024-01-01T00:00:00"
}
```

## 测试

```bash
cd backend
pytest tests/ -v
```

覆盖：Agent 单元测试、Pipeline 端到端、向量存储、数据库、文档解析等。

## 更多信息

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [数据库设计文档](./DATABASE.md)
- [PDF 导出说明](./PDF_EXPORT_SETUP.md)
- [项目根目录 README](../README.md)