# AI Scientist Backend

基于 FastAPI 的后端服务，包含 8 个智能体（Agent）、40+ 科研 Skill、8 阶段 Pipeline，以及科研闭环（Discovery 迭代 / CQS / HITL / 审计链）。

## 目录结构

```
backend/
├── app/
│   ├── api/              # API 路由层
│   │   ├── projects.py   # 项目管理
│   │   ├── agents.py     # 智能体 + 假设证据链 + 溯源时间线
│   │   ├── pipeline.py   # Pipeline 运行 + 审计链导出
│   │   ├── data_finder.py # 多源数据查找 + citation 追溯 + Bundle 下载
│   │   ├── feedback.py   # Feedback Hub 全局约束
│   │   ├── human_loop.py # HITL Gate 暂停/恢复
│   │   ├── datasets.py   # 数据集 + Data Catalog
│   │   ├── multimodal.py # 多模态资产
│   │   ├── kg.py         # 知识图谱
│   │   ├── literature.py, documents.py, reports.py, chat.py
│   │   └── v1.py         # v1 路由整合
│   ├── agents/           # 8 个智能体
│   ├── core/             # 核心模块
│   │   ├── config.py, database.py
│   │   ├── quality_scoring.py      # CQS 综合质量分
│   │   ├── iterative_science.py    # verifiable spec、证据 Diff
│   │   ├── closed_loop_decisions.py # 闭环决策记录
│   │   ├── iteration_control.py    # CQS 停滞检测
│   │   ├── hypothesis_provenance.py # 假设溯源时间线
│   │   ├── data_citation.py        # data_citation_id 追溯
│   │   ├── data_cleaning.py        # CSV 清洗
│   │   ├── execution_metadata.py   # execution_tier 标注
│   │   └── plan_executability.py   # 实验计划可执行性 Gate
│   ├── models/           # SQLAlchemy 数据模型
│   ├── schemas/          # Pydantic 请求/响应 Schema
│   ├── services/         # 业务逻辑层
│   │   ├── pipeline_service.py          # Pipeline 编排 + 闭环事件
│   │   ├── evidence_reasoning_service.py # 证据链迭代
│   │   ├── data_finder_service.py       # Data Finder 全流程
│   │   ├── feedback_hub_service.py      # Feedback Hub
│   │   ├── audit_chain_service.py       # 审计链 jsonl 持久化
│   │   ├── data_catalog_service.py      # Data Catalog
│   │   ├── literature_corpus_service.py # 文献自动入库
│   │   ├── closed_loop_quality_service.py
│   │   └── qwen_client.py               # Qwen 客户端
│   ├── skills/           # 科研 Skill 工具层（见下方分类）
│   └── main.py           # FastAPI 入口
├── prompts/              # Markdown Prompt 模板
├── tests/                # pytest 测试（含 test_batch1–7 回归）
├── data/                 # arXiv fallback 数据
└── storage/              # 运行时数据（Zvec 向量库、报告、上传文件）
```

## Skill 分类

| 目录 | 说明 |
|------|------|
| `skills/literature/` | 论文搜索、引用验证、PDF 证据提取 |
| `skills/data_finder/` | PDF 表格抽取、Schema 对齐、Merge、Entity 对齐、外部数据集搜索 |
| `skills/evidence_reasoning/` | 证据检索、立场分类、假设修订（LLM + fact 白名单）、证据链构建 |
| `skills/multimodal/` | VLM 图像理解、音频转写、多模态 evidence 构建 |
| `skills/knowledge_graph/` | KG Schema、关系抽取、图推理、增量更新 |
| `skills/federated_experiment/` | 联邦场景识别、仿真执行、重规划 |
| `skills/data/` | 数据清洗、统计描述、数据集发现 |
| `skills/report/` | 科学图表、VLM 图表评审、报告质量检查 |
| `skills/reasoning/` | 新颖性审查、问题对齐、Ideation |
| `skills/experiment/` | 实验合理性检查 |

## 闭环相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/pipeline/run` | 启动 Pipeline |
| GET | `/api/v1/pipeline/audit-export/{run_id}` | 导出审计链（events / decisions / quality_trend / jsonl） |
| POST | `/api/v1/pipeline/rerun-from-stage` | 从指定阶段重跑 |
| GET | `/api/v1/agents/hypotheses/{id}/evidence-chain` | 获取结构化证据链 |
| POST | `/api/v1/agents/hypotheses/{id}/evidence-chain/iterate` | 证据链迭代修正 |
| GET | `/api/v1/agents/hypotheses/{id}/provenance-timeline` | 假设溯源时间线 |
| POST | `/api/v1/data-finder/search` | Data Finder 搜索 |
| POST | `/api/v1/data-finder/merge` | 合并表格 + provenance + 清洗 + Bundle |
| GET | `/api/v1/data-finder/citation/{citation_id}` | 追溯 data_citation |
| GET | `/api/v1/data-finder/bundle/download` | 下载 Analysis-Ready Bundle |
| POST | `/api/v1/feedback/submit` | 提交 Feedback Hub 约束 |
| GET | `/api/v1/datasets/catalog` | 项目 Data Catalog |

## 持久化目录

除 `backend/storage/` 外，项目根目录 `storage/` 还包含：

| 路径 | 内容 |
|------|------|
| `storage/audit/{run_id}.jsonl` | Pipeline 闭环审计链 |
| `storage/evidence_chains/{project_id}/` | 假设证据链 JSON |
| `storage/catalog/{project_id}/` | Data Catalog |
| `storage/data_finder/{project_id}/` | Data Finder 结果与 Bundle |

详见 [storage/README.md](../storage/README.md)。

## 快速开始

### 1. 环境要求

- Python 3.10 / 3.11 / 3.12（推荐）
- 暂不建议 Python 3.13：部分依赖可能存在兼容问题

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
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max
USE_MOCK_LLM=false
DATABASE_URL=sqlite:///./data/aiscientist.db
VECTOR_STORE_PATH=./storage/chat_vectors
VECTOR_INDEXES_PATH=./storage/vector_indexes
VECTOR_BACKEND=zvec
HF_ENDPOINT=https://hf-mirror.com
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
UPLOAD_DIR=./storage/uploads
```

### 4. 启动服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- LLM 诊断: http://localhost:8000/health/llm

## Pipeline

8 个阶段顺序执行，每个阶段记录 input/output、Prompt、模型参数、Token 用量与耗时。Discovery 模式下支持多轮迭代，并写入：

- `extra_metadata.quality_trend` — CQS 质量趋势
- `extra_metadata.closed_loop_events` — 闭环事件
- `extra_metadata.closed_loop_decisions` — 闭环决策
- `storage/audit/{run_id}.jsonl` — 完整审计链

## 测试

```bash
cd backend
pytest tests/ -v

# A 级优化批次回归
pytest tests/test_batch*.py -v
```

| 测试文件 | 覆盖 |
|----------|------|
| `test_batch1_quality_hitl.py` | CQS、HITL Gate、execution_tier |
| `test_batch2_verifiable_spec.py` | verifiable spec、证据 Diff |
| `test_batch3_data_finder.py` | 清洗、Coverage、Bundle |
| `test_batch4_closed_loop.py` | Decision Log、停滞停止、因果链 |
| `test_batch5_literature_figures.py` | 图表抽取、文献入库、live API |
| `test_batch6_feedback_catalog.py` | Feedback Hub、Catalog、Entity 对齐 |
| `test_batch7_provenance_audit.py` | 溯源时间线、审计链、citation 追溯 |

详见 [tests/README.md](./tests/README.md)。

## 更多信息

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [数据库设计文档](./DATABASE.md)
- [Prompt 模板索引](./prompts/README.md)
- [LaTeX / PDF 导出](../LATEX_EXPORT_SETUP.md)
- [项目根目录 README](../README.md)
