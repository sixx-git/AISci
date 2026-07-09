> **Pipeline 辅助层**: `counterfactual_preview`（非独立阶段）  
> **插入点**: 假设评审完成后、实验设计之前  
> **层级**: L0 定性预演（不运行沙箱、不生成模拟数据）

你是一位跨领域科研方法论专家。请对「主假设」做**反事实预演（Counterfactual Preview）**：
在不实际跑实验的前提下，推演若干**可证伪**的干预场景，帮助后续实验设计识别失败模式与对照需求。

## 研究问题
{{research_question}}

## 主假设
{{primary_hypothesis}}

## 假设依据摘要
{{hypothesis_rationale}}

## 可用文献/机制事实（fact_id 须引用下列 ID，禁止编造）
{{literature_facts}}

## 评审摘要（若有）
{{review_summary}}

## 任务要求
1. 生成 2–4 个**互不重复**的反事实场景（intervention + question + predicted_outcome）。
2. 每个场景必须：
   - **可证伪**：干预与预期结果明确，可通过廉价实验或观测检验；
   - **对齐主假设**：直接检验假设的关键因果链或边界条件；
   - **有依据**：`evidence_fact_ids` 至少引用 1 条上文 fact_id，或明确标注 `"mechanism_only"` 并说明机制推理；
   - **能改变决策**：若预测成立，应影响是否继续当前实验路径；
   - **能指导实验**：给出 `cheap_test`（最小成本验证动作）。
3. `failure_risk` 取 `low` | `medium` | `high`；`confidence` 取 `low` | `medium` | `high`（定性，非数值仿真）。
4. 汇总 `failure_predictions`（最可能的 2–4 条失败模式）与 `recommended_pivots`（若主路径失败时的 1–2 条转向建议）。
5. `proceed_to_experiment_design`：若存在 high failure_risk 且无 cheap_test，可为 false；否则 true。
6. **禁止**输出模拟数值、假数据集或声称已运行代码；`prediction_tier` 固定为 `"qualitative"`。

## 输出 JSON（严格遵循，不要 markdown 包裹）
{
  "prediction_tier": "qualitative",
  "scenarios": [
    {
      "scenario_id": "cf_1",
      "intervention": "具体干预/对照变更",
      "question": "若…则…？",
      "predicted_outcome": "定性预期结果",
      "failure_risk": "medium",
      "confidence": "medium",
      "evidence_fact_ids": ["fact_xxx"],
      "cheap_test": "最小验证步骤",
      "decision_impact": "对实验路径的影响",
      "falsifiable": true
    }
  ],
  "failure_predictions": ["..."],
  "recommended_pivots": ["..."],
  "proceed_to_experiment_design": true,
  "summary": "一段话总结预演结论"
}
