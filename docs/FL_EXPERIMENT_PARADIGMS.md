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
| `scripts/flower_hfl_sim_entry.py` | Flower / 兼容 numpy 仿真入口 |
| `scripts/fedml_hfl_sim_entry.py` | FedML / 兼容 numpy 仿真入口 |

## 仿真后端（v1.5+）

创建联邦项目时可选 `local_pack`（默认）、`flower` 或 `fedml`，写入 `project.config.fl_simulation`。  
迭代实验「联邦仿真运行」面板可覆盖本次参数；与通用沙箱 `analysis_script` 路径隔离。

| backend | 依赖 | 未安装时 |
|---------|------|----------|
| `local_pack` | sklearn（已有） | — |
| `flower` | 可选 `flwr` | `flower_numpy_compat` |
| `fedml` | 可选 `fedml` | `fedml_numpy_compat` |

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
