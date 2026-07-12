# 多源数据采集（Data Acquisition）运维手册

面向 AISci **Pipeline 第 3 阶段**与 **Data Finder** 面板，说明默认行为、可选高级能力与配置项。

## 1. 设计原则（2026 简化）

**Pipeline 默认**：根据研究问题检索**相关领域公开数据集**，不做 PDF 表格/图表挖掘。

| 模式 | 值 | Pipeline 默认 | 做什么 |
|------|-----|---------------|--------|
| **领域数据集发现** | `dataset_discovery` | ✅ | LLM 推断 DataSpec → HF/Zenodo/registry 检索 → 返回候选列表 |
| **完整数据整合** | `full` | 可选开启 | 在上述基础上 + PDF 表格/图表抽取 + 对齐合并 + Gap 闭环 |

文献挖掘阶段已负责 PDF 入库与向量索引；数据采集阶段**不再重复**对每篇论文做 VLM 图表数字化（除非显式开启 `full` 模式）。

## 2. Pipeline 默认流程（`dataset_discovery`）

```
研究问题 + DataSpec 提示
        ↓
  DataRequirementUnderstanding（LLM）
        ↓
  ExternalDatasetSearch + registry（HF / Zenodo / Figshare / Kaggle / GEO …）
        ↓
  external_candidates[] + data_spec.json
```

**跳过**：补充材料、PDF 表格抽取、图表 VLM、自动 import、align/merge、Gap 闭环。

典型耗时：**数十秒～2 分钟**（取决于外部 API），不再是 10–25 分钟。

## 3. 完整模式（`full`）— 手动或配置开启

适用于需要从**已入库论文**抽取表格/图表并合并为 Analysis Bundle 的场景：

| 步骤 | 说明 |
|------|------|
| discover | 论文链接挖掘 + 图表检测 + VLM（慢） |
| fetch_supplementary | 补充材料 |
| extract | PDF 表格抽取 |
| fetch_external | HF/Zenodo 自动 import（每轮 ≤2） |
| align / merge | Schema 对齐与 CSV 合并 |
| gap_loop | Coverage 未达标时多轮补搜（默认最多 2–4 轮） |

在 Data Finder 面板可**分步**触发：`抽取 PDF 表格` → `对齐` → `合并`，无需一次跑满 `full`。

## 4. 支持的数据来源

| 来源 | 默认模式检索 | full 模式额外能力 |
|------|-------------|-------------------|
| HuggingFace | ✅ 搜索 | ✅ 可自动 import 样例行 |
| Zenodo / Figshare | ✅ 搜索 | ✅ 可自动 import（≤25MB） |
| Kaggle / 静态索引 | ✅ catalog | ❌ 需用户下载上传 |
| OpenAlex / GEO | ✅ 元数据 | ❌ 需用户跟链 |
| 项目 PDF | —（文献阶段已处理） | 表格 / 图表 / SI |

**诚实化原则**：候选列表区分「可自动导入」与「仅元数据/目录」；后者在 Data Finder「外部数据待办」中手动上传。

## 5. 输出物

### `dataset_discovery`（默认）

- `data_spec` / `data_requirements` — 结构化数据需求
- `external_candidates` — 领域相关数据集候选（含 URL、availability）
- `assets_index` — 轻量索引

### `full` 模式额外

- `extracted_tables` / `figures` / `merged.csv`
- `analysis_bundle.zip`（Release Gate 通过后）
- `coverage_report.json`

## 6. Release Gate

- **默认模式**：`min_merged_rows=0`，不要求合并 CSV；阶段以「检索完成」为准。
- **full 模式**：要求合并 CSV ≥1 行、provenance 覆盖等（见 `evaluate_release_gate`）。

## 7. 配置项（`project.config`）

```json
{
  "data_spec_hints": {
    "entities_of_interest": ["client_id"],
    "target_variables": ["global_accuracy"],
    "preferred_sources": ["huggingface", "zenodo"]
  },
  "data_acquisition": {
    "mode": "dataset_discovery",
    "coverage_gap_threshold": 70,
    "data_spec_gap_threshold": 60,
    "max_gap_rounds": 2,
    "auto_literature_discovery": false
  }
}
```

| 字段 | 默认 | 说明 |
|------|------|------|
| `mode` | `dataset_discovery` | 设为 `full` 启用论文抽取+合并+Gap |
| `coverage_gap_threshold` | 70 | 仅 full + gap_loop |
| `max_gap_rounds` | 2 | 仅 `mode: full` + gap_loop |

## 8. API 入口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/data-finder/search` | **领域数据集检索**（`run_dataset_discovery`） |
| POST | `/data-finder/acquire` | 按 `mode` 跑 Pipeline 同源逻辑；`auto_import` 默认 false |
| POST | `/data-finder/extract` | 仅 PDF 表格抽取（高级） |
| POST | `/data-finder/gap-enrich` | Gap 补搜（高级，需先有 coverage） |
| POST | `/data-finder/external-candidates/upload` | 手动上传 catalog 数据集 |

`acquire` 请求体可选 `acquisition_mode: "full"` 覆盖项目配置。

## 9. 可观测性

`data_acquisition.stats` 含：

- `acquisition_mode` — `dataset_discovery` | `full`
- `external_candidates` — 候选数量
- `total_duration_ms` — 各步耗时之和

`step_details` 中跳过的步骤带 `skipped: true` 与 `reason`。

## 10. 测试

```bash
cd backend
pytest tests/test_data_acquisition_e2e.py tests/test_phase5_data_integration.py -q
```

Golden Corpus（merge/gate）验收仍在 `test_data_acquisition_e2e.py`，与默认轻量 Pipeline 路径独立。
