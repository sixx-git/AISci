---
name: scientific-proposal-logic
description: >-
  Applies scientific-proposal (开题报告) logic to AISci: main contradiction,
  problem decomposition, research object boundaries, literature gap to content
  chain, and verifiable methods. Use when editing problem_understanding or
  report_generation prompts, implementing ProposalLogicReviewSkill, reviewing
  generated reports, or when the user mentions 开题报告, 立项依据, 科学思维, or
  proposal report standards.
---

# 开题报告科学思维（AISci）

## 何时使用

- 修改 `backend/prompts/problem_understanding.md` 或 `report_generation.md`
- 扩展 `ProblemUnderstandingAgent` / `ReportGenerationAgent`
- 新增或调用 `ProposalLogicReviewSkill`
- 审查用户项目生成的科研报告是否符合科学逻辑

详细映射与分期落地见 [docs/SCIENTIFIC_PROPOSAL_LOGIC.md](../../../docs/SCIENTIFIC_PROPOSAL_LOGIC.md)。

## 逻辑链（必须保持顺序）

```
矛盾 → 主要矛盾 → 拆解(内/外/边界) → 研究对象 → 分析
  → 现状 → 空白 → 工作基础 → 子问题 → 研究内容 → 方法(可验证)
```

## AISci 字段映射

| 开题概念 | 改哪里 |
|---------|--------|
| 背景、矛盾、对象、边界 | `problem_understanding` → `problem_statement`, `scope_boundary`, 扩展字段 |
| 现状 | `literature_mining` → `literature_facts` |
| 空白 | `knowledge_gap` → `knowledge_gaps` |
| 假设/内容 | `hypothesis_generation` → `rationale`, `final_hypothesis` |
| 方法/实验 | `experiment_design` → `methods`, `experiments` |
| 成稿 | `report_generation` → `chapters.*` |

## 修改 Prompt 时的硬性要求

### problem_understanding

输出须包含或可推导：

- `main_contradiction`：一句话主要矛盾
- `research_object`：`internal` / `external` / `boundary`
- `research_significance`：真实科研价值，非空泛创意
- 保留现有：`scope_boundary`, `constraints`, `expected_output`

禁止：泛化问题（如仅写「研究 XX 领域」而无具体矛盾）。

### report_generation

各 `chapters` 字段须满足：

- `problem_statement`：主要矛盾 + 领域局限 + 研究价值
- `rationale`：已知事实 → 知识缺口 → 推理 → 科学假设（不可跳步）
- `methods` / `experiments`：对应假设的可验证步骤；禁止写 LLM/Pipeline/RAG
- `paper_abstract`：背景、问题、方法、预期结果各一句

## 审查 Checklist

对报告或 draft 输出以下结构：

```markdown
## 科学逻辑审查
- 主要矛盾：[有/无] — 说明
- 对象拆解：[有/无] — 内/外/边界
- 现状→空白→内容：[连贯/断裂] — 说明
- 方法可验证：[是/否] — 说明
- 真实科研价值：[是/否] — 说明

## 修订建议（按优先级）
1. ...
2. ...
```

## 实现新 Skill 时的模板

类名：`ProposalLogicReviewSkill`  
路径：`backend/app/skills/report/proposal_logic_review_skill.py`  
继承：`BaseSkill`  
输入：`problem_understanding`, `knowledge_gaps`, `report_data`  
输出：`logic_score`, `has_main_contradiction`, `has_gap_to_content_chain`, `has_verifiable_methods`, `issues`, `revision_hints`

接入点：`report_generation` 之后，与 `ReportReviewerSkill` 串联。

## 质量红线（与现有赛题规范并存）

1. 不编造文献、数据（沿用 `ReportQualityCheckSkill` 规则）
2. 信息不足时写「信息不足，需要补充」，不虚构
3. 方法章节聚焦科学验证，不写平台内部实现

## 示例：合格的问题陈述片段

> 现有摩擦模型无法解释某类材料在特定湿度下的反直觉滑移现象（矛盾）。
> 本研究聚焦该材料-环境界面（对象边界），在控制湿度与载荷条件下（外因），
> 测量界面微观形变与摩擦系数（可验证），以填补 XX 机制在湿环境下的空白（空白）。

不合格：「本研究将深入探索摩擦学前沿，具有重要意义。」
