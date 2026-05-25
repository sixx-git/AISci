# AI Scientist 后端测试

## 目录结构

```
tests/
├── README.md              # 本文档
├── conftest.py            # pytest 配置和 fixtures
├── pytest.ini             # pytest 配置文件
│
├── 基础测试
├── test_health_check.py   # 健康检查 API 测试
├── test_database.py       # 数据库操作测试
│
├── 功能测试
├── test_document_parser.py  # 文档解析测试
├── test_vector_search.py   # 向量检索测试
│
├── Agent 测试
├── test_agents.py        # 所有 Agent 的 Mock 测试（推荐使用）
├── test_problem_understanding_agent.py
├── test_literature_mining_agent.py
├── test_knowledge_gap_agent.py
├── test_hypothesis_generation_agent.py
├── test_hypothesis_review_agent.py
├── test_experiment_design_agent.py
├── test_small_validation_agent.py
├── test_report_generation_agent.py
│
├── Pipeline 测试
└── test_pipeline.py      # Pipeline 服务 Mock 测试
```

## 环境准备

### 1. 安装依赖

```bash
# 进入后端目录
cd backend

# 安装测试依赖
pip install pytest pytest-asyncio
```

### 2. 确保项目可运行

```bash
# 验证依赖安装
python -c "import app.main"
```

## 运行测试

### 运行所有测试

```bash
# 使用 pytest 运行所有测试
pytest tests/ -v

# 或者使用 python -m pytest
python -m pytest tests/ -v
```

### 运行特定测试文件

```bash
# 运行健康检查测试
pytest tests/test_health_check.py -v

# 运行数据库测试
pytest tests/test_database.py -v

# 运行 Agent 测试
pytest tests/test_agents.py -v

# 运行 Pipeline 测试
pytest tests/test_pipeline.py -v
```

### 运行特定标记的测试

```bash
# 只运行 Agent 测试
pytest tests/ -v -m agent

# 只运行单元测试（不含集成测试）
pytest tests/ -v -m "not integration"
```

### 生成测试报告

```bash
# 生成详细的测试报告
pytest tests/ -v --tb=long

# 生成覆盖率报告（需要安装 pytest-cov）
pytest tests/ --cov=app --cov-report=html
```

## 测试内容说明

### 1. 健康检查测试 (`test_health_check.py`)
- 测试根路径端点是否正常
- 测试健康检查端点是否正常
- 测试 API 文档页面是否可访问
- 测试 ReDoc 文档页面是否可访问

### 2. 数据库测试 (`test_database.py`)
- 测试数据库连接和初始化
- 测试项目 CRUD 操作
- 测试文档 CRUD 操作
- 测试文本块 CRUD 操作
- 测试模型关系

### 3. 文档解析测试 (`test_document_parser.py`)
- 测试解析器初始化
- 测试文本切片功能
- 测试元数据提取
- 测试完整工作流
- 测试后端切换（pypdf/pymupdf）

### 4. 向量检索测试 (`test_vector_search.py`)
- 测试向量服务初始化
- 测试添加文档到向量库
- 测试搜索功能
- 测试文本分割
- 使用 Mock 避免真实的向量计算

### 5. Agent 测试 (`test_agents.py`)
- 测试 ProblemUnderstandingAgent
- 测试 LiteratureMiningAgent
- 测试 KnowledgeGapAgent
- 测试 HypothesisGenerationAgent
- 测试 HypothesisReviewAgent
- 测试 ExperimentDesignAgent
- 测试 SmallValidationAgent
- 测试 ReportGenerationAgent

所有 Agent 测试都使用 Mock，不调用真实的 LLM API。

### 6. Pipeline 测试 (`test_pipeline.py`)
- 测试 Pipeline 服务初始化
- 测试各阶段执行
- 测试阶段追踪
- 使用 Mock 测试完整流程

## Mock 测试说明

本测试套件大量使用 Mock 来：
- 避免调用真实的 LLM API（节省成本）
- 避免耗时的向量计算
- 确保测试快速、可靠
- 隔离测试各个组件

Mock 的主要组件：
- Qwen LLM 调用
- SentenceTransformer 编码
- FAISS 索引操作
- 文件系统操作
- 数据库写入操作

## 前端测试

前端测试请参考 [frontend/TEST_CHECKLIST.md](../frontend/TEST_CHECKLIST.md)

## Demo 测试数据

使用 Demo 数据进行端到端测试，请参考 [data/demo/DEMO_COMPLETE.md](../../data/demo/DEMO_COMPLETE.md)

## 常见问题

### 1. 模块导入错误

确保在正确的目录中运行测试：

```bash
cd backend
pytest tests/ -v
```

或者确保项目根目录在 PYTHONPATH 中：

```bash
export PYTHONPATH=$PWD:$PYTHONPATH
pytest tests/ -v
```

### 2. 测试数据库问题

测试使用内存 SQLite 数据库，不需要额外配置。所有数据在测试结束后自动清理。

### 3. PDF 库缺失

如果需要测试真实的 PDF 解析：

```bash
pip install pymupdf pypdf
```

### 4. 测试速度太慢

使用标记跳过慢速测试：

```bash
pytest tests/ -v -m "not slow"
```

### 5. 向量测试失败

向量测试使用 Mock，不需要真实的 embedding 模型。如果仍然失败，请检查依赖：

```bash
pip install sentence-transformers faiss-cpu numpy
```

## 持续集成

在 CI/CD 环境中运行测试：

```bash
# 安装依赖
pip install -r requirements.txt
pip install pytest

# 运行测试（排除需要真实 API 的测试）
pytest tests/ -v -m "not integration"
```

## 开发新测试

### 测试命名约定

- 测试文件：`test_*.py`
- 测试类：`Test*`
- 测试函数：`test_*`

### 添加新测试

1. 在 `tests/` 目录中创建新文件
2. 使用 `conftest.py` 中的 fixtures
3. 为需要的外部依赖添加 Mock
4. 运行测试验证

### 测试示例

```python
import pytest
from unittest.mock import Mock, patch

def test_example_functionality(db_session, test_project):
    # 测试代码
    assert test_project.name is not None
    
    # 使用 Mock
    with patch('app.services.some_service') as mock_service:
        mock_service.some_method = Mock(return_value="mocked")
        result = call_function()
        assert result == "mocked"
```

## 下一步

- 查看前端测试清单：[frontend/TEST_CHECKLIST.md](../frontend/TEST_CHECKLIST.md)
- 使用 Demo 数据测试：[data/demo/DEMO_COMPLETE.md](../../data/demo/DEMO_COMPLETE.md)
- 阅读项目主文档：[README.md](../README.md)
