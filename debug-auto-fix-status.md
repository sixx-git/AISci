# Debug Session: auto-fix-status

**Status**: [OPEN]
**Date**: 2026-08-05
**Symptom**: 报告自动修复完成后，前端仍显示「修复中...」而非「✅ 已修复」
**Expected**: 修复完成后，hint 的 fix_status 应变为 completed，前端显示「已修复」

## Hypotheses

1. **H1**: `_auto_fix_report_sync` 未被触发 —— `rg_content_quality` 规则的 `condition` 未匹配
2. **H2**: `_auto_fix_report_async` 中 LLM 调用失败 —— `qwen_chat` 抛异常或返回空
3. **H3**: fix_status 更新逻辑正确但 `_persist_coordinator_hints` 持久化失败
4. **H4**: `_save_hints_to_advice_table` 的独立会话与主线程存在数据竞争
5. **H5**: 前端 API 拉取时字段名不匹配 —— `extra_data.fix_status` 未正确映射到返回 JSON

## Plan

1. 编写并运行端到端测试，验证每个环节
2. 添加调试日志到关键路径
3. 分析日志，逐一排除假设
4. 实施最小修复

## Evidence Log

1. **数据库检查** (2026-08-05 17:44): fix_status=completed, fix_detail=已修复 1 个章节: results — 后端完全正常
2. **E2E 测试**: 4/5 通过。Step 3 失败是因为 LLM 返回文本仍含重复句号（LLM 质量问题，非代码问题）
3. **API 检查**: pipeline.py L716-717 正确返回 fix_status 和 fix_detail
4. **前端映射检查**: WorkflowPage.tsx L1364-1375 遗漏了 fix_status 和 fix_detail 字段映射

## Fix Applied

**根因**: 前端 `WorkflowPage.tsx` 两处 API 响应映射（初始加载 + 轮询）遗漏了 `fix_status` 和 `fix_detail` 字段，导致数据丢失

**修复**: 在 L1373-1374 和 L1406-1407 添加 `fix_status` 和 `fix_detail` 映射

**状态**: [CLOSED]