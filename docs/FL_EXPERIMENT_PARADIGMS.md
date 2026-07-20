# FL 实验范式（v1.4+）

> 与主 Pipeline 阶段无关：通过 Starter Pack 内容注入驱动实验设计 / 小样验证 / 迭代脚本。  
> **默认档位**：`standard_non_iid` — Dirichlet α=0.1 + Local / Centralized / FedAvg / FedProx。

## 档位

| id | 说明 |
|----|------|
| `standard_non_iid`（默认） | Dirichlet Non-IID + FedProx 对比 |
| `quick_iid` | IID + 三基线快速验证 |

创建联邦项目时可在 UI 选择；写入 `project.config.fl_experiment_profile`。

## 资源路径

| 路径 | 内容 |
|------|------|
| `experiment_paradigms/profiles.json` | 档位定义 |
| `experiment_paradigms/partitions.json` | 划分范式目录 |
| `experiment_paradigms/baselines.json` | 基线矩阵 |
| `experiment_paradigms/metrics.json` | 指标包 |
| `scripts/hfl_dirichlet_partition.py` | Dirichlet / pathological 划分 |
| `scripts/hfl_baseline_compare_pilot.py` | 四方法对比 pilot |

## 注入点

1. 创建项目 → `fl_pack.experiment_paradigm_context`
2. Pipeline `data_context.fl_experiment_context`（实验设计 / 假设 / 报告）
3. 迭代实验 `human_feedback`（推荐数据 / 设计脚本）
4. pack_d `federated_plan` / `fl_pilot` 硬约束文案
5. FL 模式 `verifiable_spec` 走联邦分支（含 FedAvg vs FedProx）

## 重新生成

```bash
cd backend
python scripts/generate_fl_starter_pack.py
```
