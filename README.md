# AISci — 基于 Qwen 的多智能体科研自动化系统

<p align="center">
  <b>基于国产大模型 Qwen 的多智能体科研系统</b> |
  全流程自动化：从研究问题到可验证科学假设与实验报告
</p>

---

## 项目简介

AISci 是基于 **Qwen/千问** 大模型构建的多智能体科研自动化系统。系统通过 7 阶段标准化 Pipeline，将科研流程从研究问题出发，经文献挖掘、知识缺口分析、假设生成与评审、迭代实验验证，最终生成结构化研究报告，实现从问题到结论的全流程自动化。

核心流程：

```
研究问题 → 文献挖掘 → 知识缺口 → 假设生成 → 假设评审 → 迭代实验 → 报告生成
```

标准 Pipeline 为 7 阶段顺序执行，由 **CoordinatorAgent（大家长 Agent）** 全程协调，支持人工审核 Gate（HITL）、综合质量分（CQS）、完整审计链导出等能力。大家长 Agent 贯穿全流程，提供 Agent 间记忆管理、端到端全局跟踪、报告内容质量自动修复、预设错误规则主动拦截等能力。

迭代实验默认对接 **shaxiang** 沙箱引擎（`AISCI_USE_SHAXIANG=true`）；报告导出走 LaTeX/PDF，并经正文净化与证据对齐护栏，保证摘要/指标/引用与实测一致。

---

## 三大核心创新机制

### 创新一：多轮证据链迭代机制

**问题背景**：现有 AI 科研辅助流程通常将文献检索、观点生成和论文撰写串联处理，信息在长上下文中逐步传递，容易出现事实混淆、引用失配和证据链断裂，导致最终结论难以追溯。

**解决方案**：系统在每次运行过程中动态提取文献中的结构化知识，形成带有来源标识的 **Fact 白名单**。各智能体在涉及科学事实和引用的环节均依托 Fact 白名单开展推理、假设生成与报告撰写。当证据不足或出现知识缺口时，系统可自动触发文献挖掘补充新的 Fact，或通过沙箱实验获得新的验证结果。对于证据级别为 low 的假设，系统还可自动触发证据链迭代进行修订。

| 环节 | 实现模块 | 说明 |
|------|----------|------|
| Fact 提取 | `LiteratureMiningAgent` | 从文献中提取结构化知识，每条 Fact 绑定唯一 `fact_id` 和 `source_chunk_id` |
| Fact 白名单校验 | `HypothesisGenerationAgent` | 验证引用仅指向真实存在的 fact，确保假设不虚构引用 |
| 证据不足检测 | `CoordinatorAgent` + `PipelineService` | 大家长 Agent 检测证据是否充足，不足时触发自动补救或提示用户 |
| 自动证据链迭代 | `PipelineService` | 低证据假设自动触发迭代修订 |
| 沙箱验证 | `IterativeExperimentService` + shaxiang | smoke/full 运行模式，产出指标与图表供报告引用 |
| 证据链迭代 | `evidence_reasoning_service` + `hypothesis_provenance` | 多轮证据推理与假设溯源 |
| 审计追踪 | `audit_chain_service` | 记录完整的审计链，支持回放与复核 |

数据流向：
```
文献 → Fact 白名单 → 假设生成(引用 fact_id) → 假设评审 → 迭代实验(验证) → 事实回填
                                                                         ↓
                                                                  证据不足? → 补充文献挖掘 → 新增 Fact → 重新生成假设
```

---

### 创新二："知识库对齐"与"小样本测试"驱动的双重过滤机制

**问题背景**：在假设生成和实验方案设计阶段，缺乏有效的前置验证机制，导致缺乏事实依据的假设或难以执行的实验方案进入正式流程，浪费时间和算力。

**解决方案**：系统通过知识证据约束与实验可执行性预检的双重过滤，在正式实验前排除缺乏依据或难以执行的方案。

**过滤器 1：知识库对齐过滤器**
- 以 Fact 白名单作为评价假设的核心证据，假设必须能够回溯到有效 Fact
- `HypothesisGenerationAgent` 自动标注 `evidence_level`（low/medium/high），基于 supporting_fact_ids 数量
- `HypothesisReviewAgent` 对偏题假设扣分，排除偏题和低证据假设
- 无事实依据的假设标记为"不通过"，进入修订流程

**过滤器 2：小样本预检过滤器**
- 识别数据集元数据和字段结构，在正式运行前生成小规模测试数据集，执行 LLM 生成的实验脚本
- `IterativeExperimentService` 支持 `smoke_only` 模式：生成小规模测试集并执行脚本
- 脚本运行失败、输出不符合预期、方案未体现假设可验证性 → 驳回并触发重新生成

双重过滤流程：
```
假设生成 → [知识库对齐] → 通过? → [小样本预检] → 通过? → 正式实验
                        ↓                ↓                  ↓
                       驳回            驳回            驳回
                        ↓                ↓                  ↓
                   假设修订         脚本重设计        方案重生成
                        ↓                ↓                  ↓
                   ←─────────────────────────────────────────→
                             反馈约束注入
```

---

### 创新三：大家长 Agent — 全局协调、质量管控与自动修复

**问题背景**：流水线式多智能体工作流中容易出现记忆漂移、单点割裂、AI 生成「机器味」、错误被动响应等问题。

**解决方案**：由 **CoordinatorAgent（大家长 Agent）** 承担全局协调者角色，贯穿 7 阶段 Pipeline，实现：

1. **线性工作流的智能交接与记忆管理** — 项目上下文、Fact 白名单快照、假设版本、门禁结果、`check_project_readiness()`
2. **端到端全局跟踪** — `suggest_stage_strategy()`、停滞检测、闭环决策记录、前端 Hint 面板
3. **报告内容质检** — 乱码 / 截断 / 标点重复 / LaTeX 转义残留检测与自动修复
4. **预设规则 + LLM 兜底** — 覆盖 7 阶段的预定义错误规则，未匹配时异步开放性分析

报告侧另有 `report_content_sanitizer`：剥离平台运维措辞、摘要与实测证据对齐、参考文献 GB/T 格式化；禁止编造 References。

协调流程概要：
```
研究问题 → [大家长：上下文初始化] → …各阶段检查/补救…
        → 迭代实验（shaxiang / 停滞告警）
        → 报告生成（内容质检 + 净化/证据对齐 + LaTeX/PDF）
        → 审计链导出
```

---

## 快速开始

**详细分步说明**请查看 [QUICKSTART.md](./QUICKSTART.md)。

### Windows

```batch
scripts\setup_backend.bat          # 项目根目录 venv + 安装 backend\requirements.txt
scripts\setup_frontend.bat         # pnpm install

# 复制 .env.example → backend\.env 并填入 QWEN_API_KEY
# 如暂无 API Key，设置 USE_MOCK_LLM=true 可跑通完整流程

scripts\run_dev.bat                # 启动后端 :8000 + 前端 :5173
# 若需「预测」Tab，可用：scripts\launch_stack.bat full
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
| http://localhost:5173 | 前端界面 |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |
| http://localhost:5173/predict | 预测 Tab（需另启 pingfenbiao :8765） |

### 端到端验收

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端（项目根目录）
python scripts/check_e2e.py
```

---

## 技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | React 18 + Vite 5 + TypeScript + TailwindCSS 3 |
| UI 图标 | lucide-react |
| 图表 | recharts |
| 数据库 | SQLite（默认） / MySQL / PostgreSQL（可选；云端可接 Supabase） |
| ORM | SQLAlchemy 2.0 |
| 向量检索 | **zvec**（默认）/ 兼容检测旧 FAISS 索引 |
| 嵌入模型 | Sentence-Transformers（本地）或 DashScope `text-embedding-v3` |
| 大模型 | Qwen（阿里云百炼 / DashScope，默认 `qwen3.6-plus`） |
| 迭代实验 | shaxiang 沙箱引擎（`shaxiang-main/`） |
| 影响力预测 | pingfenbiao（独立服务 :8765，经后端 BFF） |
| PDF / 报告 | PyMuPDF + LaTeX（XeLaTeX）导出 |
| 包管理器 | 后端 pip（根目录 `venv`）+ 前端 pnpm |

---

## 智能体架构

| Agent / 阶段 | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| **ProblemUnderstanding** | 研究问题文本 | 问题陈述、领域、关键词、边界 | 将模糊问题转化为可研究的结构化描述 |
| **LiteratureMining** | project_id + 研究问题 | 科学事实 + 证据列表 + 引用映射 | 向量检索 → Qwen 提取事实，每条绑定 chunk_id |
| **KnowledgeGap** | 文献事实 + 不确定点 | 知识缺口、矛盾、研究机会 | 发现文献中的空白和可研究方向 |
| **HypothesisGeneration** | 知识缺口 + 文献证据 | 候选假设 + 对齐评分 + 数据证据 | 基于缺口生成可验证假设，标注 supporting_fact_ids |
| **HypothesisReview** | 候选假设 + 文献上下文 | 新颖性评分、可行性评估、反事实预演 | 评估假设质量；支持反事实预演 |
| **IterativeExperiment** | 主假设 + 数据集绑定 | 脚本设计、smoke/full 迭代、图表与反馈重设计 | 对接 shaxiang；投影供报告与溯源 |
| **ReportGeneration** | 全流程中间产物 | 12 字段最终报告 + 合规检查 + PDF | 聚合各阶段输出；净化与证据对齐后导出 |
| **CoordinatorAgent** | 各阶段快照 | Hint / 补救决策 / 内容修复 | 全局协调、质检、自动修复 |

每个 Agent 的特点：
- **独立类** — 可单独实例化和测试
- **Prompt 模板** — `backend/prompts/` 独立于代码，方便调优
- **JSON Schema 约束** — Pydantic 模型确保输出类型安全
- **来源绑定** — 所有事实和引用可追溯至原始文献

### Prompt 范式预设库

`backend/prompts/presets/` 提供多套可一键应用的科研范式：

| 包 ID | 说明 |
|-------|------|
| `pack_a` | AI Scientist v1：想法 → 代码 → 运行 → 评审 |
| `pack_b` | AI Scientist v2：树搜索、剪枝、pilot 门禁 |
| `pack_c` | AISci 默认：证据溯源 + 可验证假设（推荐通用新项目） |
| `pack_d` | 联邦学习：Starter Pack + 实验范式；仅 `federated_learning` 项目可见 |

---

## 前端信息架构

| 入口 | 路径 | 说明 |
|------|------|------|
| 首页 | `/` | 项目搜索、筛选与列表 |
| 新建项目 | `/projects/new` | 通用 / 联邦学习模式 |
| 预测 | `/predict` | 评分表生成 / 报告打分 / 科学影响力预测（BFF → pingfenbiao） |
| 文献 | `/documents` | 文献上传、arXiv 检索与导入 |
| 报告 | `/reports` | 研究报告浏览与导出 |
| Skills | `/skills` | Skill 启用与目录 |
| 项目工作台 | `/projects/:id` | 多 Tab 科研全流程 |

**项目工作台主 Tab**：项目概览 · 研究问题 · 文献库 · 智能体工作流 · 候选假设 · 迭代实验 · 研究报告  
**高级深链 Tab**（顶栏不展示）：Prompt 管理 · 运行日志

首次打开会显示欢迎须知弹窗（`WelcomeNoticeModal`）。

---

## Skill 工具层

Skill 作为 Agent 调用的工具层，按子领域组织（完整列表见 `backend/app/skills/`）：

| 分类 | 代表 Skill | 功能 |
|------|-----------|------|
| 文献 | arxiv_search_skill, citation_grounding_skill | 多源检索、引用真实性验证 |
| Data Finder | pdf_table_extraction_skill, dataset_merge_skill | PDF 表格抽取、跨表实体对齐 |
| 证据推理 | iterative_hypothesis_loop_skill, hypothesis_revision_skill | 多轮证据检索、LLM 假设修订 |
| 多模态 | qwen_vl_image_understanding_skill | VLM 图像理解、多模态 fact 构建 |
| 联邦学习 | `backend/data/reference/fl/` + pack_d | 预解析文献/数据集/实验范式；单机模拟 |
| 数据 | data_juicer_lite_skill, preliminary_analysis_skill | 数据质量分析与统计描述 |
| 推理 | hypothesis_novelty_review_skill | 新颖性审查、Ideation 合成 |
| 报告 | scientific_plot_skill, report_quality_check_skill, iteration_narrative_skill | 图表、VLM 评审、迭代叙事、合规检查 |
| 实验 | experiment_sanity_check_skill | 实验方案合理性检查 |

---

## 联邦学习模式（Starter Pack）

创建项目时选择**联邦学习（资源包）**，Pipeline 阶段与通用模式相同，差异来自内容注入与可选仿真：

| 能力 | 说明 |
|------|------|
| 资源包 | `backend/data/reference/fl/`：seed facts、数据集 YAML、checklists、failure cases、实验范式 |
| 默认实验档位 | 标准 Non-IID：Dirichlet α=0.1 + Local / Centralized / FedAvg / FedProx |
| 仿真后端 | `local_pack`（默认）/ Flower / FedML（可选依赖，见 `backend/requirements.txt` 注释） |
| 迭代实验 | 详情页 FL 参考脚本模板 → 后台 job 以模板为反馈，由 LLM 设计/重设计分析脚本 |

---

## 科研闭环与优化能力

系统在标准 Pipeline 之上实现了多批次优化能力：

| 批次 | 主题 | 要点 |
|------|------|------|
| **1** | CQS + HITL Gate | 综合质量分 0–100、执行层级标注、人工审核暂停/恢复 |
| **2** | Verifiable Spec | 通用可验证假设 spec、证据 Diff、可验证性检查 |
| **3** | DataJuicer + Coverage + Bundle | 合并后自动清洗、完备性报告、Analysis-Ready Bundle 下载 |
| **4** | Decision Log + 停滞停止 | 闭环决策记录、CQS 停滞停止、Discovery 因果链、Gap/HF 补搜 |
| **5** | 图表分层 + 文献自动入库 | 图表 VLM 抽取/复核、Zenodo/NCBI GEO 检索、文献库 ↔ Data Finder |
| **6** | Feedback Hub + Catalog | 全局约束注入、Multimodal → 证据链、Data Catalog、Entity 对齐 |
| **7** | 溯源 + 审计链 | 假设溯源时间线、LLM 深度假设修订、审计链 jsonl 导出 |
| **FL** | 联邦学习 Starter Pack | 内容注入 + 可选单机仿真；模板经 LLM 设计脚本 |
| **8** | 数据获取增强 | 外部数据源连接器、补充材料/图表抽取、Release Gate |
| **9** | Prompt 范式预设 | pack_a/b/c/d 多套预设、项目内 Prompt 管理、一键应用 API |
| **报告** | 净化 + 证据对齐 + LaTeX | 摘要/指标/引用护栏；禁止虚构 References；XeLaTeX PDF |

---

## Pipeline（一键运行）

```bash
POST /api/v1/pipeline/run
```

阶段顺序：`problem_understanding` → `literature_mining` → `knowledge_gap` → `hypothesis_generation` → `hypothesis_review` → `iterative_experiment` → `report_generation`

每个阶段记录输入/输出、Prompt、模型参数、Token 用量、耗时与 CallLog。

主要 API 挂载见 `backend/app/api/v1.py`：projects、pipeline、iterative-experiments、literature、reports、human-loop、feedback、skills、pingfenbiao-proxy、fl-simulation 等。

---

## 报告质量检查

`ReportQualityCheckSkill` + `report_content_sanitizer` 对最终报告执行检查与净化：

- 12 字段完整性（Paper Title → References）
- Technical Details 是否明确 Qwen/千问和阿里云百炼
- References 是否可追溯；禁止 unknown / placeholder / 错配 arXiv
- Results 是否区分 actual / simulated / expected；指标键默认保留英文（如 `fixed accuracy`）
- 摘要与 smoke/阶段性/否定性证据同向，不得过度正面包装
- 图表是否有真实数据来源标记
- 是否出现 GPT-4 / Claude / Llama 等非 Qwen 模型表述

---

## 交叉评价机制 — 报告质量「模型对战」评估

在报告生成 Tab 下支持三种评估模式（`ReportEvaluationService` + `ReportQualityEvaluationCard`）：

| 模式 | 定位 |
|------|------|
| **简单提交评估** | 裸 LLM 无预设 |
| **客观加权评分** | 七层加权 rubric（L0–L6） |
| **科学家评分** | PI 人格 + 学术偏好 |

最有信息量的是三种模式之间的**分歧**，而非单一分数。评估结果默认不持久化。

---

## 假设质量保障体系

1. **领域对齐检测** — 过滤偏题假设  
2. **新颖性审查** — `hypothesis_novelty_review_skill`  
3. **锦标赛排序** — Margin-Weighted Tournament  
4. **人工审核** — HITL Gate  

---

## 测试

```bash
cd backend
python -m pytest tests/ -v
# 慢测试排除：python -m pytest tests/ -v -m "not slow"

# A 级优化批次回归
python -m pytest tests/test_batch*.py -v
```

前端：

```bash
cd frontend
pnpm lint
pnpm build
```

---

## 前置要求

| 工具 | 版本 |
|------|------|
| Python | 3.10 / 3.11 / 3.12（推荐；暂不建议 3.13） |
| Node.js | ≥ 18 |
| pnpm | ≥ 9 |
| XeLaTeX（可选） | 用于报告 PDF 编译，见 [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md) |

---

## 配置说明

复制 `.env.example` 为 `backend/.env`（后端优先读此文件），按需修改：

```env
# 千问 API（必需，或开启 USE_MOCK_LLM）
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.6-plus

# Mock LLM（无需真实 API Key 即可跑通 Pipeline）
USE_MOCK_LLM=false

# 数据库（默认 SQLite）
DATABASE_URL=sqlite:///./data/aiscientist.db

# 向量存储（默认 zvec）
VECTOR_BACKEND=zvec
VECTOR_INDEXES_PATH=./storage/vector_indexes
EMBEDDING_BACKEND=sentence_transformers
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# 迭代实验引擎
AISCI_USE_SHAXIANG=true

# CORS（开发前端为 Vite :5173，请按实际前端源配置）
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 获取 Qwen API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 创建 API Key
3. 填入 `backend/.env` 的 `QWEN_API_KEY`

LLM 调用统一走 `backend/app/services/qwen_client.py`（禁止在新代码中直接 `OpenAI()`）。

---

## 项目结构

```
AISci/
├── backend/
│   ├── app/
│   │   ├── agents/               # 阶段智能体 + CoordinatorAgent
│   │   ├── api/                  # 路由（v1.py 汇总挂载）
│   │   ├── core/                 # 配置、闭环控制、质量评分、溯源
│   │   ├── models/               # SQLAlchemy 模型
│   │   ├── schemas/              # Pydantic Schema
│   │   ├── services/             # Pipeline、迭代实验、报告净化、Qwen 客户端等
│   │   ├── integrations/         # shaxiang bridge 等外部桥接
│   │   ├── skills/               # 科研 Skill 工具层（40+）
│   │   └── main.py               # FastAPI 入口
│   ├── prompts/                  # 阶段 Prompt + presets/
│   ├── tests/                    # pytest
│   ├── requirements.txt          # 后端依赖权威清单
│   └── data/                     # arXiv fallback + reference/fl 资源包
├── frontend/                     # React + Vite（开发端口 :5173）
├── pingfenbiao-main/             # 评分表 / 影响力预测（:8765）
├── shaxiang-main/                # 迭代实验沙箱引擎
├── storage/                      # 审计链、证据链、报告产物等
├── docs/                         # 专题文档
├── scripts/                      # setup / run_dev / launch_stack / check_e2e
├── .env.example                  # 环境变量模板
├── QUICKSTART.md
└── README.md
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [QUICKSTART.md](./QUICKSTART.md) | 5 分钟快速入门 |
| [backend/README.md](./backend/README.md) | 后端架构、API、测试、联邦 Pack |
| [backend/DATABASE.md](./backend/DATABASE.md) | 数据库表结构与闭环 metadata |
| [docs/DATA_ACQUISITION.md](./docs/DATA_ACQUISITION.md) | 领域数据集发现与数据整合 |
| [docs/FL_STARTER_PACK.md](./docs/FL_STARTER_PACK.md) | 联邦学习资源包 |
| [docs/FL_EXPERIMENT_PARADIGMS.md](./docs/FL_EXPERIMENT_PARADIGMS.md) | FL 实验范式与脚本注入 |
| [docs/SCIENCE_ITERATION.md](./docs/SCIENCE_ITERATION.md) | 科学迭代相关说明 |
| [backend/prompts/README.md](./backend/prompts/README.md) | Prompt 模板与范式预设索引 |
| [backend/tests/README.md](./backend/tests/README.md) | 测试说明 |
| [frontend/README.md](./frontend/README.md) | 前端组件与页面 |
| [storage/README.md](./storage/README.md) | 审计链、证据链持久化 |
| [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md) | LaTeX 报告导出 |

---

## 未来展望

- 引入更多科学领域的数据集和领域专家知识，扩展跨学科覆盖
- 将反事实预演升级为定量仿真，提升实验方案评估精度
- 在更多领域与真实实验室仪器环境对接，实现虚拟到物理的闭环
- 探索多 Agent 间基于强化学习的协作策略优化
