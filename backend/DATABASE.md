# AI Scientist 数据库设计文档

## 概述

本文档描述 AI Scientist 的数据库设计。默认使用 **SQLite**（`backend/data/aiscientist.db`），可选 **MySQL**；ORM 为 SQLAlchemy 2.0。

除关系型表外，部分闭环与 Data Finder 数据持久化在 **`storage/`** 目录（审计链 jsonl、证据链 JSON、Catalog 等），见 [storage/README.md](../../storage/README.md)。

## 数据库架构

### ER 图概览

```
┌──────────────┐       ┌──────────────┐       ┌──────────────────┐
│   Project    │1─────*│   Document   │1─────*│      Chunk       │
└──────────────┘       └──────────────┘       └──────────────────┘
      1│
       │              ┌──────────────┐
       ├─────────────*│  Hypothesis  │
       │              └──────────────┘
       │                    1│
       │                     *│
       │              ┌──────────────┐
       │              │   Evidence   │
       │              └──────────────┘
       │
       │              ┌───────────────────┐
       ├─────────────*│ ExperimentDesign  │
       │              └───────────────────┘
       │
       │              ┌──────────────┐
       ├─────────────*│    Report    │
       │              └──────────────┘
       │
       │              ┌──────────────┐
       ├─────────────*│  PipelineRun │── extra_metadata: quality_trend / events / decisions
       │              └──────────────┘
       │                    1│
       │                     *│
       │              ┌───────────────────────┐
       │              │ PipelineStageExecution│
       │              └───────────────────────┘
       │
       ├──────────────┐
       │              *
       │       ┌──────────────┐
       ├──────*│    RunLog    │
       │       └──────────────┘
       │
       └──────*┌──────────────┐
               │   Dataset    │
               └──────────────┘
                    1│
                     *│
              ┌──────────────┐
              │MultimodalAsset│
              └──────────────┘

       ┌──────────────────┐   ┌─────────────────────────┐
       │  PromptVersion   │   │ ProjectPromptOverride   │
       └──────────────────┘   └─────────────────────────┘

       ┌──────────────┐       ┌──────────────┐
       │ ChatSession  │1─────*│ ChatMessage  │
       └──────────────┘       └──────────────┘
```

## 数据表设计

### 1. projects（项目表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| name | VARCHAR(200) | 项目名称 |
| description | TEXT | 项目描述 |
| research_topic | TEXT | 研究主题 |
| keywords | TEXT | 关键词，逗号分隔 |
| research_question | TEXT | 研究问题 |
| research_domain | VARCHAR(200) | 研究领域 |
| research_goal | TEXT | 研究目标 |
| research_background | TEXT | 已知背景 |
| data_source | TEXT | 数据来源 |
| constraints | TEXT | 限制条件 |
| expected_output | TEXT | 期望输出 |
| status | VARCHAR(50) | 项目状态 |
| created_by | VARCHAR(100) | 创建者 |
| priority | INTEGER | 优先级（1-10） |
| config | JSON | 项目配置 |
| project_mode | VARCHAR(50) | 项目模式：`general` / `federated_learning` |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**ProjectStatus 枚举**：draft / in_progress / documents_processed / hypothesis_generated / experiment_designed / completed / archived

---

### 2. documents（文档表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| filename | VARCHAR(255) | 原始文件名 |
| file_path | VARCHAR(512) | 文件存储路径 |
| file_type | VARCHAR(50) | 文件类型（扩展名） |
| file_size | INTEGER | 文件大小（字节） |
| mime_type | VARCHAR(100) | MIME 类型 |
| title | VARCHAR(500) | 论文标题 |
| authors | TEXT | 作者列表 |
| abstract | TEXT | 摘要 |
| keywords | TEXT | 关键词 |
| publication_date | DATETIME | 发布日期 |
| journal | VARCHAR(200) | 期刊/会议名称 |
| doi | VARCHAR(200) | DOI 编号 |
| source_url | VARCHAR(500) | 来源 URL |
| doc_type | VARCHAR(50) | 文档类型 |
| status | VARCHAR(50) | 处理状态 |
| error_message | TEXT | 错误信息 |
| raw_text | TEXT | 原始提取文本 |
| summary | TEXT | 文档摘要 |
| extra_metadata | JSON | 额外元数据 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 3. chunks（文献切片表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| document_id | VARCHAR(36) | 外键 → documents.id |
| chunk_index | INTEGER | 在文档中的序号 |
| content | TEXT | 切片文本内容 |
| content_preview | VARCHAR(500) | 内容预览 |
| start_offset | INTEGER | 在原文档中的起始位置 |
| end_offset | INTEGER | 在原文档中的结束位置 |
| start_page | INTEGER | 起始页码 |
| end_page | INTEGER | 结束页码 |
| embedding_model | VARCHAR(100) | 向量化模型名称 |
| vector | JSON | 向量数据 |
| dimension | INTEGER | 向量维度 |
| chunk_type | VARCHAR(50) | 切片类型 |
| status | VARCHAR(50) | 处理状态 |
| tokens_count | INTEGER | Token 数量 |
| extra_metadata | JSON | 额外元数据 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 4. hypotheses（科学假设表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| research_question | TEXT | 研究问题 |
| hypothesis | TEXT | 假设内容 |
| rationale | TEXT | 推理依据 |
| novelty | TEXT | 创新性说明 |
| testability | TEXT | 可测试性 |
| required_data | TEXT | 所需数据 |
| possible_method | TEXT | 可行方法 |
| risk | TEXT | 风险评估 |
| supporting_fact_ids | TEXT | 关联的文献事实 ID 列表（JSON） |
| evidence_level | VARCHAR(20) | 证据级别：high / medium / low |
| status | VARCHAR(50) | 状态：draft / testing / accepted / rejected |
| priority | INTEGER | 优先级（1-5） |
| confidence | FLOAT | 置信度（0-1） |
| alignment_score | INTEGER | 问题对齐度（0-100） |
| off_topic | BOOLEAN | 是否偏题 |
| off_topic_reason | TEXT | 偏题原因 |
| matched_keywords | TEXT | 匹配到的关键词（JSON） |
| missing_keywords | TEXT | 缺失的关键词（JSON） |
| question_alignment | TEXT | 假设与研究问题的对齐说明 |
| dataset_field_refs | TEXT | 引用的数据集字段（JSON） |
| data_evidence_ids | TEXT | 引用的数据证据 ID（JSON） |
| validation_target | TEXT | 验证目标指标 |
| expected_measurable_effect | TEXT | 预期的可量化效果 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 5. experiment_designs（实验设计表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| hypothesis_id | VARCHAR(36) | 外键 → hypotheses.id |
| hypothesis | TEXT | 关联假设内容 |
| methods | TEXT | 研究方法 |
| datasets | TEXT | 数据集说明 |
| source_data | TEXT | 源数据说明 |
| target_data | TEXT | 目标数据说明 |
| baselines | TEXT | 基线方法 |
| metrics | TEXT | 评估指标 |
| experimental_steps | TEXT | 实验步骤 |
| expected_results | TEXT | 预期结果 |
| limitations | TEXT | 局限性 |
| status | VARCHAR(50) | 状态：draft / ready / running / completed |
| priority | INTEGER | 优先级（1-5） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 6. reports（报告表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| hypothesis_id | VARCHAR(36) | 关联假设 ID |
| experiment_design_id | VARCHAR(36) | 关联实验设计 ID |
| small_validation_id | VARCHAR(36) | 关联小样验证 ID |
| title | VARCHAR(500) | 报告标题 |
| paper_title | VARCHAR(500) | 论文标题 |
| paper_abstract | TEXT | 论文摘要 |
| problem_statement | TEXT | 问题陈述 |
| rationale | TEXT | 原理依据 |
| technical_details | TEXT | 技术细节 |
| datasets | TEXT | 数据集说明 |
| source | TEXT | 源数据说明 |
| target | TEXT | 目标说明 |
| methods | TEXT | 研究方法 |
| experiments | TEXT | 实验设计 |
| results | TEXT | 预期结果 |
| references | TEXT | 参考文献 |
| markdown_content | TEXT | Markdown 格式完整报告 |
| attachments | JSON | 附件列表 |
| pdf_path | VARCHAR(500) | PDF 文件路径 |
| version | INTEGER | 版本号 |
| status | VARCHAR(50) | 状态：draft / generating / generated / ready / published / archived |
| language | VARCHAR(20) | 语言 |
| generated_by | VARCHAR(100) | 生成者 |
| model_used | VARCHAR(100) | 使用的模型 |
| authors | TEXT | 作者列表 |
| summary | TEXT | 报告摘要 |
| extra_metadata | JSON | 额外元数据（含合规检查结果） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 7. pipeline_runs（Pipeline 运行表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| run_id | VARCHAR(36) | 运行 ID（唯一标识） |
| research_question | TEXT | 研究问题 |
| status | VARCHAR(50) | 运行状态：pending / running / completed / failed / cancelled / human_review_required |
| started_at | DATETIME | 开始时间 |
| completed_at | DATETIME | 完成时间 |
| total_duration_ms | INTEGER | 总耗时（毫秒） |
| input_data | JSON | 输入数据 |
| config | JSON | 运行配置 |
| output_data | JSON | 输出数据 |
| final_report_id | VARCHAR(36) | 关联报告 ID |
| error_message | TEXT | 错误信息 |
| failed_stage | VARCHAR(50) | 失败的阶段 |
| current_stage | VARCHAR(50) | 当前执行阶段 |
| extra_metadata | JSON | 闭环元数据（见下方说明） |
| prompt_versions_used | JSON | 各阶段 Prompt 版本 |
| version | INTEGER | 运行版本号 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 8. pipeline_stage_executions（Pipeline 阶段执行表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| pipeline_run_id | VARCHAR(36) | 外键 → pipeline_runs.id |
| stage | VARCHAR(50) | 阶段名称（8 个阶段之一） |
| stage_order | INTEGER | 阶段序号（1-8） |
| status | VARCHAR(50) | 执行状态 |
| started_at | DATETIME | 开始时间 |
| completed_at | DATETIME | 完成时间 |
| duration_ms | INTEGER | 耗时（毫秒） |
| input_data | JSON | 输入数据 |
| output_data | JSON | 输出数据 |
| model_used | VARCHAR(100) | 使用的模型 |
| model_parameters | JSON | 模型参数 |
| prompt_used | TEXT | 使用的 Prompt |
| token_count | INTEGER | Token 用量 |
| extra_metadata | JSON | 人工修改、revision_history、HITL 审阅等 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 9. evidences（证据链表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| hypothesis_id | VARCHAR(36) | 外键 → hypotheses.id |
| document_id | VARCHAR(36) | 来源文档 ID |
| chunk_id | VARCHAR(36) | 来源 Chunk ID |
| fact_text | TEXT | 事实陈述 |
| quote_text | TEXT | 原文引用片段 |
| page_number | INTEGER | 页码 |
| relevance_score | FLOAT | 相关度分数（0-1） |
| source_title | VARCHAR(500) | 来源论文/文档标题 |
| extra_metadata | TEXT | 额外元数据（JSON） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 10. datasets（数据集表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| filename | VARCHAR(500) | 原始文件名 |
| file_path | VARCHAR(1000) | 存储路径 |
| file_size | INTEGER | 文件大小（字节） |
| data_type | VARCHAR(50) | tabular / image / time_series / json / pdf / unknown |
| source_type | VARCHAR(50) | upload / history / public / data_finder |
| n_rows | INTEGER | 行数 |
| n_columns | INTEGER | 列数 |
| columns_json | TEXT | 列名（JSON 数组） |
| dtypes_json | TEXT | 字段类型（JSON） |
| missing_count | INTEGER | 缺失值总数 |
| missing_rate | FLOAT | 缺失率 0–1 |
| statistics_json | TEXT | 统计摘要（JSON） |
| preview_json | TEXT | 预览行（JSON） |
| preprocessing_status | VARCHAR(50) | pending / processing / completed / failed |
| use_for_hypothesis | BOOLEAN | 是否用于假设生成 |
| extra_metadata | TEXT | 额外元数据（JSON） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 11. multimodal_assets（多模态资产表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| dataset_id | VARCHAR(36) | 可选，关联 datasets.id |
| file_name | VARCHAR(500) | 文件名 |
| file_path | VARCHAR(1000) | 存储路径 |
| modality | VARCHAR(20) | text / image / audio |
| mime_type | VARCHAR(100) | MIME 类型 |
| extracted_text | TEXT | 提取/转写全文 |
| extracted_summary | TEXT | 摘要 |
| evidence_facts_json | TEXT | 多模态 Evidence Facts（JSON 数组） |
| metadata_json | TEXT | 解析元数据（JSON） |
| parse_status | VARCHAR(50) | pending / completed / failed / warning |
| use_for_hypothesis | BOOLEAN | 是否用于假设生成 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 12. small_validations（小样验证表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| experiment_design_id | VARCHAR(36) | 外键 → experiment_designs.id |
| hypothesis | TEXT | 关联假设 |
| has_real_data | INTEGER | 0=模拟 / 1=真实数据 |
| analysis_script | TEXT | Python 分析脚本 |
| simulated_data | TEXT | 模拟数据（JSON） |
| simulation_assumptions | TEXT | 模拟假设说明 |
| charts | TEXT | 图表数据（JSON） |
| statistics | TEXT | 统计结果（JSON） |
| run_log | TEXT | 运行日志 |
| status | VARCHAR(50) | draft / generated / running / completed |
| execution_time | FLOAT | 执行耗时 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 13. run_logs（运行日志表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| project_id | VARCHAR(36) | 外键 → projects.id |
| level | VARCHAR(20) | 日志级别：debug / info / warning / error / critical |
| category | VARCHAR(50) | 日志类别：system / document_processing / vectorization / hypothesis_generation / experiment_design / report_generation / user_action / api_call |
| message | TEXT | 日志消息 |
| details | JSON | 详细数据 |
| execution_time_ms | INTEGER | 执行时间（毫秒） |
| success | BOOLEAN | 是否成功 |
| error_message | TEXT | 错误信息 |
| user_id | VARCHAR(100) | 用户 ID |
| user_action | VARCHAR(100) | 用户操作 |
| component | VARCHAR(100) | 组件名称 |
| module | VARCHAR(100) | 模块名称 |
| function | VARCHAR(100) | 函数名称 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 14. prompt_versions（Prompt 版本表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 |
| name | VARCHAR(200) | Prompt 名称 |
| stage | VARCHAR(50) | 适用 Pipeline 阶段 |
| version | INTEGER | 版本号 |
| prompt_template | TEXT | 模板正文 |
| variables | JSON | 变量列表 |
| status | VARCHAR(50) | draft / active / deprecated / archived |
| model | VARCHAR(100) | 默认模型 |
| default_parameters | JSON | 默认参数 |
| created_at | DATETIME | 创建时间 |

---

### 15. project_prompt_overrides（项目 Prompt 覆盖表）

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 |
| project_id | VARCHAR(36) | 外键 → projects.id |
| stage | VARCHAR(50) | Pipeline 阶段 |
| prompt_template | TEXT | 覆盖后的模板 |
| editor | VARCHAR(100) | 最后编辑者 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

---

### 16. chat_sessions / chat_messages（对话表）

| 表 | 主要列 | 说明 |
|----|--------|------|
| chat_sessions | id, created_at | 对话会话 |
| chat_messages | id, session_id, role, content, references | 消息记录 |

---

## pipeline_runs.extra_metadata 结构（闭环）

Discovery / 联邦 Campaign 等模式下，`extra_metadata` JSON 常见字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `quality_trend` | array | CQS 质量趋势条目（stage、score、cqs、raw_score） |
| `closed_loop_events` | array | 闭环事件（discovery_refine、ensemble_review、sandbox_validation 等） |
| `closed_loop_decisions` | array | 决策记录（trigger、action、reason、next_stage、round） |
| `hitl_gate` | object | HITL 暂停状态、待审阶段 |
| `execution_tier` | string | 执行层级标注 |
| `data_authenticity` | string | 数据真实性标注 |
| `version_snapshots` | array | 迭代前后 snapshot（用于因果链 Diff） |

完整审计链另写入 **`storage/audit/{run_id}.jsonl`**，可通过 `GET /api/v1/pipeline/audit-export/{run_id}` 导出。

## 文件系统持久化（非 SQL 表）

| 路径 | 内容 |
|------|------|
| `storage/evidence_chains/{project_id}/{hypothesis_id}.json` | 结构化证据链 |
| `storage/data_finder/{project_id}/` | Data Finder 结果、merged CSV、Bundle |
| `storage/catalog/{project_id}/data_catalog.json` | Data Catalog |
| `storage/feedback/{project_id}/` | Feedback Hub 约束 |
| `backend/storage/reports/{report_id}/` | report.md / report.tex / report.pdf |

假设 **`data_citation_id`**（`cite_*`）与 **`table_row_id`** 存于 Data Finder 的 `row_provenance` 与 merged CSV 列 `_data_citation_id`、`_table_row_id`，不单独建表。

---

## 使用说明

### 初始化数据库

```bash
python scripts/init_db.py
```

数据库文件会自动创建在 `backend/data/aiscientist.db`。

### 访问数据库

使用任何 SQLite 客户端打开 `data/aiscientist.db` 文件即可查看和操作数据库。

## 设计决策

### 1. UUID 作为主键
- 使用 UUID 作为主键，有利于分布式部署和数据同步
- 避免使用自增 ID 带来的锁争用问题

### 2. 时间戳列
- 所有表都包含 `created_at` 和 `updated_at` 列
- `created_at` 使用数据库自动生成的时间戳
- `updated_at` 由应用程序在更新时维护

### 3. JSON 字段
- 使用 JSON 类型存储灵活的元数据和配置
- 允许在不修改数据库结构的情况下扩展功能

### 4. 外键级联删除
- 使用外键级联删除，确保数据一致性

### 5. 假设溯源字段
- `hypotheses.supporting_fact_ids` / `dataset_field_refs` / `data_evidence_ids` 均以 JSON 文本存储
- 字段引用可含 `cite_*` 形式的 `data_citation_id`，对应 Data Finder 行级 provenance

## 相关文档

- [backend/README.md](./README.md)
- [backend/prompts/README.md](./prompts/README.md)
- [storage/README.md](../storage/README.md)