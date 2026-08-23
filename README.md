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

标准 Pipeline 为 7 阶段顺序执行，由 **CoordinatorAgent（大家长 Agent）** 全程协调，支持人工审核 Gate（HITL）、综合质量分（CQS）、完整审计链导出等能力。大家长 Agent 贯穿全流程，提供 Agent 间记忆管理、端到端全局跟踪、报告内容质量自动修复、预设错误规则主动拦截等能力，相当于给科研流水线配备了一位智能质检员。

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
| 沙箱验证 | `IterativeExperimentService` | 通过 smoke/full 运行模式获得实验验证结果 |
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
- `HypothesisReviewAgent` 对偏题假设扣分 40%，排除偏题和低证据假设
- 无事实依据的假设标记为"不通过"，进入修订流程

**过滤器 2：小样本预检过滤器**
- 识别数据集元数据和字段结构，在正式运行前生成小规模测试数据集，执行 LLM 生成的实验脚本
- `IterativeExperimentService` 支持 smoke_only 模式：生成小规模测试集并执行脚本
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

**问题背景**：流水线式多智能体工作流中容易出现以下问题：
- **记忆漂移**：前序 Agent 的输出信息在后继阶段逐步丢失或扭曲
- **单点割裂**：各阶段独立运行，缺乏全局视角，问题累积到最终阶段才暴露
- **机器味**：AI 生成内容存在乱码、标点重复、LaTeX 转义残留等基础质量问题
- **被动响应**：错误仅在阶段失败时被发现，缺乏主动预防和自动修复机制

**解决方案**：由 **CoordinatorAgent（大家长 Agent）** 承担全局协调者角色，贯穿 7 阶段 Pipeline 全流程，实现四大核心能力：

#### 1. 线性工作流的智能交接与记忆管理

大家长 Agent 维护项目级结构化上下文，确保信息在 Agent 间有序传递，不丢失、不扭曲：

| 能力 | 实现模块 | 说明 |
|------|----------|------|
| 项目上下文维护 | `CoordinatorAgent._context` | 持续维护研究问题、Fact 白名单快照、假设版本历史、门禁结果、补救动作记录 |
| 阶段结果自动同步 | `update_stage_result()` | 每阶段完成后自动更新上下文，如文献挖掘后将 fact_id 注入 Fact 白名单 |
| 假设版本管理 | `_context["hypothesis_versions"]` | 记录每次假设生成的版本数、偏题数、低证据数，支持版本回溯 |
| 运行前就绪检查 | `check_project_readiness()` | 检查研究问题、文献数量、LLM 配置、历史运行状态，预判运行风险 |

#### 2. 端到端全局跟踪，打破单点割裂

大家长 Agent 以全局视角审视整个 Pipeline，主动发现跨阶段问题：

| 能力 | 实现模块 | 说明 |
|------|----------|------|
| 跨阶段策略建议 | `suggest_stage_strategy()` | 根据已完成阶段的结果，主动建议下一阶段的执行策略（如文献不足时建议补搜） |
| 阶段停滞检测 | `detect_stalled_stages()` | 监测各阶段耗时，超时自动告警（如迭代实验超 60 分钟触发提醒） |
| 闭环决策记录 | `PipelineService` | 记录完整的补救决策轨迹，支持审计追溯 |
| 统一 Hint 面板 | `CoordinatorHints.tsx`（前端） | 所有阶段检查结果、LLM 分析、修复状态统一展示，一目了然 |

#### 3. 全程质检 — 专治 AI 生成内容的"机器味儿"

大家长 Agent 在报告生成阶段执行专项内容质量检查，自动识别并修复 AI 生成常见问题：

| 检查项 | 检测内容 | 说明 |
|--------|----------|------|
| 乱码检测 | 非法字符、替换字符、控制字符 | 正则扫描报告章节，发现乱码立即标记 |
| 截断检测 | 末行不完整结束 | 检查章节末尾是否以句号/感叹号等正常结束 |
| 标点重复检测 | 句号/逗号/感叹号/问号等连续重复（如"。。"） | 正则匹配中英文标点的 2+ 次重复 |
| LaTeX 转义残留 | `\_`、`\{`、`\}`、`\%`、`\\` 等 | 检测 LaTeX 转义字符未正确转换的残留 |
| 自动修复触发 | 发现上述问题后自动调用 LLM 修复 | 修复后经后处理去除标点重复和 LaTeX 转义，结果直接持久化到数据库 |

#### 4. 全局质量监控 — 预设常见问题 + 自我修正

大家长 Agent 内置覆盖全部 7 阶段的预定义错误规则库，自动触发分级响应：

| 阶段 | 预定义规则 | 触发条件 | 默认响应 |
|------|-----------|----------|---------|
| 问题理解 | 描述不充分 | 关键词 < 2 个 | 提示用户重跑 |
| 文献挖掘 | 无事实 / 事实不足 | facts_count = 0 / < 3 | 提示导入文献 / 补搜 |
| 知识缺口 | 无缺口 | gaps_count = 0 且有事实 | 自动跳过 |
| 假设生成 | 全部偏题 / 全部低证据 | off_topic 100% / low_evidence 100% | 提示重跑 / 自动证据链迭代 |
| 假设评审 | 无主假设 | has_primary = False | 提示修订假设 |
| 报告生成 | 质量分过低 / 引用未核验 / 缺失章节 / 内容质量问题 | score < 60 / refs_verified = 0 / 缺失 ≥ 3 章节 / 有内容问题 | 提示修订 / 自动修复 |
| **任意阶段** | LLM 兜底分析 | 预定义规则未匹配但检测到异常数据 | 异步调用 LLM 做开放性分析 |

协调流程：
```
研究问题 → [大家长：上下文初始化] → 问题理解
                             ↓
                        [大家长：阶段检查] ← 匹配预定义规则库
                             ↓                    ↓
                        文献挖掘          未匹配 → 异常检测 → LLM 兜底分析
                             ↓                    ↓              ↓
                        [大家长：自动/提示] → 补救动作    兜底建议
                             ↓
                        知识缺口 → [大家长：证据不足?] → 提示补搜
                             ↓
                        假设生成 → [大家长：低证据?] → 自动证据链迭代
                             ↓
                        假设评审 → [大家长：无主假设?] → 提示修订
                             ↓
                        迭代实验 → [大家长：停滞检测] → 超时告警
                             ↓
                        报告生成 → [大家长：内容质量检查] → 自动修复乱码/截断/标点重复
                             ↓
                        [大家长：报告后专项检查 + 补救决策轨迹]
                             ↓
                        [审计链导出]
```

**总结**：大家长 Agent 相当于给整个科研流水线配备了三位一体的智能监督员 — 既是**记忆管家**（确保信息不丢失）、又是**质量质检员**（专治 AI 生成内容的"机器味儿"）、还是**全局监控员**（预设 12+ 规则 + LLM 兜底，主动发现并自动修复问题）。

---

## 快速开始

**详细分步说明**请查看 [QUICKSTART.md](./QUICKSTART.md)。

### Windows

```batch
scripts\setup_backend.bat          # 创建根目录 venv + 安装 backend\requirements.txt
scripts\setup_frontend.bat         # pnpm install

# 复制 .env.example → backend\.env 并填入你的 QWEN_API_KEY
# 如暂无 API Key，设置 USE_MOCK_LLM=true 可跑通完整流程

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
| http://localhost:5173 | 前端界面 |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |

### 端到端验收

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端
python scripts\check_e2e.py
```

---

## 技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | React 18 + Vite 5 + TailwindCSS 3 |
| UI 图标 | lucide-react |
| 图表 | recharts |
| 数据库 | SQLite（默认） / MySQL（可选） |
| ORM | SQLAlchemy 2.0 |
| 向量检索 | zvec（默认；可检测兼容旧 FAISS 索引） |
| 嵌入模型 | Sentence-Transformers |
| 大模型 | Qwen（阿里云百炼 / DashScope） |
| PDF 解析 | PyMuPDF |
| 包管理器 | pnpm |

---

## 智能体架构

| Agent / 阶段 | 输入 | 输出 | 核心职责 |
|-------|------|------|----------|
| **ProblemUnderstanding** | 研究问题文本 | 问题陈述、领域、关键词、边界 | 将模糊问题转化为可研究的结构化描述 |
| **LiteratureMining** | project_id + 研究问题 | 科学事实 + 证据列表 + 引用映射 | FAISS 检索 → Qwen 提取事实，每条绑定 chunk_id |
| **KnowledgeGap** | 文献事实 + 不确定点 | 知识缺口、矛盾、研究机会 | 发现文献中的空白和可研究方向 |
| **HypothesisGeneration** | 知识缺口 + 文献证据 | 候选假设 + 对齐评分 + 数据证据 | 基于缺口生成可验证假设，标注 supporting_fact_ids |
| **HypothesisReview** | 候选假设 + 文献上下文 | 新颖性评分、可行性评估、反事实预演 | 评估假设质量；支持反事实预演 |
| **IterativeExperiment** | 主假设 + 数据集绑定 | 脚本设计、smoke/full 迭代、图表与反馈重设计 | 对接实验引擎；嵌套投影供报告与溯源 |
| **ReportGeneration** | 全流程中间产物 | 12 字段最终报告 + 合规检查 | 聚合各阶段输出，生成完整报告 |

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
| 预测 | `/predict` | 评分表生成 / 报告打分 / 科学影响力预测（BFF → pingfenbiao） |
| 文献 | `/documents` | 文献上传、arXiv 检索与导入 |
| 报告 | `/reports` | 研究报告浏览与导出 |
| Skills | `/skills` | Skill 启用与目录 |
| 项目工作台 | `/projects/:id` | 多 Tab 科研全流程 |

**项目工作台主 Tab**：项目概览 · 研究问题 · 文献库 · 智能体工作流 · 候选假设 · 迭代实验 · 研究报告

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
| 报告 | scientific_plot_skill, report_quality_check_skill | 图表生成、VLM 评审、合规检查 |
| 实验 | experiment_sanity_check_skill | 实验方案合理性检查 |

---

## 联邦学习模式（Starter Pack）

创建项目时选择**联邦学习（资源包）**，Pipeline 阶段与通用模式相同，差异来自内容注入：

| 能力 | 说明 |
|------|------|
| 资源包 | `backend/data/reference/fl/`（当前 v1.4+）：seed facts、数据集 YAML、checklists、failure cases、实验范式 |
| 默认实验档位 | 标准 Non-IID：Dirichlet α=0.1 + Local / Centralized / FedAvg / FedProx |
| 可选档位 | 快速验证（IID + 三基线） |
| 领域种子 | 金融 / 医疗康养 / 边缘 / 工业 / 交通，以及 DP、CV、NLP、多语言、FedLLM、LoRA 异构等 |
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
| **9** | Prompt 范式预设 | pack_a/b/c/d 多套预设、项目内 Prompt 管理 Tab、一键应用 API |

---

## Pipeline（一键运行）

```bash
POST /api/v1/pipeline/run
```

阶段顺序：`problem_understanding` → `literature_mining` → `knowledge_gap` → `hypothesis_generation` → `hypothesis_review` → `iterative_experiment` → `report_generation`

每个阶段记录：

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

---

## 报告质量检查

`ReportQualityCheckSkill` 对最终报告执行以下检查：

- 12 字段完整性（Paper Title → References）
- Technical Details 是否明确 Qwen/千问和阿里云百炼
- References 是否包含 unknown / placeholder 等虚构引用
- Results 是否区分 actual / simulated / expected
- Datasets 是否有真实来源或标记拟采集
- 图表是否有 `source_dataset_id` 和 `is_generated_from_real_data`
- 是否出现 GPT-4 / Claude / Llama 等非 Qwen 模型表述

输出示例：
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

---

## 交叉评价机制 — 报告质量"模型对战"评估

**问题背景**：传统报告质量评估依赖单一规则或单一视角，难以全面反映报告的综合质量。客观评分可能忽略学术品味，而主观判断又缺乏标准化基准。

**解决方案**：在报告生成 Tab 下新增**质量评估卡片**，支持三种评估模式对同一份报告进行交叉评价，形成"模型对战"对比：

| 模式 | 定位 | 提示词设计 | 评分体系 |
|------|------|-----------|---------|
| **简单提交评估** | 裸 LLM 无预设，看基础反应 | 直接提交报告，仅附带"请客观评估" | 0–100 综合分 + 评语 |
| **客观加权评分** | LLM 戴"评分员"面具，按固定 rubric 机械打分 | 从 `report-scorer-suite` 提炼的七层加权模型 | L0 类型识别(5%) → L1 形式合规(5%) → L2 选题与问题(20%) → L3 方法学(25%) → L4 证据强度(25%) → L5 诚实度(15%) → L6 可用性(5%) |
| **科学家评分** | LLM 戴"科学家 PI"面具，带学术偏好和理解 | 从 `report-scorer-suite` 提炼的 PI 人格设定 | 选题价值(20%) → 方法恰当性(25%) → 证据强度(30%) → 贡献清晰度(15%) → 表达与诚实度(10%) |

**最有信息量的是分歧而非分数本身**。三种模式的分歧揭示报告的深层问题：

| 模式分歧 | 含义 |
|----------|------|
| 客观加权高 + 科学家低 | 报告"看起来结构完整，但缺乏实质贡献" |
| 科学家高 + 客观加权低 | 报告"内容扎实有趣，但形式上有硬伤" |
| 三种模式差异大（≥10 分） | 报告存在争议点，建议重点审阅 |

**使用方式**：在报告生成 Tab 中找到"报告质量评估（模型对战）"卡片，选择模式后点击"开始评估"即可即时获得评分结果，或点击"三种模式全部运行"一次性获得完整对战对比。

**实现**：`ReportEvaluationService`（后端）+ `ReportQualityEvaluationCard`（前端），评估结果不持久化，每次点击重新评估，确保独立性。

---

## 假设质量保障体系

系统通过四层机制保障假设生成质量：

1. **领域对齐检测**：`hypothesis_generation_agent` 内置 6 个领域关键词集合，自动检测假设关键词是否属于研究问题的领域范围，过滤偏题假设
2. **新颖性审查**：`hypothesis_novelty_review_skill` 对候选假设进行新颖性评分，检测与已有文献的高风险重叠
3. **锦标赛排序**：通过改进的 Margin-Weighted Tournament 对候选假设进行全配对比较，交叉评估多个维度
4. **人工审核**：HITL Gate 在关键节点暂停，允许人工审核、编辑和决策

---

## 测试

```bash
cd backend
pytest tests/ -v

# A 级优化批次回归（1–7 批）
pytest tests/test_batch1_quality_hitl.py tests/test_batch2_verifiable_spec.py \
       tests/test_batch3_data_finder.py tests/test_batch4_closed_loop.py \
       tests/test_batch5_literature_figures.py tests/test_batch6_feedback_catalog.py \
       tests/test_batch7_provenance_audit.py -v
```

---

## 前置要求

| 工具 | 版本 |
|------|------|
| Python | 3.10 / 3.11 / 3.12（推荐） |
| Node.js | ≥ 18 |
| pnpm | ≥ 9 |

---

## 配置说明

复制 `.env.example` 为 `backend/.env`，按需修改。核心环境变量：

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

### 获取 Qwen API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 创建 API Key
3. 填入 `backend/.env` 的 `QWEN_API_KEY`

---

## 项目结构

```
AISci/
├── backend/
│   ├── app/
│   │   ├── agents/               # 各阶段智能体（独立类 + Prompt + JSON Schema）
│   │   ├── api/                  # API 路由（v1.py 汇总挂载）
│   │   ├── core/                 # 配置、闭环控制、质量评分、溯源
│   │   ├── models/               # SQLAlchemy 模型
│   │   ├── schemas/              # Pydantic 请求/响应 Schema
│   │   ├── services/             # 业务逻辑 + Qwen 客户端 + 向量存储
│   │   ├── integrations/         # 外部系统桥接
│   │   ├── skills/               # 科研 Skill 工具层
│   │   └── main.py               # FastAPI 入口
│   ├── prompts/                  # 阶段 Prompt 模板 + presets/ 范式预设库
│   ├── tests/                    # pytest 测试
│   └── data/                     # arXiv fallback + reference/fl 资源包
├── pingfenbiao-main/              # 评分表 / 科学影响力预测（独立 Web 服务）
├── shaxiang-main/                # 迭代实验引擎
├── storage/                      # 项目级持久化（审计链、证据链等）
├── docs/                         # 专题文档
├── frontend/
│   └── src/
│       ├── components/           # 工作流、迭代实验、预测页等
│       ├── pages/                # 首页、预测、文献、报告、项目工作台等
│       ├── services/             # API 服务模块
│       ├── types/                # TypeScript 类型定义
│       └── config/               # 项目配置
├── scripts/
│   ├── setup_backend.bat/sh      # 后端环境搭建
│   ├── setup_frontend.bat/sh     # 前端环境搭建
│   ├── run_dev.bat/sh            # 一键启动前后端
│   └── check_e2e.py              # 端到端验收脚本
├── .env.example                  # 环境变量模板
├── QUICKSTART.md                 # 详细快速入门
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
| [backend/prompts/README.md](./backend/prompts/README.md) | Prompt 模板与范式预设索引 |
| [backend/tests/README.md](./backend/tests/README.md) | 测试说明 |
| [frontend/README.md](./frontend/README.md) | 前端组件与页面 |
| [storage/README.md](./storage/README.md) | 审计链、证据链持久化 |
| [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md) | LaTeX 报告导出 |

---

## 未来展望

- 引入更多科学领域的数据集和领域专家知识，扩展系统的跨学科覆盖范围
- 将反事实预演升级为定量仿真，提升实验方案评估的精确度
- 在更多领域与真实实验室仪器环境对接，实现从虚拟仿真到物理实验的闭环
- 探索多 Agent 间基于强化学习的协作策略优化，实现更高效的任务分配和资源调度