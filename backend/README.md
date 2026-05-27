# AI Scientist Backend

基于 FastAPI 的后端服�?
## 📁 目录结构

```
backend/
├── app/
�?  ├── api/              # API 路由�?�?  �?  ├── projects.py  # 项目管理 API
�?  �?  ├── research.py  # 研究功能 API
�?  �?  ├── chat.py      # 对话功能 API
�?  �?  ├── documents.py # 文档管理 API
�?  �?  └── v1.py        # v1 路由整合
�?  ├── core/            # 核心配置
�?  �?  ├── config.py    # 配置管理
�?  �?  └── database.py  # 数据库配�?�?  ├── models/          # 数据模型
�?  �?  ├── project.py   # 项目模型
�?  �?  ├── research.py  # 研究模型
�?  �?  ├── chat.py      # 对话模型
�?  �?  └── documents.py # 文档模型
�?  ├── schemas/         # Pydantic Schemas
�?  �?  ├── common.py    # 通用响应格式
�?  �?  ├── project.py   # 项目相关 schemas
�?  �?  ├── research.py  # 研究相关 schemas
�?  �?  ├── chat.py      # 对话相关 schemas
�?  �?  └── documents.py # 文档相关 schemas
�?  ├── services/        # 业务逻辑�?�?  �?  ├── project_service.py  # 项目服务
�?  �?  ├── research_service.py # 研究服务
�?  �?  ├── chat_service.py     # 对话服务
�?  �?  ├── document_service.py # 文档服务
�?  �?  ├── llm_service.py      # LLM 服务
�?  �?  └── vector_service.py   # 向量检索服�?�?  └── main.py          # 应用入口
└── README.md            # 本文�?```

## 🚀 快速开�?
### 1. 环境要求

- Python 3.10 / 3.11 / 3.12 (推荐)
- **暂不建议 Python 3.13**：部分依赖（SQLAlchemy、FAISS、sentence-transformers）可能存在兼容问�?- MySQL 8.0+ (可选，默认使用 SQLite)

### 2. 安装依赖

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件�?
```env
# 应用配置
APP_NAME=AI Scientist
DEBUG=True
VERSION=0.1.0

# 后端服务
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 数据库配�?(默认使用 SQLite)
DATABASE_URL=sqlite:///../data/aiscientist.db
# 或使�?MySQL
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aiscientist

# 千问 API (可选，用于研究功能)
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

# 文件上传配置
UPLOAD_DIR=../storage/documents

# CORS 配置
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 4. 初始化数据库

```bash
cd ..
python scripts/init_db.py
```

### 5. 启动服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问：
- API 文档 (Swagger): http://localhost:8000/docs
- API 文档 (ReDoc): http://localhost:8000/redoc

## 📡 API 接口

### 1. 基础接口

#### 健康检�?```http
GET /health
```

响应示例�?```json
{
  "code": 200,
  "message": "服务运行正常",
  "data": {
    "status": "healthy",
    "version": "0.1.0"
  },
  "timestamp": "2024-01-01T00:00:00"
}
```

### 2. 项目管理接口

#### 创建项目
```http
POST /api/v1/projects
Content-Type: application/json

{
  "name": "AI 研究项目",
  "description": "这是一�?AI 研究项目",
  "keywords": "AI,机器学习,深度学习",
  "created_by": "admin"
}
```

#### 获取项目列表
```http
GET /api/v1/projects?page=1&page_size=20&keyword=AI
```

#### 获取项目详情
```http
GET /api/v1/projects/{project_id}
```

#### 更新项目
```http
PUT /api/v1/projects/{project_id}
Content-Type: application/json

{
  "name": "更新后的项目�?,
  "status": "in_progress"
}
```

#### 删除项目
```http
DELETE /api/v1/projects/{project_id}
```

### 3. 文件上传接口

#### 上传文件
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: [选择文件]
project_id: [项目ID，可选]
```

支持的文件格式：
- .pdf (PDF 文档)
- .docx (Word 文档)
- .txt (文本文件)
- .md (Markdown 文件)
- .csv (CSV 文件)

#### 获取项目文档列表
```http
GET /api/v1/documents?project_id={project_id}&page=1&page_size=20
```

## 📋 统一响应格式

所�?API 接口都使用统一的响应格式：

### 成功响应
```json
{
  "code": 200,
  "message": "success",
  "data": { /* 数据内容 */ },
  "timestamp": "2024-01-01T00:00:00"
}
```

### 分页响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [ /* 数据列表 */ ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  },
  "timestamp": "2024-01-01T00:00:00"
}
```

### 错误响应
```json
{
  "code": 400,
  "message": "错误信息",
  "details": [...]
}
```

## 🗄�?数据库表

### projects (项目�?
- id: 项目ID
- name: 项目名称
- description: 项目描述
- status: 项目状�?(draft/in_progress/completed/archived)
- keywords: 关键�?- created_by: 创建�?- created_at: 创建时间
- updated_at: 更新时间

### documents (文档�?
- id: 文档ID
- project_id: 所属项目ID
- filename: 原始文件�?- file_path: 文件存储路径
- file_type: 文件类型
- file_size: 文件大小
- content: 提取的文本内�?- summary: 文档摘要
- status: 处理状�?- error_message: 错误信息
- created_at: 上传时间
- updated_at: 更新时间

## 🛠�?开发指�?
### 添加新的 API 接口

1. �?`app/schemas/` 中定义请�?响应格式
2. �?`app/models/` 中定义数据模型（如果需要）
3. �?`app/services/` 中实现业务逻辑
4. �?`app/api/` 中创�?API 路由
5. �?`app/api/v1.py` 中注册路�?
### 数据库迁�?
如果需要修改数据库结构，可以使�?Alembic�?
```bash
# 初始�?alembic
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

## 📚 更多信息

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [项目根目�?README](../README.md)
