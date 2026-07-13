# 多源数据采集 — 高级工具运维手册（非 Pipeline 默认阶段）

面向 **Data Finder 高级工具面板** 与手动 API，**不属于**默认 8 阶段 Pipeline。

## 1. 设计原则（2026）

**默认 Pipeline**：上传数据集 → 实验设计（含数据充分性评估）→ 小样验证。

| 能力 | 默认 Pipeline | 独立高级工具 |
|------|---------------|-------------|
| 上传数据集 + 充分性评估 | ✅ | — |
| 缺口时 DatasetDiscovery 推荐 URL | ✅ 实验设计阶段 | — |
| 领域数据集检索 / 论文建库 | ❌ | `POST /data-finder/*` |
| Gap 多轮补搜 | ❌（`enable_gap_search` 默认关） | `POST /gap-enrich` |

## 2. 默认 Pipeline 数据流

```
用户上传 CSV
    → 引擎探查 + DatasetSemanticUnderstanding
    → 实验设计 Agent
    → DataAdequacyAssessment（假设 ↔ 数据是否匹配）
    → 不充分时 DatasetDiscovery 返回推荐数据集 URL
    → 可执行性 Gate → 小样验证（仅 adequacy≠inadequate）
```

## 3. 独立论文建库（高级工具）

适用于需要从**已入库论文**抽取表格/图表并合并为 Analysis Bundle 的场景（不参与 Pipeline）：

| 步骤 | 说明 |
|------|------|
| discover | 论文链接挖掘 + 图表检测 + VLM |
| fetch_supplementary | 补充材料 |
| extract | PDF 表格抽取 |
| fetch_external | HF/Zenodo 自动 import（每轮 ≤2） |
| align / merge | Schema 对齐与 CSV 合并 |
| gap_loop | 可选，Coverage 未达标时多轮补搜 |

### 调用方式

**HTTP API**

```http
POST /api/v1/data-finder/build-library
{
  "project_id": "...",
  "research_question": "...",
  "auto_import": true,
  "enable_gap_search": false
}
```

**CLI 脚本**

```bash
cd backend
python scripts/run_paper_extraction_pipeline.py <project_id>
python scripts/run_paper_extraction_pipeline.py <project_id> --gap-search
```

**分步 API**（无需一次跑满建库）：

- `POST /extract-tables`
- `POST /align-schema`
- `POST /merge`
- `GET /bundle/download`

**Python 模块**

```python
from app.services.data_finder_service import get_data_finder_service

svc = get_data_finder_service(db)
await svc.run_paper_extraction_pipeline(project_id, research_question)
```

实现位于 `app/services/paper_extraction_pipeline.py`。

## 4. 支持的数据来源

| 来源 | Pipeline 检索 | 建库工具额外能力 |
|------|---------------|------------------|
| HuggingFace | ✅ | ✅ 可自动 import 样例行 |
| Zenodo / Figshare | ✅ | ✅ 可自动 import（≤25MB） |
| Kaggle / 静态索引 | ✅ catalog | ❌ 需用户下载上传 |
| OpenAlex / GEO | ✅ 元数据 | ❌ 需用户跟链 |
| 项目 PDF | —（文献阶段已处理） | 表格 / 图表 / SI |

## 5. 输出物

### Pipeline（`dataset_discovery`）

- `data_spec` / `data_requirements`
- `external_candidates`
- `assets_index`

### 建库工具（`paper_extraction_library`）

- `extracted_tables` / `figures` / `merged.csv`
- `analysis_bundle.zip`（Release Gate 通过后）
- `coverage_report.json`
- `release_gate` 验收报告

## 6. Release Gate

仅在建库工具路径生效：要求合并 CSV ≥1 行、provenance 覆盖等（见 `evaluate_release_gate`）。Pipeline 检索路径**不使用** Release Gate。

## 7. 配置项

`project.config.data_acquisition.mode` 已不再影响 Pipeline；历史 `full` 配置请改用 `build-library` API 或 CLI。

Gap 相关阈值（`coverage_gap_threshold` 等）仅在建库工具请求体或 `gap-enrich` 中传递。

## 8. 相关文件

| 文件 | 职责 |
|------|------|
| `app/services/data_finder_service.py` | 检索 + 分步抽取 |
| `app/services/paper_extraction_pipeline.py` | 独立建库流水线 |
| `app/services/data_acquisition_release_gate.py` | 建库验收 |
| `app/services/data_finder_gap_search.py` | Gap 补搜逻辑 |
| `scripts/run_paper_extraction_pipeline.py` | CLI 入口 |
| `scripts/run_data_search_quick.py` | 轻量检索 CLI |
