# FL 参考脚本

纯本地可跑（numpy / sklearn），**无 Flower/FATE 依赖**。

| 脚本 | 场景 | 输出 |
|------|------|------|
| `hfl_fedavg_pilot.py` | HFL FedAvg | `metrics.json` |
| `hfl_non_iid_partition.py` | 生成 Non-IID CSV | `synthetic_hfl.csv` + metrics |
| `vfl_aligned_logistic_pilot.py` | VFL 对齐+logistic | `metrics.json` |
| `run_fedavg_pilot.py` | 供服务调用的统一入口 | stdout JSON |

在迭代实验中：将脚本路径与注释中的成功标准复制到 `analysis_script`，按数据路径改参。
