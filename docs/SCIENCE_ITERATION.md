# 科学自迭代（Science Iteration）

AISci 在标准 Pipeline 中支持「假设溯源 → 轻量 refine → 资料补充计划 → 会话持久化」闭环，与 Discovery 多轮回退、Teaching 自动精化并行存在，互不替代。

## 配置

写入 `project.config.science_iteration`（也可通过 Pipeline `run_options` 覆盖）：

| 字段 | 默认 | 说明 |
|------|------|------|
| `enabled` | `true` | 是否启用自迭代编排 |
| `max_rounds` | `2` | 标准模式最多 refine 轮次（含初始） |
| `auto_triggers` | `evidence_weak`, `review_reject`, `validation_fail` | 自动触发类型 |
| `min_ensemble_score` | `7.5` | 评审分阈值（未 Accept 时可 refine） |
| `auto_literature_on_weak_evidence` | `true` | 证据弱时自动补文献 |
| `show_iteration_in_report` | `true` | 报告中展示迭代摘要（预留） |

示例：

```json
{
  "science_iteration": {
    "enabled": true,
    "max_rounds": 2,
    "min_ensemble_score": 7.5
  }
}
```

## API

前缀：`/api/v1/science-iteration`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/projects/{project_id}/hypotheses/{hypothesis_id}/provenance` | 假设溯源（来源/依据/验证） |
| GET | `/runs/{run_id}/session` | 自迭代会话（轮次、快照、资料计划） |
| GET | `/projects/{project_id}/config` | 解析后的迭代配置 |

## Pipeline 钩子

`ScienceIterationOrchestrator` 在 `pipeline_service` 中挂载：

1. **假设生成后**：记录 `initial` 里程碑；可选 `maybe_supplement_literature_on_weak_evidence`
2. **假设评审后**：记录 `hypothesis_review`；若未 Accept 且非 Discovery，执行 `maybe_run_standard_refinement`（单轮重跑 P4→证据链→假设树→P5）
3. **小样验证后**：沙箱失败时记录 `validation_fail`
4. **Pipeline 完成**：`finalize_session` 写入 `extra_metadata.science_iteration`

## 前端

- **假设页**：证据链抽屉新增「来源」「验证」Tab，调用 provenance API
- **闭环总览**：`IterationRoundPanel` 展示轮次、评分 delta、资料补充计划；与 `VersionComparePanel` 联动

## 与 Discovery / Teaching 的关系

- **Discovery**：仍使用 `discovery_loop` 多轮回退；标准 refine 在 `pipeline_mode=discovery` 时跳过
- **Teaching**：Teaching 自动精化针对实验/报告；Science Iteration 针对假设与证据层
- **version_snapshots**：各闭环共用快照结构，便于 `VersionComparePanel` 对比

## 相关文件

- `backend/app/services/science_iteration_service.py`
- `backend/app/api/science_iteration.py`
- `backend/app/schemas/science_iteration.py`
- `frontend/src/services/scienceIterationService.ts`
- `frontend/src/components/IterationRoundPanel.tsx`
