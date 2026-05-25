# AI Scientist 数据库设计文档

## 概述

本文档描述了 AI Scientist 项目的数据库设计。数据库使用 SQLite（默认）或 MySQL 构建，使用 SQLAlchemy 作为 ORM。

## 数据库架构

### ER 图概览

```
┌─────────────┐         ┌─────────────┐
│   Project   │1───────*│  Document   │
└─────────────┘         └─────────────┘
      1│
       │                       ┌──────────────┐
       ├──────────────────────*│  Hypothesis  │
       │                       └──────────────┘
       │                              │
       │                              │ 1
       │                              *
       │                       ┌───────────────────┐
       ├──────────────────────*│ ExperimentDesign  │
       │                       └───────────────────┘
       │
       │                       ┌──────────┐
       ├──────────────────────*│  Report  │
       │                       └──────────┘
       │
       │                       ┌───────────┐
       └──────────────────────*│  RunLog   │
                               └───────────┘
    *
┌─────────────┐
│    Chunk    │
└─────────────┘
```

## 数据表设计

### 1. projects（项目表）

存储研究项目的基本信息。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| name | VARCHAR(200) | NO | - | 项目名称 |
| description | TEXT | YES | NULL | 项目描述 |
| research_topic | TEXT | YES | NULL | 研究主题 |
| keywords | TEXT | YES | NULL | 关键词，逗号分隔 |
| status | VARCHAR(50) | NO | draft | 项目状态 |
| created_by | VARCHAR(100) | YES | NULL | 创建者 |
| priority | INTEGER | YES | 5 | 优先级（1-10） |
| config | JSON | YES | NULL | 项目配置 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**状态枚举 (ProjectStatus)**:
- draft - 草稿
- in_progress - 进行中
- documents_processed - 文档已处理
- hypothesis_generated - 假设已生成
- experiment_designed - 实验已设计
- completed - 已完成
- archived - 已归档

---

### 2. documents（文档表）

存储论文和其他文献的元数据。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | NO | - | 所属项目 ID，外键 |
| filename | VARCHAR(255) | NO | - | 原始文件名 |
| file_path | VARCHAR(512) | NO | - | 文件存储路径 |
| file_type | VARCHAR(50) | NO | - | 文件类型（扩展名） |
| file_size | INTEGER | YES | 0 | 文件大小（字节） |
| mime_type | VARCHAR(100) | YES | NULL | MIME 类型 |
| title | VARCHAR(500) | YES | NULL | 论文标题 |
| authors | TEXT | YES | NULL | 作者列表 |
| abstract | TEXT | YES | NULL | 摘要 |
| keywords | TEXT | YES | NULL | 关键词 |
| publication_date | DATETIME | YES | NULL | 发布日期 |
| journal | VARCHAR(200) | YES | NULL | 期刊/会议名称 |
| volume | VARCHAR(50) | YES | NULL | 卷 |
| issue | VARCHAR(50) | YES | NULL | 期 |
| pages | VARCHAR(50) | YES | NULL | 页码 |
| doi | VARCHAR(200) | YES | NULL | DOI 编号 |
| source_url | VARCHAR(500) | YES | NULL | 来源 URL |
| doc_type | VARCHAR(50) | YES | research_paper | 文档类型 |
| status | VARCHAR(50) | NO | uploaded | 处理状态 |
| error_message | TEXT | YES | NULL | 错误信息 |
| raw_text | TEXT | YES | NULL | 原始提取文本 |
| summary | TEXT | YES | NULL | 文档摘要 |
| extra_metadata | JSON | YES | NULL | 额外元数据 |
| custom_fields | JSON | YES | NULL | 自定义字段 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**文档类型枚举 (DocumentType)**:
- research_paper - 研究论文
- review - 综述
- thesis - 学位论文
- report - 报告
- preprint - 预印本
- other - 其他

**处理状态枚举 (DocumentStatus)**:
- uploaded - 已上传
- processing - 处理中
- processed - 已处理
- failed - 处理失败

---

### 3. chunks（文献切片表）

存储向量化后的文献切片。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | NO | - | 所属项目 ID，外键 |
| document_id | VARCHAR(36) | NO | - | 所属文档 ID，外键 |
| chunk_index | INTEGER | NO | - | 在文档中的序号 |
| content | TEXT | NO | - | 切片文本内容 |
| content_preview | VARCHAR(500) | YES | NULL | 内容预览 |
| start_offset | INTEGER | YES | NULL | 在原文档中的起始位置 |
| end_offset | INTEGER | YES | NULL | 在原文档中的结束位置 |
| start_page | INTEGER | YES | NULL | 起始页码 |
| end_page | INTEGER | YES | NULL | 结束页码 |
| embedding_model | VARCHAR(100) | YES | NULL | 向量化模型名称 |
| vector | JSON | YES | NULL | 向量数据 |
| dimension | INTEGER | YES | NULL | 向量维度 |
| chunk_type | VARCHAR(50) | YES | text | 切片类型 |
| status | VARCHAR(50) | NO | pending | 处理状态 |
| tokens_count | INTEGER | YES | NULL | Token 数量 |
| extra_metadata | JSON | YES | NULL | 额外元数据 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**切片状态枚举 (ChunkStatus)**:
- pending - 待处理
- embedding - 向量化中
- ready - 已就绪
- failed - 处理失败

---

### 4. hypotheses（科学假设表）

存储由 AI 生成的科学假设。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | NO | - | 所属项目 ID，外键 |
| title | VARCHAR(500) | NO | - | 假设标题 |
| description | TEXT | NO | - | 假设详细描述 |
| summary | TEXT | YES | NULL | 假设摘要 |
| category | VARCHAR(100) | YES | NULL | 假设分类 |
| tags | TEXT | YES | NULL | 标签列表，逗号分隔 |
| confidence_score | FLOAT | YES | 0.5 | 置信度评分（0-1） |
| novelty_score | FLOAT | YES | NULL | 创新性评分（0-1） |
| feasibility_score | FLOAT | YES | NULL | 可行性评分（0-1） |
| source_documents | TEXT | YES | NULL | 来源文献 ID 列表 |
| source_chunks | TEXT | YES | NULL | 来源切片 ID 列表 |
| version | INTEGER | YES | 1 | 版本号 |
| parent_id | VARCHAR(36) | YES | NULL | 父假设 ID |
| status | VARCHAR(50) | NO | draft | 状态 |
| reasoning | TEXT | YES | NULL | 推理和论证过程 |
| evidence | TEXT | YES | NULL | 支持证据 |
| counterarguments | TEXT | YES | NULL | 反驳意见 |
| experiment_suggestions | TEXT | YES | NULL | 实验建议 |
| generated_by | VARCHAR(100) | YES | NULL | 生成者 |
| model_used | VARCHAR(100) | YES | NULL | 使用的模型 |
| extra_metadata | JSON | YES | NULL | 额外元数据 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**假设状态枚举 (HypothesisStatus)**:
- draft - 草稿
- pending_review - 待审核
- accepted - 已接受
- rejected - 已拒绝
- modified - 已修改

---

### 5. experiment_designs（实验设计表）

存储由 AI 生成的实验设计方案。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | NO | - | 所属项目 ID，外键 |
| hypothesis_id | VARCHAR(36) | YES | NULL | 关联的假设 ID，外键 |
| title | VARCHAR(500) | NO | - | 实验设计标题 |
| description | TEXT | NO | - | 实验描述 |
| purpose | TEXT | YES | NULL | 实验目的 |
| design_type | VARCHAR(100) | YES | NULL | 实验类型 |
| variables | JSON | YES | NULL | 变量配置 |
| procedure | TEXT | YES | NULL | 实验步骤 |
| materials | TEXT | YES | NULL | 所需材料 |
| equipment | TEXT | YES | NULL | 所需设备 |
| data_collection | TEXT | YES | NULL | 数据收集方法 |
| measurement_methods | TEXT | YES | NULL | 测量方法 |
| statistical_methods | TEXT | YES | NULL | 统计分析方法 |
| expected_results | TEXT | YES | NULL | 预期结果 |
| success_criteria | TEXT | YES | NULL | 成功判定标准 |
| time_estimate | VARCHAR(100) | YES | NULL | 时间估计 |
| budget_estimate | TEXT | YES | NULL | 预算估计 |
| resources_needed | TEXT | YES | NULL | 所需资源 |
| potential_pitfalls | TEXT | YES | NULL | 潜在问题 |
| contingency_plans | TEXT | YES | NULL | 应急预案 |
| version | INTEGER | YES | 1 | 版本号 |
| status | VARCHAR(50) | NO | draft | 状态 |
| generated_by | VARCHAR(100) | YES | NULL | 生成者 |
| model_used | VARCHAR(100) | YES | NULL | 使用的模型 |
| extra_metadata | JSON | YES | NULL | 额外元数据 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**实验设计状态枚举 (ExperimentDesignStatus)**:
- draft - 草稿
- ready_for_review - 待审核
- approved - 已批准
- modified - 已修改
- deprecated - 已弃用

---

### 6. reports（报告表）

存储 AI 生成的最终研究报告。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | NO | - | 所属项目 ID，外键 |
| title | VARCHAR(500) | NO | - | 报告标题 |
| summary | TEXT | YES | NULL | 报告摘要 |
| authors | TEXT | YES | NULL | 作者列表 |
| introduction | TEXT | YES | NULL | 引言 |
| literature_review | TEXT | YES | NULL | 文献综述 |
| methodology | TEXT | YES | NULL | 研究方法 |
| results | TEXT | YES | NULL | 研究结果 |
| discussion | TEXT | YES | NULL | 讨论 |
| conclusion | TEXT | YES | NULL | 结论 |
| future_work | TEXT | YES | NULL | 未来工作 |
| references | TEXT | YES | NULL | 参考文献 |
| full_content | TEXT | YES | NULL | 完整报告内容 |
| attachments | JSON | YES | NULL | 附件列表 |
| version | INTEGER | YES | 1 | 版本号 |
| status | VARCHAR(50) | NO | draft | 状态 |
| language | VARCHAR(20) | YES | zh-CN | 语言 |
| generated_by | VARCHAR(100) | YES | NULL | 生成者 |
| model_used | VARCHAR(100) | YES | NULL | 使用的模型 |
| extra_metadata | JSON | YES | NULL | 额外元数据 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**报告状态枚举 (ReportStatus)**:
- draft - 草稿
- generating - 生成中
- ready - 已就绪
- published - 已发布
- archived - 已归档

---

### 7. run_logs（运行日志表）

存储系统运行日志。

| 列名 | 类型 | 是否为空 | 默认值 | 说明 |
|------|------|----------|--------|------|
| id | VARCHAR(36) | NO | UUID | 主键 |
| project_id | VARCHAR(36) | YES | NULL | 所属项目 ID，外键 |
| level | VARCHAR(20) | NO | info | 日志级别 |
| category | VARCHAR(50) | NO | system | 日志类别 |
| message | TEXT | NO | - | 日志消息 |
| document_id | VARCHAR(36) | YES | NULL | 关联文档 ID |
| hypothesis_id | VARCHAR(36) | YES | NULL | 关联假设 ID |
| experiment_design_id | VARCHAR(36) | YES | NULL | 关联实验设计 ID |
| report_id | VARCHAR(36) | YES | NULL | 关联报告 ID |
| details | JSON | YES | NULL | 详细数据 |
| extra_metadata | JSON | YES | NULL | 元数据 |
| execution_time_ms | INTEGER | YES | NULL | 执行时间（毫秒） |
| success | BOOLEAN | YES | TRUE | 是否成功 |
| error_message | TEXT | YES | NULL | 错误信息 |
| error_stacktrace | TEXT | YES | NULL | 错误堆栈 |
| user_id | VARCHAR(100) | YES | NULL | 用户 ID |
| user_action | VARCHAR(100) | YES | NULL | 用户操作 |
| component | VARCHAR(100) | YES | NULL | 组件名称 |
| module | VARCHAR(100) | YES | NULL | 模块名称 |
| function | VARCHAR(100) | YES | NULL | 函数名称 |
| line_number | INTEGER | YES | NULL | 行号 |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | YES | NULL | 更新时间 |

**日志级别枚举 (LogLevel)**:
- debug - 调试
- info - 信息
- warning - 警告
- error - 错误
- critical - 严重

**日志类别枚举 (LogCategory)**:
- system - 系统
- document_processing - 文档处理
- vectorization - 向量化
- hypothesis_generation - 假设生成
- experiment_design - 实验设计
- report_generation - 报告生成
- user_action - 用户操作
- api_call - API 调用

---

## 使用说明

### 初始化数据库

```bash
# 使用简化脚本初始化
python scripts/init_db_simple.py
```

### 数据库迁移

项目使用 Alembic 进行数据库迁移管理：

```bash
# 初始化迁移（仅首次）
cd backend
alembic init alembic

# 创建新的迁移
alembic revision --autogenerate -m "your message"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 访问数据库

使用任何 SQLite 客户端打开 `data/aiscientist.db` 文件即可查看和操作数据库。

## 设计决策

### 1. UUID 作为主键
- 使用 UUID 作为主键，有利于分布式部署和数据同步
- 避免使用自增 ID 带来的锁争用问题

### 2. 时间戳列
- 所有表都包含 `created_at` 和 `updated_at` 列
- `created_at` 使用数据库自动生成的时间戳
- `updated_at` 应用程序在更新时维护

### 3. JSON 字段
- 使用 JSON 类型存储灵活的元数据和配置
- 允许在不修改数据库结构的情况下扩展功能

### 4. 软删除
- 目前未实现软删除
- 使用外键级联删除，确保数据一致性

### 5. 索引策略
- 为所有主键、外键和常用查询字段创建索引
- 优化查询性能

## 未来改进

- 添加软删除功能
- 添加审计日志表
- 优化索引策略
- 添加数据库备份脚本
- 添加性能监控
