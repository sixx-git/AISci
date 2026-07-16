# 存储目录

项目运行时数据持久化目录，部分路径由 `backend/.env` 配置（如 `UPLOAD_DIR`、`VECTOR_STORE_PATH`）。

## 目录说明

| 路径 | 内容 |
|------|------|
| `faiss_index/` | FAISS 向量索引（文献 chunk 嵌入） |
| `uploads/` | 用户上传的 PDF / DOCX / TXT / MD / CSV |
| `reports/` | 生成的研究报告 Markdown 与 PDF |
| `audit/` | Pipeline 闭环审计链 `{run_id}.jsonl`（events / decisions / quality_trend 条目） |
| `evidence_chains/` | 假设结构化证据链 `{project_id}/{hypothesis_id}.json` |
| `catalog/` | 项目 Data Catalog `{project_id}/data_catalog.json` |
| `data_finder/` | Data Finder 结果、合并 CSV、Analysis-Ready Bundle |
| `feedback/` | Feedback Hub 全局约束 `{project_id}/constraints.json` |
| `pingfenbiao_jobs/` | 预测 Tab（pingfenbiao）任务与历史；由 `PINGFENBIAO_WORK_DIR` 指向 |

## 审计链格式

`audit/{run_id}.jsonl` 每行一条 JSON 记录，例如：

```json
{"record_type": "closed_loop_event", "run_id": "...", "type": "discovery_refine", "at": "...", ...}
{"record_type": "quality_trend_entry", "run_id": "...", "stage": "discovery_r2", "cqs": 72.5, ...}
{"record_type": "closed_loop_decision", "run_id": "...", "trigger": "...", "action": "...", ...}
```

可通过 `GET /api/v1/pipeline/audit-export/{run_id}` 导出完整审计包（含 metadata 快照 + jsonl 全量）。

## Data Finder Bundle

`data_finder/{project_id}/bundle/` 包含：

- `merged.csv` — 合并（及可选清洗后）表格，含 `_provenance_*`、`_table_row_id`、`_data_citation_id`
- `schema.json` — 列类型推断
- `provenance.jsonl` — 表级与行级 provenance
- `quality_report.json` — 清洗与合并质量报告
- `README.md` — Bundle 说明

## 注意事项

- 本目录通常 **不纳入 Git**（已在 `.gitignore` 中忽略），仅保留 `README.md` 作说明。
- 删除项目或 run 记录不会自动清理此处文件；如需释放空间请手动清理对应子目录。
