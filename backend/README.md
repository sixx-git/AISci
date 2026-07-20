# AI Scientist Backend

基于 FastAPI 的后端服务：多智能体 Pipeline、科研 Skill、Discovery/CQS/HITL/审计链，以及联邦学习 Starter Pack（内容注入）。

主链路为 **7 阶段**（含 `iterative_experiment`，取代独立实验设计 + 小样验证 HTTP 面）。

## 目录结构

```
backend/
├── app/
│   ├── api/              # API 路由（由 v1.py 汇总挂载）
│   │   ├── projects.py, literature.py, documents.py, agents.py
│   │   ├── pipeline.py, iterative_experiments.py, reports.py
│   │   ├── feedback.py, human_loop.py, prompts.py, skills.py
│   │   ├── pingfenbiao_proxy.py, science_iteration.py
│   │   ├── vector_search.py, diagnose.py, llm_config.py
│   │   ├── research.py, chat.py   # 保留文件，默认未挂入对外 OpenAPI 主面
│   │   └── v1.py
│   ├── agents/           # 问题理解 / 文献 / 缺口 / 假设生成与评审 / 报告等
│   ├── core/             # 配置、CQS、verifiable spec、溯源、可执行性 Gate 等
│   ├── models/ / schemas/
│   ├── services/         # pipeline、iterative_experiment、fl_pack、evidence、feedback…
│   ├── integrations/     # shaxiang 桥接等
│   ├── skills/           # 科研 Skill（见下方）
│   └── main.py
├── prompts/              # 阶段 Prompt + presets/（见 prompts/README.md）
├── scripts/              # generate_fl_starter_pack.py、generate_prompt_presets.py 等
├── tests/                # pytest（含 test_batch*、test_fl_starter_pack）
├── data/                 # DB / arXiv fallback / reference/fl（FL Pack）
└── storage/              # 运行时向量、上传、报告等
```

## Skill 分类

| 目录 | 说明 |
|------|------|
| `skills/literature/` | 论文搜索、引用验证、PDF 证据提取 |
| `skills/data_finder/` | PDF 表格抽取、Schema 对齐、Merge、Entity 对齐（服务层；对外 Data Finder HTTP 已下线） |
| `skills/evidence_reasoning/` | 证据检索、假设修订、证据链构建 |
| `skills/multimodal/` | VLM 图像理解、多模态 evidence |
| `skills/data/` | 数据清洗、统计描述、数据集发现 |
| `skills/report/` | 科学图表、VLM 图表评审、报告质量检查 |
| `skills/reasoning/` | 新颖性审查、问题对齐、Ideation |
| `skills/experiment/` | 实验合理性检查 |
| `skills/counterfactual/` | 反事实预演（L0） |
| `skills/academic/` / `chinese_writing/` / `modeling/` | 学术写作与建模辅助 |
| `data/reference/fl/` | **联邦学习 Starter Pack v1.4+**（非 skill；非多机 runtime） |

> 已移除：`skills/federated_experiment/`、`skills/knowledge_graph/` 目录。旧联邦能力改为 Pack 内容注入。

## 闭环相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/pipeline/run` | 启动 Pipeline |
| GET | `/api/v1/pipeline/audit-export/{run_id}` | 导出审计链 |
| POST | `/api/v1/pipeline/rerun-from-stage` | 从指定阶段重跑 |
| GET | `/api/v1/agents/hypotheses/{id}/evidence-chain` | 结构化证据链 |
| POST | `/api/v1/agents/hypotheses/{id}/evidence-chain/iterate` | 证据链迭代修正 |
| GET | `/api/v1/agents/hypotheses/{id}/provenance-timeline` | 假设溯源时间线 |
| * | `/api/v1/iterative-experiments/*` | 迭代实验 CRUD / 运行 |
| GET | `/api/v1/projects/{id}/fl-pack/scripts` | FL 参考脚本模板 |
| POST | `/api/v1/projects/{id}/iterative-experiments/{eid}/apply-fl-script` | 一键写入 analysis_script |
| POST | `/api/v1/feedback/submit` | Feedback Hub 约束 |
| GET/POST | `/api/v1/pingfenbiao/*` | 预测服务 BFF |

> `datasets` / `data_finder` / `kg` / `multimodal` 独立路由文件已删除；相关逻辑若仍存在，多在 `services/` 与 Pipeline 内部调用。

## 持久化目录

除 `backend/storage/` 外，项目根目录 `storage/` 还包含：

| 路径 | 内容 |
|------|------|
| `storage/audit/{run_id}.jsonl` | Pipeline 闭环审计链 |
| `storage/evidence_chains/{project_id}/` | 假设证据链 JSON |
| `storage/catalog/{project_id}/` | Data Catalog（若使用） |
| `storage/data_finder/{project_id}/` | Data Finder 结果与 Bundle（若使用） |

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
AISCI_FL_PACK_ENABLED=true
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

阶段顺序执行，每个阶段记录 input/output、Prompt、模型参数、Token 用量与耗时。Discovery 模式下支持多轮迭代，并写入：

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

# 联邦 Pack
pytest tests/test_fl_starter_pack.py -q
```

| 测试文件 | 覆盖 |
|----------|------|
| `test_batch1_quality_hitl.py` | CQS、HITL Gate、execution_tier |
| `test_batch2_verifiable_spec.py` | verifiable spec、证据 Diff |
| `test_batch3_data_finder.py` | 清洗、Coverage、Bundle |
| `test_batch4_closed_loop.py` | Decision Log、停滞停止、因果链 |
| `test_batch5_literature_figures.py` | 图表抽取、文献入库 |
| `test_batch6_feedback_catalog.py` | Feedback Hub、Catalog、Entity 对齐 |
| `test_batch7_provenance_audit.py` | 溯源时间线、审计链、citation 追溯 |
| `test_fl_starter_pack.py` | FL Pack 挂载、领域过滤、标准 Non-IID、Dirichlet/baseline 脚本 |

详见 [tests/README.md](./tests/README.md)。

## 联邦学习 Starter Pack

定位：**内容注入**（文献种子 / 数据集元数据 / 实验范式 / 单机 pilot），**不是** Flower/FATE 多机部署。

| 路径 | 说明 |
|------|------|
| `data/reference/fl/` | Pack 根目录（manifest v1.4+） |
| `data/reference/fl/experiment_paradigms/` | 默认档位 `standard_non_iid`（Dirichlet + FedProx） |
| `data/reference/fl/scripts/` | 含 `hfl_dirichlet_partition.py`、`hfl_baseline_compare_pilot.py` |
| `app/services/fl_pack_service.py` | 加载、挂载、`experiment_paradigm_context` |
| `prompts/presets/pack_d/` | 联邦专用三阶段 Prompt |

**使用方式**

1. 前端创建项目 → 模式「联邦学习」→ 实验档位默认「标准 Non-IID」
2. 系统写入 `project.config.fl_pack` 并自动应用 pack_d
3. 迭代实验详情 → **FL 参考脚本模板** → 一键写入 `analysis_script`

```bash
# 重新生成 Pack
python scripts/generate_fl_starter_pack.py

# 摘要
python -c "from app.services.fl_pack_service import get_fl_pack_service; print(get_fl_pack_service().summary())"
```

文档：[FL_STARTER_PACK.md](../docs/FL_STARTER_PACK.md)、[FL_EXPERIMENT_PARADIGMS.md](../docs/FL_EXPERIMENT_PARADIGMS.md)。

## 更多信息

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [数据库设计文档](./DATABASE.md)
- [Prompt 模板索引](./prompts/README.md)
- [LaTeX / PDF 导出](../LATEX_EXPORT_SETUP.md)
- [项目根目录 README](../README.md)
