# FL 参考脚本

纯本地可跑（numpy / sklearn），**无 Flower/FATE 依赖**（除非另装）。

| 脚本 | 场景 | 输出 |
|------|------|------|
| `hfl_fedavg_pilot.py` | HFL FedAvg | `metrics.json` |
| `hfl_non_iid_partition.py` | 生成 label-skew Non-IID CSV | `synthetic_hfl.csv` + metrics |
| `hfl_dirichlet_partition.py` | Dirichlet / pathological 划分 | CSV + metrics |
| `hfl_baseline_compare_pilot.py` | Local / Centralized / FedAvg / FedProx | `metrics.json` 对比表 |
| `vfl_aligned_logistic_pilot.py` | VFL 对齐+logistic | `metrics.json` |
| `run_fedavg_pilot.py` | 供服务调用的统一入口 | stdout JSON |
| `flower_hfl_sim_entry.py` | Flower / 兼容 numpy 单机仿真入口 | `metrics.json` |
| `fedml_hfl_sim_entry.py` | FedML / 兼容 numpy 单机仿真入口 | `metrics.json` |

默认实验档位：**标准 Non-IID（Dirichlet α=0.1 + FedAvg/FedProx）**。

三层执行（+ 可选框架后端）：

1. **资源包** — 文献/数据集/脚本内容注入  
2. **local_pack** — sklearn pilot（默认）  
3. **Flower / FedML** — 对应 `*_hfl_sim_entry.py`（可选安装；未装则兼容仿真）

可选依赖：

```bash
pip install 'flwr>=1.8.0'   # Flower
pip install fedml           # FedML（较重，可不装）
```

在迭代实验中：使用「基于模板重新设计脚本」（`apply-fl-script` 后台 job，LLM 适配真实数据），或使用「联邦仿真控制台」运行 local_pack / Flower / FedML。**不要**把模板原文直接粘贴进 `analysis_script`。
