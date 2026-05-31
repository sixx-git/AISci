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

# 运行特定标记的测试
pytest tests/ -v -m agent              # 只运行 Agent 测试
pytest tests/ -v -m "not integration"  # 排除集成测试

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## 测试内容

- 健康检查 API 测试
- 数据库操作测试（CRUD）
- 文档解析测试（PDF / TXT / DOCX）
- 向量检索测试
- Agent 单元测试（Mock，不消耗 LLM Token）
- Pipeline 服务测试

所有 Agent 测试使用 Mock，避免调用真实 LLM API。

## Mock 测试说明

Mock 的主要组件：
- Qwen LLM 调用
- SentenceTransformer 编码
- FAISS 索引操作
- 文件系统操作
- 数据库写入操作

## 常见问题

### 模块导入错误

确保在正确的目录中运行：

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
pip install sentence-transformers faiss-cpu numpy
```

## 开发新测试

测试命名约定：
- 测试文件：`test_*.py`
- 测试类：`Test*`
- 测试函数：`test_*`

```python
import pytest
from unittest.mock import Mock, patch

def test_example_functionality(db_session, test_project):
    assert test_project.name is not None

    with patch('app.services.some_service') as mock_service:
        mock_service.some_method = Mock(return_value="mocked")
        result = call_function()
        assert result == "mocked"
```