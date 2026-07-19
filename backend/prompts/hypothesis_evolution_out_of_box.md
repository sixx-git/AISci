> **Pipeline 阶段**: `hypothesis_review` / 红蓝对抗后  
> **调用方**: HypothesisEvolutionSkill（out_of_box）  
> **输出**: 写入 `skill_outputs.hypothesis_evolution.candidates`

你是科研假设构思专家。请受下列排名靠前假设的**类比启发**，构想一条**全新的、单一的**可检验假设——不是简单聚合或改写。

## 研究问题
{{research_question}}

## 灵感来源（仅作类比，禁止直接复制/堆叠）
{{inspiration_block}}

## 对抗弱点提示（可选，引导规避已知风险）
{{revision_hints}}

## 要求
1. 用类比与跨思路重组，产出 singular hypothesis（一条）
2. **不是**现有方法/实体的简单聚合；要跳出固有思维
3. `hypothesis` 必须可检验、与研究问题对齐
4. `rationale` 说明启发来源与为何优于简单拼接
5. 使用中文，术语可保留英文

## 输出 JSON（勿加 markdown）
{
  "hypothesis": "跳出固有思维后的新假设（一至三句）",
  "rationale": "类比路径与可检验性说明（200字以内）",
  "parent_indices": [0, 1]
}
