# [AISci] - 基于 Qwen 的智能科研助手

<p align="center">
  <b>挑战杯 XH-202619</b> |
  基于国产开源大模型的 AISci 多智能体科研系统
</p>

---

## 📋 项目简介

基于 **Qwen/千问**大模型开发的 **AISci** 多智能体科研系统原型。从文献 / 数据输入到可验证科学假设输出，全流程自动化。

### 核心流程

```
研究问题 → 文献挖掘 → 知识缺口 → 假设生成 → 假设评估 → 迭代实验 → 报告生成
                              ↑_________________________________________|
                                    科研闭环（Discovery 迭代 / HITL / CQS）
```

标准 Pipeline 为 **7 阶段**（`iterative_experiment` 取代原实验设计 + 小样验证）。系统另支持 **Discovery 多轮迭代**、**HITL 人工审核 Gate**、**综合质量分 CQS（0–100）**、**完整审计链导出**，以及顶栏 **预测**（基于 pingfenbiao 的评分表 / 科学影响力预测）。

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
| http://localhost:3000/predict | 预测（评分表 / 影响力；需另启 pingfenbiao :8765） |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |

### 🌐 内网渗透（公网访问）

如需让其他人从公网访问本地项目，可使用 **Cloudflare Tunnel**：

#### 安装 Cloudflare Tunnel

```bash
# Windows
winget install cloudflare.cloudflared

# 安装后刷新 PATH
$env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

#### 启动内网穿透

```bash
# 启动前端和后端后，新开终端执行
cloudflared tunnel --url http://localhost:3000
```

启动后会输出类似以下的公网地址：

```
2026-07-17T08:00:00Z INF +--------------------------------------------------------------------------------------------+
2026-07-17T08:00:00Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-07-17T08:00:00Z INF |  https://xxx-xxx-xxx-xxx.trycloudflare.com                                                 |
2026-07-17T08:00:00Z INF +--------------------------------------------------------------------------------------------+
```

#### Vite 配置

确保 `frontend/vite.config.ts` 中已配置允许外部访问：

```typescript
server: {
  host: '0.0.0.0',        // 监听所有接口
  port: 3000,
  allowedHosts: true,     // 允许所有域名访问（内网穿透必需）
}
```

#### 注意事项

| 事项 | 说明 |
|------|------|
| **临时地址** | 每次启动会生成新地址，关闭终端后失效 |
| **HTTPS** | Cloudflare 自动配置 HTTPS，公网访问为安全连接 |
| **延迟** | 通过 Cloudflare 中转，公网访问延迟约 100–200ms |
| **稳定性** | 免费试用模式，适合临时分享和测试 |
| **长期使用** | 建议注册 Cloudflare 账号并创建命名隧道 |

#### 预测 Tab（pingfenbiao）

顶栏 **首页 → 预测 → 文献**。页面复刻 pingfenbiao：侧栏历史 + 三 Tab（生成评分表 / 报告打分 / 科学影响力预测）+ 详情四面板。

- 独立服务默认监听 `127.0.0.1:8765`
- 前端经 AISci 后端 BFF：`/api/v1/pingfenbiao/*` → `:8765/*`（走现有 `/api` 代理，不依赖 Vite 专用 `/pingfenbiao` 反代）
- 需同时启动：**AISci 后端 :8000** + **pingfenbiao :8765** + **前端 :3000**

```batch
# 新开终端（需 DASHSCOPE_API_KEY，可写在 pingfenbiao-main/pingfenbiao-main/.env）
scripts\run_pingfenbiao.bat
```

```bash
cd pingfenbiao-main/pingfenbiao-main/web
pip install -r requirements.txt   # 首次；另需各 rubric-auto-gen*/requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8765
```

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
│   │   ├── agents/               # 各阶段智能体（独立类 + Prompt + JSON Schema）
│   │   │   ├── problem_understanding_agent.py
│   │   │   ├── literature_mining_agent.py
│   │   │   ├── knowledge_gap_agent.py
│   │   │   ├── hypothesis_generation_agent.py
│   │   │   ├── hypothesis_review_agent.py
│   │   │   └── report_generation_agent.py
│   │   │   # 迭代实验：services/iterative_experiment_service.py + integrations/shaxiang/
│   │   ├── api/                  # API 路由（v1.py 汇总挂载）
│   │   │   ├── projects.py, literature.py, agents.py, pipeline.py, reports.py
│   │   │   ├── documents.py, iterative_experiments.py, pingfenbiao_proxy.py
│   │   │   ├── feedback.py, human_loop.py, prompts.py, skills.py
│   │   │   ├── science_iteration.py, vector_search.py, diagnose.py, llm_config.py
│   │   │   # 未挂载（保留文件）：research.py / chat.py / datasets.py / data_finder.py 等
│   │   ├── core/                 # 配置、闭环控制、质量评分、溯源
│   │   │   ├── quality_scoring.py, iterative_science.py, data_cleaning.py
│   │   │   ├── closed_loop_decisions.py, hypothesis_provenance.py, data_citation.py
│   │   ├── models/               # SQLAlchemy 模型（project / core / pipeline 等）
│   │   ├── schemas/              # Pydantic 请求/响应 Schema
│   │   ├── services/             # 业务逻辑 + Qwen 客户端 + 向量存储
│   │   │   ├── pipeline_service.py, iterative_experiment_service.py
│   │   │   ├── evidence_reasoning_service.py, data_finder_service.py
│   │   │   ├── feedback_hub_service.py, audit_chain_service.py
│   │   ├── integrations/         # 外部系统桥接（如 shaxiang）
│   │   ├── skills/               # 科研 Skill 工具层（40+）
│   │   │   ├── literature/       # 论文搜索、引用验证、PDF 证据提取
│   │   │   ├── data_finder/      # 表格抽取、Schema 对齐、Merge、Entity 对齐
│   │   │   ├── evidence_reasoning/ # 证据链迭代、假设修订、引用完整性
│   │   │   ├── multimodal/       # VLM 图像理解、多模态证据构建
│   │   │   ├── knowledge_graph/  # KG 构建、推理、增量更新
│   │   │   ├── federated_experiment/ # 联邦学习场景识别与仿真
│   │   │   ├── data/             # 数据清洗、数据集发现
│   │   │   ├── report/           # 图表生成、VLM 评审、质量检查
│   │   │   ├── reasoning/        # 新颖性审查、问题对齐、Ideation
│   │   │   ├── counterfactual/   # 反事实预演（L0）
│   │   │   └── experiment/       # 实验合理性检查
│   │   └── main.py               # FastAPI 入口 + /health + /health/llm
│   ├── prompts/                  # 阶段 Prompt 模板 + presets/ 范式预设库（见 prompts/README.md）
│   ├── scripts/                  # generate_prompt_presets.py 等工具脚本
│   ├── tests/                    # pytest 测试
│   ├── data/                     # arXiv fallback 数据
│   └── storage/                  # 运行时数据（见 storage/README.md）
├── pingfenbiao-main/              # 评分表 / 科学影响力预测（独立 Web :8765，顶栏「预测」）
├── shaxiang-main/                # 迭代实验上游实现（桥接用，通常 gitignore）
├── storage/                      # 项目级持久化（audit / catalog / evidence_chains 等）
├── docs/                         # 专题文档（如 DATA_ACQUISITION.md）
├── designs/                      # Pencil UI 设计稿（*.pen，与前端代码同仓版本管理）
├── frontend/
│   └── src/
│       ├── components/           # 工作流、迭代实验、predict/ 预测页等
│       ├── pages/                # Home、Predict、Documents、Reports、ProjectWorkspace 等
│       ├── services/             # pipelineService、predictService、iterativeExperimentService 等
│       ├── types/                # TypeScript 类型定义
│       ├── lib/                  # 工具函数（api.ts、utils.ts）
│       └── config/               # projectTabs、pipelineStageNavigation、promptStages 等
├── scripts/
│   ├── setup_backend.bat/sh      # 后端环境搭建（venv + pip install）
│   ├── setup_frontend.bat/sh     # 前端环境搭建（pnpm install）
│   ├── run_dev.bat/sh            # 一键启动前后端
│   ├── run_pingfenbiao.bat       # 启动预测服务（:8765）
│   ├── start_backend.bat/sh      # 仅启动后端
│   ├── init_db.py                # 数据库建表脚本
│   └── check_e2e.py              # 端到端验收脚本
├── .env.example                  # 环境变量模板
├── QUICKSTART.md                 # 详细快速入门
├── LATEX_EXPORT_SETUP.md         # LaTeX 报告导出
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

| Agent / 阶段 | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| **ProblemUnderstanding** | 研究问题文本 | 问题陈述、领域、关键词、边界 | 将模糊问题转化为可研究的结构化描述 |
| **LiteratureMining** | project_id + 研究问题 | 科学事实 + 证据列表 + 引用映射 | FAISS 检索 → Qwen 提取事实，每条绑定 chunk_id |
| **KnowledgeGap** | 文献事实 + 不确定点 | 知识缺口、矛盾、研究机会 | 发现文献中的空白和可研究方向 |
| **HypothesisGeneration** | 知识缺口 + 文献证据 | 候选假设 + 对齐评分 + 数据证据 | 基于缺口生成可验证假设，标注 supporting_fact_ids |
| **HypothesisReview** | 候选假设 + 文献上下文 | 新颖性评分、可行性评估、反事实预演 | 评估假设质量；可选 L0 CounterfactualPreview |
| **IterativeExperiment** | 主假设 + 数据集绑定 | 脚本设计、smoke/full 迭代、图表与反馈重设计 | 对接 shaxiang；嵌套投影 `experiment_design` / `small_validation` 供报告与溯源 |
| **ReportGeneration** | 全流程中间产物（只读迭代实验投影） | 12 字段最终报告 + 合规检查 | 聚合各阶段输出，生成完整报告 |

> 历史阶段 `experiment_design` / `small_validation` / `data_acquisition` 已淘汰出主链路；新 run 以 `iterative_experiment` 为准。观测/溯源/Feedback 重跑经 `resolve_ed_sv_from_results` 优先读新格式、兼容旧顶层键。

每个 Agent 的特点：
- **独立类** — 可单独实例化和测试
- **Prompt 模板** — `backend/prompts/*.md`，独立于代码，方便调优
- **JSON Schema 约束** — Pydantic 模型确保输出类型安全
- **来源绑定** — 所有事实和引用 traceable 到原始文献

### Prompt 范式预设库

除各阶段默认 Prompt 外，`backend/prompts/presets/` 提供多套可一键应用的科研范式（**不含 `report_generation`**，报告固定 12 章模板）：

| 包 ID | 说明 |
|-------|------|
| `pack_a` | AI Scientist v1：想法 → 代码 → 运行 → 评审 |
| `pack_b` | AI Scientist v2：树搜索、剪枝、pilot 门禁 |
| `pack_c` | AISci 默认：证据溯源 + 可验证假设（**推荐新项目**） |
| `pack_d` | 联邦学习（仅 `federated_learning` 项目可见） |

API：`GET /api/v1/prompts/presets/catalog`、`POST /api/v1/prompts/presets/apply`  
前端：项目工作台 **Prompt 管理** Tab + 工作流阶段 **PromptPresetBar**

---

## 🖥️ 前端信息架构

| 入口 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 项目搜索、筛选与列表 |
| **预测** | `/predict` | 评分表生成 / 报告打分 / 科学影响力预测（经 BFF → pingfenbiao） |
| 文献 | `/documents` | 文献上传、arXiv 检索与导入 |
| 报告 | `/reports` | 研究报告浏览与导出 |
| Skills | `/skills` | Skill 启用与目录 |
| 项目工作台 | `/projects/:id` | 多 Tab 科研全流程 |

`/projects`、`/workflow`、`/settings` 已重定向至 `/`。LLM 配置在顶栏 **DeveloperMenu**（不再单独 Settings 页）。

**项目工作台主 Tab**（`frontend/src/config/projectTabs.ts`）：项目概览 · 研究问题 · 文献库 · 智能体工作流 · 候选假设 · **迭代实验** · 研究报告  

高级深链：Prompt 管理 · 运行日志（数据绑定仅在「迭代实验」内完成）

---

## 🔬 Skill 工具层

Skill 作为 Agent 调用的工具层，按子领域组织（完整列表见 `backend/app/skills/`）：

| 分类 | 代表 Skill | 功能 |
|------|-----------|------|
| **文献** | arxiv_search_skill, citation_grounding_skill | 多源检索、引用真实性验证 |
| **Data Finder** | pdf_table_extraction_skill, dataset_merge_skill, entity_resolution_skill | PDF 表格抽取、Merge + provenance、跨表实体对齐 |
| **证据推理** | iterative_hypothesis_loop_skill, hypothesis_revision_skill | 多轮证据检索、LLM 假设修订（fact 白名单） |
| **多模态** | qwen_vl_image_understanding_skill, multimodal_evidence_builder_skill | VLM 图像理解、多模态 fact 构建 |
| **知识图谱** | evidence_graph_builder_skill, graph_reasoning_skill | 证据图构建与推理 |
| **联邦实验** | federated_experiment_plan_skill, federated_simulation_executor_skill | 联邦场景识别、仿真与重规划 |
| **数据** | data_juicer_lite_skill, preliminary_analysis_skill | 数据质量分析与统计描述 |
| **推理** | hypothesis_novelty_review_skill, ideation_novelty_skill | 新颖性审查、Ideation 合成 |
| **报告** | scientific_plot_skill, plot_vlm_critique_skill, report_quality_check_skill | 图表生成、VLM 评审、12 字段合规检查 |
| **实验** | experiment_sanity_check_skill | 实验方案合理性检查 |

---

## 🔄 科研闭环与 A 级优化

系统在标准 Pipeline 之上实现了多批 A 级优化能力：

| 批次 | 主题 | 要点 |
|------|------|------|
| **1** | CQS + HITL Gate | 综合质量分 0–100、`execution_tier` 标注、人工审核暂停/恢复 |
| **2** | Verifiable Spec | 通用可验证假设 spec、证据 Diff、可验证性检查 |
| **3** | DataJuicer + Coverage + Bundle | 合并后自动清洗、完备性报告、Analysis-Ready Bundle 下载 |
| **4** | Decision Log + 停滞停止 | 闭环决策记录、CQS 停滞停止、Discovery 因果链、Gap/HF 补搜 |
| **5** | 图表分层 + 文献自动入库 | 图表 VLM 抽取/复核、Zenodo/NCBI GEO 检索、文献库 ↔ Data Finder |
| **6** | Feedback Hub + Catalog | 全局约束注入、Multimodal → 证据链、Data Catalog、Entity 对齐 |
| **7** | 溯源 + 审计链 | 假设溯源时间线 Tab、LLM 深度假设修订、审计链 jsonl 导出、`data_citation_id` 追溯 |
| **8** | 数据获取增强 | 外部数据源连接器、补充材料/图表抽取、Release Gate、分阶段集成测试（见 [docs/DATA_ACQUISITION.md](./docs/DATA_ACQUISITION.md)） |
| **9** | Prompt 范式预设 | pack_a/b/c/d 多套预设、项目内 Prompt 管理 Tab、一键应用 API |

### 关键 API（闭环相关）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/pipeline/audit-export/{run_id}` | 导出完整审计链（quality_trend / events / decisions / jsonl） |
| GET | `/api/v1/agents/hypotheses/{id}/provenance-timeline` | 假设溯源时间线（fact → 多模态 → 数据集 → spec） |
| POST | `/api/v1/agents/hypotheses/{id}/evidence-chain/iterate` | 单条假设证据链迭代修正 |
| POST | `/api/v1/feedback/submit` | Feedback Hub 提交全局约束（实验类重跑目标为 `iterative_experiment`） |
| GET/POST | `/api/v1/pingfenbiao/*` | 预测服务 BFF 代理（转发至本机 :8765） |
| * | `/api/v1/iterative-experiments/*` | 项目级迭代实验 CRUD / 运行 / 报告勾选 |

> `datasets` / `data_finder` / `research` / `chat` HTTP 面已下线（服务层可能仍被 Pipeline 内部调用）。单阶段 Agent POST（如 `/agents/problem-understanding`）仍可调用，但默认不出现在 OpenAPI schema。

审计链持久化路径：`storage/audit/{run_id}.jsonl`。

---

## 📊 Pipeline（一键运行）

```bash
POST /api/v1/pipeline/run
```

阶段顺序：`problem_understanding` → `literature_mining` → `knowledge_gap` → `hypothesis_generation` → `hypothesis_review` → `iterative_experiment` → `report_generation`

7 个阶段顺序执行。`iterative_experiment` 负责数据绑定、脚本设计与 smoke/full 迭代；报告阶段从该阶段投影实验方案与结果。每个阶段记录：

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

检查项示例（以 `scripts/check_e2e.py` 当前实现为准）：

```
[PASS] 后端健康检查 (/health)
[PASS] 千问客户端诊断 (/health/llm)
[PASS] 项目列表 (/api/v1/projects)
[PASS] 文献源列表 (/api/v1/literature/sources)
[PASS] arXiv 论文搜索
[PASS] Pipeline 运行列表 / 状态接口
[PASS] 最新报告 (/api/v1/reports/latest)
[PASS] 假设相关 Agent 接口
[PASS] Skills / .env 等完整性检查
```

---

## 🧪 测试

```bash
cd backend
pytest tests/ -v

# A 级优化批次回归（1–7 批）
pytest tests/test_batch1_quality_hitl.py tests/test_batch2_verifiable_spec.py \
       tests/test_batch3_data_finder.py tests/test_batch4_closed_loop.py \
       tests/test_batch5_literature_figures.py tests/test_batch6_feedback_catalog.py \
       tests/test_batch7_provenance_audit.py -v
```

覆盖：Agent 单元测试、Pipeline 端到端、向量存储、闭环质量、Data Finder、溯源审计等。详见 [backend/tests/README.md](./backend/tests/README.md)。

---

## 📐 前置要求

| 工具 | 版本 |
|------|------|
| Python | 3.10 / 3.11 / 3.12（推荐） |
| Node.js | ≥ 18 |
| pnpm | ≥ 9 |

> ⚠️ 暂不建议 Python 3.13——FAISS、sentence-transformers 等依赖可能存在兼容问题。

---

## 🤝 AI 协作（Cursor / Agent 上下文）

在新对话中粘贴以下摘要，可让 Agent 快速理解本仓库（完整版见下方代码块后的说明）：

```
项目：AISci — Qwen 多智能体科研系统（d:\Workplace\AISci）
栈：FastAPI + React/Vite/Tailwind + FAISS + SQLite
Pipeline 7 阶段：问题理解→文献→知识缺口→假设→评估→迭代实验→报告
ed/sv：优先 iterative_experiment 嵌套，resolve_ed_sv_from_results 兼容旧键
闭环：Discovery 迭代 / HITL / CQS / 审计链 storage/audit/{run_id}.jsonl
前端：/ 首页 | /predict 预测(BFF) | /documents 文献 | /reports 报告 | /projects/:id 工作台
关键路径：pipeline_service.py | iterative_experiment_service.py | pingfenbiao_proxy.py | predict/
原则：最小改动、中文回复、禁止虚构引用、不擅自 git commit
任务：（在此填写）
```

**Pencil 设计任务**（需安装 Pencil 扩展并连接 MCP）：设计稿 `designs/aisci-ui.pen`，须用 Pencil MCP 读写（勿直接 Read `.pen` 文件）；风格对齐深色 Tailwind UI（参考 `Home.tsx`、工作流相关组件）。

**建议 Agent 按任务选读**：`README.md` → `backend/DATABASE.md` → `docs/DATA_ACQUISITION.md` → 相关组件/服务源码。

---

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| [QUICKSTART.md](./QUICKSTART.md) | 5 分钟快速入门 |
| [backend/README.md](./backend/README.md) | 后端架构、API、测试 |
| [backend/DATABASE.md](./backend/DATABASE.md) | 数据库表结构与闭环 metadata |
| [docs/DATA_ACQUISITION.md](./docs/DATA_ACQUISITION.md) | 领域数据集发现（默认）与完整数据整合（可选） |
| [backend/prompts/README.md](./backend/prompts/README.md) | Prompt 模板与范式预设索引 |
| [backend/tests/README.md](./backend/tests/README.md) | pytest 与 batch 回归 |
| [frontend/README.md](./frontend/README.md) | 前端组件与页面 |
| [storage/README.md](./storage/README.md) | 审计链、证据链、Data Finder 持久化 |
| [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md) | LaTeX 报告导出与 PDF 回退 |