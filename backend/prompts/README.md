# Prompt 模板目录

本目录存放 Pipeline 阶段的 Markdown Prompt 模板。Agent 运行时通过 Jinja2 渲染变量后提交给 Qwen；项目级覆盖见 `project_prompt_overrides` 表与 Prompt Console。

| 文件 | Pipeline 阶段 | 调用方 | 主要输出 |
|------|---------------|--------|----------|
| [problem_understanding.md](./problem_understanding.md) | `problem_understanding` | ProblemUnderstandingAgent | 问题陈述、领域、关键词、边界、科学逻辑 |
| [literature_recommendation.md](./literature_recommendation.md) | `literature_mining`（发现子阶段） | LiteratureRecommendationService | 子主题、推荐论文、search_queries |
| [literature_mining.md](./literature_mining.md) | `literature_mining` | LiteratureMiningAgent | facts、citation_map、uncertain_points |
| [knowledge_gap.md](./knowledge_gap.md) | `knowledge_gap` | KnowledgeGapAgent | knowledge_gaps、contradictions、研究机会 |
| [hypothesis_generation.md](./hypothesis_generation.md) | `hypothesis_generation` | HypothesisGenerationAgent | 候选假设 + supporting_fact_ids |
| [hypothesis_review.md](./hypothesis_review.md) | `hypothesis_review` | HypothesisReviewAgent | 五维评分、修改建议 |
| [iterative_experiment.md](./iterative_experiment.md) | `iterative_experiment` | 迭代实验相关引导 | 与 shaxiang 迭代实验衔接的说明/约束 |
| [pro_con_con_challenge.md](./pro_con_con_challenge.md) | `hypothesis_review` | ProConAdversarialService | 反方质疑 `challenges[]` |
| [pro_con_evolution.md](./pro_con_evolution.md) | `hypothesis_review` | ProConAdversarialService | 正方演化 `evolution` |
| [report_generation.md](./report_generation.md) | `report_generation` | ReportGenerationAgent | 12 字段 Markdown / LaTeX 报告 |
| [counterfactual_preview.md](./counterfactual_preview.md) | （可选） | Counterfactual 相关 | 反事实预演 |
| [hypothesis_evolution_*.md](./hypothesis_evolution_simplify.md) | （可选） | 假设演化 | 简化 / out-of-box 变体 |

> **已移除顶层文件**：`experiment_design.md`、`small_validation.md`。主链路由 `iterative_experiment` 承接；联邦项目仍可通过 **pack_d** 预设使用 `presets/pack_d/experiment_design/federated_plan.md` 与 `presets/pack_d/small_validation/fl_pilot.md`（写入项目级覆盖）。

## 与闭环能力的衔接

- **Feedback Hub**：Pipeline 启动前会将 `global_constraints` 注入部分阶段的上下文。
- **Verifiable Spec**：假设生成后由 `iterative_science.attach_verifiable_specs_to_hypotheses` 附加（联邦模式走 FL 分支）。
- **证据链迭代**：假设修订由 `HypothesisRevisionSkill` 完成，非本目录主文件。
- **Discovery 迭代**：自动多轮 refine 已退役；旧 run 的 snapshot / Decision Log 仍可只读复用上述 Prompt 展示。

## 范式预设库（Prompt Presets）

`presets/manifest.json` 定义多套科研自动化范式（参考 Sakana AI Scientist / v2），**不含 `report_generation`**。

| 包 ID | 说明 |
|-------|------|
| `pack_a` | AI Scientist v1：想法 → 代码 → 运行 → 评审 |
| `pack_b` | AI Scientist v2：树搜索、剪枝、pilot 门禁 |
| `pack_c` | AISci 默认：证据溯源 + 可验证假设（推荐通用新项目） |
| `pack_d` | 联邦学习 Starter Pack + 实验范式（默认标准 Non-IID）；**仅 `federated_learning` 项目**可见 |

生成/更新预设文件：`python scripts/generate_prompt_presets.py`  
重新生成 FL 资源：`python scripts/generate_fl_starter_pack.py`

API：`GET /api/v1/prompts/presets/catalog`、`POST /api/v1/prompts/presets/apply`

联邦专题：[docs/FL_STARTER_PACK.md](../../docs/FL_STARTER_PACK.md)、[docs/FL_EXPERIMENT_PARADIGMS.md](../../docs/FL_EXPERIMENT_PARADIGMS.md)

## 编辑约定

1. 保持 JSON 输出 Schema 与对应 `schemas/` / Agent 解析逻辑一致。
2. 禁止在 Prompt 中要求编造 `fact_id`、引用或数据集字段。
3. 修改后建议运行相关 Agent 测试或 `pytest tests/test_*agent*.py -v`。
4. 赛题合规：References 必须可追溯；Technical Details 须提及 Qwen/千问。

## 相关文档

- [backend/README.md](../README.md)
- [DATABASE.md](../DATABASE.md) — `prompt_versions` / `project_prompt_overrides`
- [项目根 README](../../README.md)
