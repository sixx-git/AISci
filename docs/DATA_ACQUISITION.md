# 多源数据采集（Data Acquisition）运维手册

面向 AI Scientist **数据场景层**（Data Finder），说明能力边界、配置项、输出物与 HITL 流程。科研主流程（问题理解 → 文献 → 假设 → 实验 → 报告）不变；本模块在 `data_acquisition` 阶段提供可编排的多源发现、抽取、对齐与合并。

## 1. 能力概览

| 阶段 | 能力 | 说明 |
|------|------|------|
| Discover | 文献自动发现、外部库检索、论文链接挖掘 | 文献 &lt; 3 篇时可自动 arXiv/OpenAlex |
| Fetch | 补充材料、HF/Zenodo/Figshare 导入 | 见下方限制 |
| Extract | PDF 表格、图表 L1–L4、正文 L1 数值句 | 低置信默认不进 merge |
| Integrate | Schema 对齐、stack/join、清洗、Gap 闭环 | 双阈值 Coverage + DataSpec |
| Output | merged CSV、Analysis Bundle、Release Gate | 见 §4 |

## 2. 支持的数据来源

| 来源 | 搜索 | 自动 Import | availability |
|------|------|-------------|--------------|
| 项目 PDF/BibTeX | — | 表格/SI/图表 | 本地 |
| HuggingFace | ✅ | ✅ first-rows API | `search_and_import` |
| Zenodo / Figshare | ✅ | ✅（≤25MB，tabular/zip） | `search_and_import` |
| Kaggle / 静态索引 | ✅ | ❌ | `catalog_only` |
| OpenAlex / NCBI GEO | ✅ | ❌ 仅元数据 | `metadata_only` |

**诚实化原则**：UI 与 Coverage 区分「命中候选」与「可自动导入」；catalog/metadata 来源需用户手动上传或跟链。

## 3. 限制与默认值

| 项 | 默认 | 说明 |
|----|------|------|
| HF 导入行数 | ≤2000 行/次 | `datasets-server` first-rows |
| Zenodo 单文件 | 25 MB | 超出跳过 |
| 外部 auto-import | 每轮最多 2 个 | `_rank_import_candidates` |
| 自动文献 | 项目 &lt; 3 篇时 Top-5 | `auto_literature_discovery` 可关 |
| Gap 轮次 | 最多 2–4 | `max_gap_rounds` |
| Coverage 阈值 | 70% / DataSpec 60% | 研究问题页可配 |

## 4. 输出物（Analysis Bundle）

解压 `analysis_bundle.zip` 后典型文件：

- `merged.csv` — 清洗后合并表（含 provenance 列）
- `data_spec.json` — 本次 DataSpec
- `schema.json` — 列类型 + 对齐映射
- `provenance.jsonl` — 表/图/外部源溯源
- `figure_manifest.jsonl` — 图表识别/提取/校验（tier、points_count、auto_checks）
- `text_facts.jsonl` — 正文 L1 数值句（不进 merge，供假设/实验引用）
- `quality_report.json` / `coverage_report.json`

## 5. 图表提取分级

| Tier | 含义 | 默认进 merge |
|------|------|--------------|
| L1 | caption/版式元信息 | 否 |
| L2 | caption 规则数值 | 否（需复核） |
| L3 | VLM 结构化/趋势 | 否（需复核） |
| L4 | 点列数字化（≥10 点 + 校验） | 否（建议复核；确认后 `L4_confirmed`） |

**HITL**：Data Finder → 图表复核 → 确认后 **自动 re-merge**（无需再点 merge）。

### 外部数据待办（catalog / metadata）

对 Kaggle、OpenAlex、GEO 等 **不可自动 import** 的候选：

1. 在 Data Finder **「外部数据待办」** 列表打开数据源链接并下载  
2. 在同一行 **上传 CSV/XLSX**  
3. 状态：`待下载` → `处理中` → `已纳入合并`（失败则显示错误，可重新上传）

API：`POST /data-finder/external-candidates/upload`（multipart：`project_id`, `candidate_id`, `file`）

## 6. Release Gate（Phase 7）

`evaluate_release_gate(results)` 检查：

- 合并 CSV ≥ 1 行
- 表格 provenance 100% 覆盖
- 有图则 100% manifest
- Gap 轮次 ≤ 配置上限

结果写入 `results.release_gate` 与 `data_acquisition.stats.release_gate_passed`。

Golden Corpus 验收：`pytest tests/test_data_acquisition_e2e.py`（无外网）。

## 7. 配置项（`project.config`）

```json
{
  "data_spec_hints": {
    "entities_of_interest": ["client_id"],
    "target_variables": ["global_accuracy"],
    "preferred_sources": ["paper_table", "zenodo"]
  },
  "data_acquisition": {
    "coverage_gap_threshold": 70,
    "data_spec_gap_threshold": 60,
    "max_gap_rounds": 2,
    "auto_literature_discovery": true,
    "auto_literature_min_docs": 3,
    "auto_literature_max_papers": 5
  }
}
```

## 8. API 入口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/data-finder/search` | 发现 + DataSpec |
| POST | `/data-finder/acquire` | 完整采集流水线 |
| POST | `/data-finder/gap-enrich` | Gap 补搜 |
| POST | `/data-finder/figures/{id}/review` | 图表复核 → re-merge |

## 9. 可观测性

`data_acquisition.step_details` 每步含：

- `duration_ms` — 耗时
- `error_code` — 失败时异常类型，成功为 `null`

`stats.total_duration_ms` 为各步之和。

## 10. 测试

```bash
cd backend
pytest tests/test_phase1_data_integration.py \
       tests/test_phase2_data_integration.py \
       tests/test_phase3_data_integration.py \
       tests/test_phase4_data_integration.py \
       tests/test_phase5_data_integration.py \
       tests/test_phase6_data_integration.py \
       tests/test_data_acquisition_e2e.py -q
```

带 `@pytest.mark.live` 的外网测试（若有）仅 nightly 运行：`pytest -m live`。
