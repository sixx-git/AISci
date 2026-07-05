# 开题报告科学思维规范（AISci 落地指南）

> 来源：科研开题报告培训视频（约 16 分钟）  
> 目的：把「背景 → 目的 → 意义 → 方法 → …」模板背后的**科学逻辑**写进 AISci，而不是只套格式。

---

## 1. 核心原则

| 原则 | 要求 |
|------|------|
| 真实需求 | 先自己跑通一遍研究逻辑，再交给 AI 辅助 |
| 真实问题 | 来自可观察的矛盾，不是空泛创意 |
| 主要矛盾 | 在众多问题中选定一个最值得做的切入点 |
| 可验证 | 假设与方法必须能被检验 |
| 真实科研价值 | 优于「情怀价值」或堆砌文字 |

**开题逻辑链（必须贯穿 Pipeline）：**

```
矛盾 → 主要矛盾 → 拆解（内/外/边界）→ 研究对象 → 分析对象
  → 研究现状 → 空白/新问题 → 结合工作基础 → 子问题 → 研究内容 → 方法
```

---

## 2. 各章节写作要求

### 2.1 研究背景

- 说明**科学问题为什么存在**、**本质是什么**
- 从现象/矛盾出发，**一句一层**讲故事
- 结合国家战略需求、学术热点、工程需求

### 2.2 问题提出

- 问题源于**现象中的矛盾**（理论 vs 实验、预期 vs 实际）
- 选出**主要矛盾**，不能什么都做
- **拆解**：内部因素 / 外部因素 / 系统边界 / 演化机制
- 对象必须**具体**（例：细胞 → 膜 / 质 / ECM + 环境）

### 2.3 研究目的

- 在问题拆解之后写
- 与主要矛盾、研究对象一一对应

### 2.4 研究意义

- 区分基础研究（解释规律）与应用研究（解决现实问题）
- 强调**真实科研价值**，避免空泛「创新性」表述

### 2.5 研究现状

- 已解决什么？
- 已有哪些方法？
- **还有什么没研究**（空白）？
- 必须结合团队/项目**已有工作基础**

### 2.6 研究内容

- 基于空白 + 工作基础提出**可操作的子问题**
- 每个内容点应对应一个可验证子问题

### 2.7 研究方法

- 观察方式（实验 / 模拟 / 行为观察）
- 工具与手段
- 机制验证路径
- 按问题类型选方法：结构性 / 环境类 / 机制类 / 模型类

---

## 3. 与 AISci 现有结构的映射

| 开题报告概念 | AISci Pipeline 阶段 | 报告字段 / 数据结构 |
|-------------|---------------------|---------------------|
| 研究背景、问题本质 | `problem_understanding` | `problem_statement` 前半、`paper_abstract` |
| 主要矛盾、内外拆解、边界 | `problem_understanding`（待扩展） | `scope_boundary`、`constraints` |
| 研究目的 | `problem_understanding` | `expected_output` |
| 研究现状 | `literature_mining` | `literature_facts`、`citation_map` |
| 研究空白 | `knowledge_gap` | `knowledge_gaps` |
| 科学假设 / 研究内容 | `hypothesis_generation` | `final_hypothesis`、`rationale` |
| 研究方法 | `experiment_design` | `methods`、`technical_details` |
| 实验方案 | `experiment_design` + `small_validation` | `experiments`、`results` |
| 工作基础 | 项目文献库 + 本地资料 | 文献 facts、项目 documents |
| 质量审查 | `ReportReviewerSkill` | `compliance_check` |

当前差距（需补齐）：

1. `problem_understanding` 缺少：主要矛盾、内外拆解、研究对象结构化字段  
2. `report_generation` prompt 未显式要求「矛盾→空白→内容」逻辑链  
3. `ReportQualityCheckSkill` 偏赛题合规，缺少科学思维 checklist  

---

### 第一期：Prompt 层（改动小，见效快） ✅ 已实现

见 `backend/prompts/problem_understanding.md`、`backend/prompts/report_generation.md`。

### 第二期：Agent / Schema 层 ✅ 已实现

见 `backend/app/agents/problem_understanding_agent.py`、`pipeline_service.py`（科学逻辑约束传递）。

### 第三期：Skill 审查层 ✅ 已实现

见 `backend/app/skills/report/proposal_logic_review_skill.py`，在 `ReportGenerationAgent` 质量检查后自动调用。

---

## 4. 推荐落地步骤（分三期）

### 第一期：Prompt 层（改动小，见效快）

**4.1 增强 `backend/prompts/problem_understanding.md`**

在输出 JSON 中增加字段（或先在 prompt 里要求写入 `scope_boundary` / `constraints` 的固定结构）：

```json
{
  "main_contradiction": "主要矛盾的一句话描述",
  "phenomenon_contradiction": "现象/理论矛盾来源",
  "research_object": {
    "internal": "内部因素/结构",
    "external": "外部环境",
    "boundary": "研究边界"
  },
  "decomposition_notes": "拆解与演化说明",
  "research_significance": "真实科研价值（非情怀）"
}
```

**4.2 增强 `backend/prompts/report_generation.md`**

在各章节要求中追加：

- `problem_statement`：必须含主要矛盾 + 研究价值  
- `rationale`：必须含现状 → 空白 → 推理 → 假设（禁止跳步）  
- `methods` / `experiments`：必须对应 `research_object` 中的可验证子问题  

**4.3 验证方式**

- 新建测试项目，跑完整 Pipeline  
- 检查生成报告是否出现：矛盾、边界、空白、可验证方法  

---

### 第二期：Agent / Schema 层

**4.4 扩展 `ProblemUnderstandingResponse`**

文件：`backend/app/agents/problem_understanding_agent.py`

- 在 Pydantic 模型中增加上述新字段  
- 在 `schema_example` 与 `_validate_and_normalize` 中同步  

**4.5 向下游传递**

- `PipelineService._exec_hypothesis_generation`：把 `main_contradiction`、`research_object` 传入假设生成  
- `ReportGenerationAgent._format_input`：把科学逻辑字段写入 prompt 变量  

---

### 第三期：Skill 审查层

**4.6 新增 `ProposalLogicReviewSkill`**

路径建议：`backend/app/skills/report/proposal_logic_review_skill.py`

输入：`problem_understanding`、`knowledge_gaps`、`report_data`  
输出：

```json
{
  "logic_score": 0-10,
  "has_main_contradiction": true,
  "has_gap_to_content_chain": true,
  "has_verifiable_methods": true,
  "issues": ["problem_statement 未写明主要矛盾"],
  "revision_hints": ["在 rationale 中补充文献空白"]
}
```

**4.7 接入 Pipeline**

- 在 `report_generation` 之后、`ReportReviewerSkill` 之前调用  
- 将 `issues` 写入 `extra_metadata.compliance_check`  

**4.8 注册 Skill**

- 在 skill registry 中启用（与现有 `ReportReviewerSkill` 并列）  

---

## 5. 使用 Cursor Skill 辅助开发

项目已添加 Cursor Skill：`.cursor/skills/scientific-proposal-logic/SKILL.md`

在 Cursor 中可这样用：

```
@scientific-proposal-logic 请按规范修改 problem_understanding.md
@scientific-proposal-logic 检查这份报告是否符合开题逻辑
```

---

## 6. 人工 + AI 协作流程（与视频一致）

1. **你（导师）**：定义科学思维——矛盾、对象、边界、验证标准  
2. **AISci Pipeline**：文献盘点 → 现状/空白 → 假设 → 实验 → 报告  
3. **审查**：`ProposalLogicReviewSkill` + `ReportReviewerSkill`  
4. **迭代**：根据 `revision_hints` 修改 prompt 或补充项目文献，再跑 Pipeline  

---

## 7. 快速自检清单

写报告或改 prompt 前，逐项确认：

- [ ] 是否写清**主要矛盾**（不是多个并列问题）  
- [ ] 是否定义**研究对象**的内/外/边界  
- [ ] 现状是否回答「已有什么、缺什么」  
- [ ] 研究内容是否来自**空白 + 工作基础**  
- [ ] 方法是否**可验证**、与假设对应  
- [ ] 是否避免空泛「创新」「意义重大」而无依据  
- [ ] 引用与数据是否真实（AISci 已有红线，继续保持）  

---

## 8. 参考文件

| 文件 | 作用 |
|------|------|
| `backend/prompts/problem_understanding.md` | 问题理解 prompt |
| `backend/prompts/report_generation.md` | 报告生成 prompt |
| `backend/app/skills/report/report_reviewer_skill.py` | 报告审查 |
| `backend/app/skills/report/report_quality_check_skill.py` | 赛题合规检查 |
| `video_transcript.txt`（项目根目录） | 视频完整转录 |
