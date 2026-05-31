# AI Scientist - 基于 Qwen 的智能科研助手

<p align="center">
  <b>挑战杯 XH-202619</b> |
  基于国产开源大模型的 AI Scientist 研发与应用
</p>

---

## 📋 项目简介

基于 **Qwen/千问**大模型开发的多智能体科研系统原型。从文献 / 数据输入到可验证科学假设输出，全流程自动化。

### 核心流程

```
研究问题 → 文献挖掘 → 知识缺口分析 → 假设生成 → 假设评估 → 实验设计 → 小样验证 → 报告生成
```

### 8 条设计原则

| # | 原则 |
|---|------|
| 1 | 后端 Python + FastAPI，前端 React + Vite + TailwindCSS |
| 2 | 向量检索 FAISS，本地数据库 SQLite |
| 3 | 模型调用通过 Qwen API 封装，API Key 仅从 `.env` 读取 |
| 4 | 每个 Agent 独立类 + Prompt 模板 + 输入/输出 JSON Schema |
| 5 | 所有科学事实和参考文献必须绑定来源，禁止虚构引用 |
| 6 | Pipeline 一键运行，保存每步输入、输出、日志、模型参数 |
| 7 | 最终报告 12 字段：Paper Title、Abstract、Problem Statement、Rationale、Technical Details、Datasets、Source、Target、Methods、Experiments、Results、References |
| 8 | 端到端验收脚本可一键验证所有接口 |

---

## 🚀 快速开始

**详细分步说明**请查看 [QUICKSTART.md](./QUICKSTART.md)。

### Windows

```batch
scripts\setup_backend.bat          # 创建 venv + 安装依赖
scripts\setup_frontend.bat         # pnpm install

# 复制 .env.example → backend\.env 并填入你的 QWEN_API_KEY
# 如果暂时没有 Key，设置 USE_MOCK_LLM=true 可跑通完整流程

scripts\run_dev.bat                # 一键启动前后端
```

### Linux / Mac

```bash
bash scripts/setup_backend.sh
bash scripts/setup_frontend.sh

# 复制 .env.example → backend/.env 并填入配置

bash scripts/run_dev.sh
```

启动后访问：

| 地址 | 说明 |
|------|------|
| http://localhost:3000 | 前端界面 |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |

### 端到端验收

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端
python scripts\check_e2e.py
```

输出示例：`14 PASS  0 WARN  0 FAIL`（所有核心接口可达）。

---

## 🛠️ 技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | React 18 + Vite 5 + TailwindCSS 3 |
| UI 图标 | lucide-react |
| 图表 | recharts |
| 数据库 | SQLite（默认） / MySQL（可选） |
| ORM | SQLAlchemy 2.0 |
| 向量检索 | FAISS (faiss-cpu) |
| 嵌入模型 | Sentence-Transformers |
| 大模型 | Qwen（阿里云百炼 / DashScope） |
| PDF 解析 | PyMuPDF |
| 包管理器 | pnpm |

---

## 📁 项目结构

```
AISci/
├── backend/
│   ├── app/
│   │   ├── agents/               # 8 个智能体（独立类 + Prompt + JSON Schema）
│   │   │   ├── problem_understanding_agent.py
│   │   │   ├── literature_mining_agent.py
│   │   │   ├── knowledge_gap_agent.py
│   │   │   ├── hypothesis_generation_agent.py
│   │   │   ├── hypothesis_review_agent.py
│   │   │   ├── experiment_design_agent.py
│   │   │   ├── small_validation_agent.py
│   │   │   └── report_generation_agent.py
│   │   ├── api/                  # API 路由模块
│   │   │   ├── projects.py, research.py, literature.py, datasets.py
│   │   │   ├── agents.py, pipeline.py, reports.py, documents.py
│   │   │   ├── chat.py, vector_search.py, diagnose.py, v1.py
│   │   ├── core/                 # 配置（.env 加载）、数据库、响应格式
│   │   ├── models/               # SQLAlchemy 模型（project / core / pipeline / chat / research）
│   │   ├── schemas/              # Pydantic 请求/响应 Schema
│   │   ├── services/             # 业务逻辑 + Qwen 客户端 + 向量存储
│   │   ├── skills/               # 14 个科研 Skill（工具层）
│   │   │   ├── literature/       # 论文搜索、引用验证、PDF 证据提取
│   │   │   ├── data/             # 数据清洗、数据集发现、多模态
│   │   │   ├── report/           # 图表生成、质量检查
│   │   │   ├── reasoning/        # 新颖性审查、问题对齐
│   │   │   └── experiment/       # 实验合理性检查
│   │   └── main.py               # FastAPI 入口 + /health + /health/llm
│   ├── prompts/                  # 8 个 Markdown Prompt 模板
│   ├── tests/                    # pytest 测试
│   ├── data/                     # arXiv fallback 数据
│   └── storage/                  # 运行时数据（FAISS 索引、向量索引、报告、上传文件）
├── frontend/
│   └── src/
│       ├── components/           # 32 个组件（QualityCheckCard、HypothesisCard、PipelineProgress 等）
│       ├── pages/                # 8 个页面（Projects、Workflow、Reports、Documents 等）
│       ├── services/             # 10 个 API 模块（projectService、pipelineService、hypothesisService 等）
│       ├── types/                # TypeScript 类型定义
│       ├── lib/                  # 工具函数（api.ts、utils.ts）
│       └── config/               # 环境配置
├── scripts/
│   ├── setup_backend.bat/sh      # 后端环境搭建（venv + pip install）
│   ├── setup_frontend.bat/sh     # 前端环境搭建（pnpm install）
│   ├── run_dev.bat/sh            # 一键启动前后端
│   ├── start_backend.bat/sh      # 仅启动后端
│   ├── init_db.py                # 数据库建表脚本
│   └── check_e2e.py              # 端到端验收脚本
├── .env.example                  # 环境变量模板
├── QUICKSTART.md                 # 详细快速入门
└── README.md
```

---

## ⚙️ 配置说明

复制 `.env.example` 为 `backend/.env`，按需修改。**必须从 `backend/` 目录启动后端**，uvicorn 会自动加载 `backend/.env`。

### 核心环境变量

```env
# 千问 API（必需，或开启 USE_MOCK_LLM）
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

# Mock LLM 模式（无需真实 API Key 即可跑通完整 Pipeline）
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

完整配置项参见 [.env.example](./.env.example)。

### 获取 Qwen API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 创建 API Key
3. 填入 `backend/.env` 的 `QWEN_API_KEY`

**没有 Key？** 设置 `USE_MOCK_LLM=true`，所有 LLM 调用返回模拟数据，可完整跑通 Pipeline 和前端交互。

---

## 🤖 智能体架构

| Agent | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| **ProblemUnderstanding** | 研究问题文本 | 问题陈述、领域、关键词、边界 | 将模糊问题转化为可研究的结构化描述 |
| **LiteratureMining** | project_id + 研究问题 | 科学事实 + 证据列表 + 引用映射 | FAISS 检索 → Qwen 提取事实，每条绑定 chunk_id |
| **KnowledgeGap** | 文献事实 + 不确定点 | 知识缺口、矛盾、研究机会 | 发现文献中的空白和可研究方向 |
| **HypothesisGeneration** | 知识缺口 + 文献证据 | 候选假设 + 对齐评分 + 数据证据 | 基于缺口生成可验证假设，标注 supporting_fact_ids |
| **HypothesisReview** | 候选假设 + 文献上下文 | 新颖性评分、可行性评估 | 评估假设质量和原创性 |
| **ExperimentDesign** | 通过审查的假设 + 多模态数据 | 实验方案 + 指标 + 基线 | 为每个假设设计验证实验 |
| **SmallValidation** | 实验设计 + 数据集 | 验证结果 + 量化指标 | 小样本快速验证假设可行性 |
| **ReportGeneration** | 全流程中间产物 | 12 字段最终报告 + 合规检查 | 聚合所有阶段输出，生成完整报告 |

每个 Agent 的特点：
- **独立类** — 可单独实例化和测试
- **Prompt 模板** — `backend/prompts/*.md`，独立于代码，方便调优
- **JSON Schema 约束** — Pydantic 模型确保输出类型安全
- **来源绑定** — 所有事实和引用 traceable 到原始文献

---

## 🔬 Skill 工具层

14 个 Skill 分别覆盖 5 个子领域，作为 Agent 调用的工具层：

| 分类 | Skill | 功能 |
|------|-------|------|
| **文献** | arxiv_search_skill | arXiv API 搜索 + 去重 + fallback |
| | search_papers_skill | 多源搜索整合（arXiv / Semantic Scholar / OpenAlex / CrossRef） |
| | citation_grounding_skill | 引用真实性验证 → 拒绝 LLM 虚构引用 |
| | pdf_evidence_extraction_skill | PDF 原文证据提取与定位 |
| **数据** | preliminary_analysis_skill | CSV 统计描述、缺失值、柱状图 |
| | dataset_discovery_skill | 公开数据集发现（HuggingFace / Kaggle / PapersWithCode） |
| | data_juicer_lite_skill | 数据质量分析与清洗 |
| | multimodal_ingest_skill | 多模态数据导入与预处理 |
| | multimodal_linking_skill | 跨模态数据对齐与关联 |
| **推理** | hypothesis_novelty_review_skill | 新颖性自动审查 |
| | question_alignment_skill | 研究问题-假设对齐度评分 |
| **报告** | scientific_plot_skill | 基于真实数据的科学图表 |
| | report_chart_generation_skill | 统计图表生成 |
| | report_quality_check_skill | 12 字段合规检查 + 虚构引用检测 |
| **实验** | experiment_sanity_check_skill | 实验方案合理性检查 |

---

## 📊 Pipeline（一键运行）

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

前端 [PipelineProgress](frontend/src/components/PipelineProgress.tsx) 实时展示进度、[RunLogDetail](frontend/src/components/RunLogDetail.tsx) 查看每步详情。

---

## 📝 报告质量检查

`ReportQualityCheckSkill` 对最终报告做以下检查：

- 12 字段完整性（Paper Title → References）
- Technical Details 是否明确 Qwen/千问和阿里云百炼
- References 是否包含 unknown / placeholder / ViT Paper 等虚构引用
- Results 是否区分 actual / simulated / expected
- Datasets 是否有真实来源或标记拟采集
- 图表是否有 `source_dataset_id` 和 `is_generated_from_real_data`
- 是否出现 GPT-4 / Claude / Llama 等非 Qwen 模型表述

输出：
```json
{
  "score": 75,
  "passed": true,
  "missing_fields": ["Results"],
  "critical_issues": ["References 存在 unknown/匿名作者"],
  "recommendations": ["先导入文献库再生成报告，确保 References 可追溯"],
  "references_verified": 3,
  "has_real_data_plots": false,
  "has_actual_or_simulated_results": false
}
```

前端 [QualityCheckCard](frontend/src/components/QualityCheckCard.tsx) 展示评分、缺失字段、关键问题和改进建议。

---

## 🔍 端到端验收

```bash
python scripts/check_e2e.py
```

检查项（14 项）：

```
[PASS] 后端健康检查 (/health)
[PASS] 千问客户端诊断 (/health/llm)
[PASS] 项目列表 (/api/v1/projects)
[PASS] 文献源列表 (/api/v1/literature/sources)
[PASS] arXiv 论文搜索
[PASS] 数据集列表 (/api/v1/datasets)
[PASS] Pipeline 运行列表
[PASS] Pipeline 状态接口
[PASS] 最新报告 (/api/v1/reports/latest)
[PASS] Agent 接口 (hypotheses / experiment-designs / small-validations)
[PASS] Skills 文件完整性 (10 个核心 Skill)
[PASS] .env 配置文件
```

---

## 🧪 测试

```bash
cd backend
pytest tests/ -v
```

覆盖：Agent 单元测试、Pipeline 端到端、向量存储、数据库、文档解析等。

---

## 📐 前置要求

| 工具 | 版本 |
|------|------|
| Python | 3.10 / 3.11 / 3.12（推荐） |
| Node.js | ≥ 18 |
| pnpm | ≥ 9 |

> ⚠️ 暂不建议 Python 3.13——FAISS、sentence-transformers 等依赖可能存在兼容问题。