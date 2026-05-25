# 文献解析模块测试

## 运行测试

```bash
# 进入后端目录
cd backend

# 运行单元测试
python -m pytest tests/test_document_parser.py -v

# 或者直接运行测试文件
python tests/test_document_parser.py
```

## 测试内容

### 1. 解析器初始化测试
- 测试解析器是否能正常初始化
- 测试后端选择功能

### 2. 文本切片测试
- 测试按中文字符数切片
- 测试切片大小控制
- 测试重叠功能

### 3. 元数据提取测试
- 测试标题提取
- 测试作者提取
- 测试摘要提取
- 测试参考文献提取

### 4. 完整工作流测试
- 测试文件解析
- 测试数据库写入
- 测试错误处理

### 5. 后端切换测试
- 测试 pypdf 后端
- 测试 pymupdf 后端

## 准备真实 PDF 测试

如果您有真实的 PDF 文件需要测试：

```python
from app.services.document_parser import parse_and_save_document
from app.core.database import init_db

# 获取数据库会话
engine, SessionLocal = init_db()
db = SessionLocal()

# 解析 PDF
try:
    document, chunks = parse_and_save_document(
        db=db,
        file_path="/path/to/your/document.pdf",
        project_id="your_project_id"
    )
    print(f"解析成功！文档 ID: {document.id}")
    print(f"生成 {len(chunks)} 个切片")
finally:
    db.close()
```

## 常见问题

### 1. 模块导入错误
确保在正确的目录中运行测试，并已安装所有依赖：
```bash
pip install -r ../requirements.txt
```

### 2. 测试数据库问题
测试使用内存 SQLite 数据库，不需要额外配置。

### 3. PDF 库缺失
安装缺失的库：
```bash
pip install pymupdf pypdf
```
