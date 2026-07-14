# 迭代实验（Iterative Experiment）

本阶段由 AISci 对接 shaxiang 风格的迭代实验流程：数据推荐与绑定 → 分析脚本设计 → smoke/full 迭代 → 人工反馈重设计。

## 目标

- 在绑定真实数据前阻断「假跑」与无依据的报告伪成功
- 产出可复现的脚本、指标与迭代记录，供报告多选引用

## 输入

- 主假设文本（来自假设评审）
- 项目内已创建的迭代实验（用户可在「迭代实验」页手动多选纳入报告）
- 数据配置（sandbox 模式必填）

## 输出约定

- `status`: `ok` | `blocked_need_data` | `blocked_need_hypothesis`
- `experiments`: 实验列表摘要
- 兼容字段：必要时合成 `experiment_design` / `small_validation` 供旧报告模板读取

## 约束

- 缺数据时不得继续设计脚本或跑迭代
