# Prompt 模板目录

本目录存放 8 个 Pipeline 阶段的 Markdown Prompt 模板。Agent 运行时通过 Jinja2 渲染变量后提交给 Qwen；项目级覆盖见 `project_prompt_overrides` 表与 Prompt Console。

| 文件 | Pipeline 阶段 | 调用 Agent | 主要输出 |
|------|---------------|------------|----------|
| [problem_understanding.md](./problem_understanding.md) | `problem_understanding` | ProblemUnderstandingAgent | 问题陈述、领域、关键词、边界 |
| [literature_mining.md](./literature_mining.md) | `literature_mining` | LiteratureMiningAgent | facts、citation_map、uncertain_points |
| [knowledge_gap.md](./knowledge_gap.md) | `knowledge_gap` | KnowledgeGapAgent | knowledge_gaps、contradictions、研究机会 |
| [hypothesis_generation.md](./hypothesis_generation.md) | `hypothesis_generation` | HypothesisGenerationAgent | 候选假设 + supporting_fact_ids + 数据字段引用 |
| [hypothesis_review.md](./hypothesis_review.md) | `hypothesis_review` | HypothesisReviewAgent | 五维评分、修改建议 |
| [experiment_design.md](./experiment_design.md) | `experiment_design` | ExperimentDesignAgent | 实验方案、指标、基线、步骤 |
| [small_validation.md](./small_validation.md) | `small_validation` | SmallValidationAgent | 小样验证脚本、统计、图表 |
| [report_generation.md](./report_generation.md) | `report_generation` | ReportGenerationAgent | 12 字段 Markdown / LaTeX 报告 |

## 与闭环能力的衔接

- **Feedback Hub**：Pipeline 启动前会将 `global_constraints` 注入部分阶段（如假设生成、Data Finder）的上下文。
- **Verifiable Spec**：假设生成/评审后由 `iterative_science.build_verifiable_specs_to_hypotheses` 附加，不直接写在 Prompt 内。
- **证据链迭代**：假设修订由 `HypothesisRevisionSkill`（独立 Prompt `hypothesis_revision` 内置于 Skill）完成，非本目录文件。
- **Discovery 迭代**：多轮 refine 复用上述 Prompt，输入含上一轮 snapshot 与 Decision Log 摘要。

## 编辑约定

1. 保持 JSON 输出 Schema 与对应 `schemas/` / Agent 解析逻辑一致。
2. 禁止在 Prompt 中要求编造 `fact_id`、引用或数据集字段。
3. 修改后建议运行相关 Agent 测试或 `pytest tests/test_*agent*.py -v`。
4. 赛题合规：References 必须可追溯；Technical Details 须提及 Qwen/千问。

## 相关文档

- [backend/README.md](../README.md)
- [DATABASE.md](../DATABASE.md) — `prompt_versions` / `project_prompt_overrides`
- [项目根 README](../../README.md) — 科研闭环与 A 级优化
