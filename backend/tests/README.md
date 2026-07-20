# AI Scientist 后端测试

## 环境准备

```bash
cd backend
pip install pytest pytest-asyncio
```

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# A 级优化批次回归（推荐 CI 使用）
pytest tests/test_batch*.py -v

# 运行特定标记的测试
pytest tests/ -v -m agent              # 只运行 Agent 测试
pytest tests/ -v -m "not integration"  # 排除集成测试

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## 测试内容

### 基础测试

- 健康检查 API
- 文档解析（PDF / TXT / DOCX）
- 向量检索
- Agent 单元测试（`test_agents.py`，Mock，不消耗 LLM Token）
- Pipeline 服务测试
- 独立 Pipeline Mock 验收：`python scripts/pipeline_e2e.py`（非 pytest）

### A 级优化批次回归（test_batch1–7）

| 文件 | 覆盖能力 |
|------|----------|
| `test_batch1_quality_hitl.py` | CQS 评分、quality_trend 富化、HITL Gate、闭环质量验收 |
| `test_batch2_verifiable_spec.py` | verifiable spec 构建、证据 Diff、provenance 摘要 |
| `test_batch3_data_finder.py` | CSV 清洗、Coverage 报告、Bundle、Entity 对齐前置 |
| `test_batch4_closed_loop.py` | Decision Log、迭代控制、可执行性 Gate、因果摘要 |
| `test_batch5_literature_figures.py` | 图表抽取、VLM 系列、文献 corpus、Figure 复核 |
| `test_batch6_feedback_catalog.py` | Feedback Hub、Multimodal evidence、Entity Resolution、Catalog |
| `test_batch7_provenance_audit.py` | 假设溯源时间线、LLM/规则假设修订、审计链 jsonl、data_citation 追溯 |

### 其他专项测试

- `test_fl_starter_pack.py` — FL Pack 挂载、领域、标准 Non-IID、Dirichlet/baseline 脚本
- `test_closed_loop_quality.py` — 闭环质量验收
- `test_hypothesis_tree.py` — 假设树剪枝
- `test_ensemble_review.py` — 集成评审
- `test_validation_feedback.py` — 验证反馈回灌
- `test_prompt_presets.py` — Prompt 范式预设 catalog / pack_d

## Mock 测试说明

Mock 的主要组件：

- Qwen LLM 调用（`USE_MOCK_LLM=true` 或 patch）
- SentenceTransformer 编码
- Zvec 向量索引操作
- 文件系统操作（批次测试多用 `tempfile.TemporaryDirectory`）
- 数据库写入操作

## 常见问题

### 模块导入错误

```bash
cd backend
pytest tests/ -v
```

### 测试速度太慢

```bash
pytest tests/ -v -m "not slow"
```

### 向量测试失败

```bash
pip install sentence-transformers zvec numpy
```

## 开发新测试

命名约定：

- 测试文件：`test_*.py`
- 测试类：`Test*`
- 测试函数：`test_*`

闭环相关新功能建议追加到对应 `test_batchN_*.py`，或新建批次文件以保持回归粒度清晰。
