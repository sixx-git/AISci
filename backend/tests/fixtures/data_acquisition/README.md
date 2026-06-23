# Data Acquisition Golden Corpus

固定基准集，供 `test_data_acquisition_e2e.py` 与 Release Gate 验收使用（不依赖外网）。

| 文件 | 用途 |
|------|------|
| `fl_client_metrics.csv` | 联邦 baseline 主表（client_id + global_accuracy） |
| `fl_client_f1.csv` | 按 client_id join 的补充指标 |
| `paper_results_snippet.txt` | Methods/Results 数值句，用于 TextFacts L1 |
