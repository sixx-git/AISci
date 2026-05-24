# AI Scientist - 基于 Qwen 的智能科研助手

## 项目简介

本项目是为**挑战杯 XH-202619**开发的基于 Qwen/千问大模型的 AI Scientist 系统。系统集成了智能文献检索、自动研究报告生成、学术对话等功能，旨在通过 AI 技术提升科研效率。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + MySQL
- **前端**: React + Vite + Ant Design
- **向量检索**: FAISS
- **大模型**: 阿里千问 (Qwen)

## 项目结构

```
AISci/
├── backend/                 # 后端服务
│   └── app/
│       ├── api/            # API 路由
│       ├── core/           # 核心配置
│       ├── models/         # 数据模型
│       ├── schemas/        # Pydantic schemas
│       ├── services/       # 业务逻辑层
│       └── utils/          # 工具函数
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── pages/          # 页面
│   │   ├── services/       # API 服务
│   │   └── styles/         # 样式
│   └── public/
├── data/                   # 数据目录
├── storage/                # 存储目录
├── scripts/                # 脚本目录
├── docs/                   # 文档目录
├── tests/                  # 测试目录
├── requirements.txt        # Python 依赖
└── README.md              # 项目说明
```

## 功能特性

### 1. 智能研究报告生成
- 基于研究主题自动生成文献综述
- 支持多种研究类型（文献综述、研究 proposal、实验设计等）
- 关键词提取和分析

### 2. 学术对话
- 与 AI 进行专业的学术讨论
- 基于 RAG 的文献检索增强
- 会话历史管理

### 3. 文献管理
- 文档上传和存储
- 自动向量化和索引
- 智能语义检索

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0+

### 1. 克隆项目

```bash
git clone <repository-url>
cd AISci
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置信息
```

### 3. 数据库配置

创建 MySQL 数据库：

```sql
CREATE DATABASE aiscientist CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

更新 `.env` 中的数据库连接信息。

### 4. 安装后端依赖

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
```

### 5. 初始化数据库

```bash
cd ..
python scripts/init_db.py
```

### 6. 启动后端服务

```bash
# Windows
scripts\start_backend.bat
# Linux/Mac
bash scripts/start_backend.sh

# 或直接使用
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 http://localhost:8000 启动，API 文档可访问 http://localhost:8000/docs

### 7. 安装前端依赖

```bash
cd frontend
npm install
```

### 8. 启动前端服务

```bash
npm run dev
```

前端将在 http://localhost:3000 启动。

## 开发路线图

### Phase 1: MVP 核心功能 (当前)
- [x] 项目基础架构搭建
- [x] 后端 FastAPI 框架
- [x] 前端 React + Vite 框架
- [x] 基础数据库模型
- [x] 千问 API 集成
- [x] FAISS 向量检索基础
- [x] 研究报告生成功能
- [x] 学术对话功能
- [x] 文献上传功能

### Phase 2: 功能增强
- [ ] 支持更多文档格式解析 (PDF, DOCX, CSV)
- [ ] 文献元数据提取
- [ ] 研究报告导出功能 (PDF, Word)
- [ ] 用户认证系统
- [ ] 项目管理功能
- [ ] 多轮对话优化

### Phase 3: 高级特性
- [ ] 文献引用网络分析
- [ ] 研究趋势可视化
- [ ] 实验数据可视化
- [ ] 多语言支持
- [ ] 模型微调支持
- [ ] 分布式向量检索

### Phase 4: 生产就绪
- [ ] 性能优化
- [ ] 缓存机制
- [ ] 日志系统完善
- [ ] 单元测试和集成测试
- [ ] CI/CD 流程
- [ ] Docker 容器化
- [ ] 部署文档

## API 文档

启动后端服务后，访问以下地址查看完整的 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 主要 API 端点

### 研究相关
- `POST /api/v1/research/generate` - 生成研究报告

### 对话相关
- `POST /api/v1/chat/message` - 发送对话消息

### 文档相关
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/list` - 获取文档列表

## 配置说明

### 千问 API 配置

1. 注册阿里云账号并开通百炼/千问服务
2. 获取 API Key
3. 在 `.env` 文件中配置：

```
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen-max
```

### 向量模型配置

默认使用 `sentence-transformers` 库的多语言模型，首次运行时会自动下载。

## 开发指南

### 后端开发

后端采用分层架构：
- `api/`: API 路由层，处理 HTTP 请求
- `services/`: 业务逻辑层，核心功能实现
- `models/`: 数据模型层，数据库表定义
- `schemas/`: Pydantic 模式，请求/响应验证

### 前端开发

前端采用组件化开发：
- `pages/`: 页面组件
- `components/`: 可复用组件
- `services/`: API 调用封装

### 代码规范

- Python: 遵循 PEP 8
- JavaScript/React: 使用 ESLint
- 提交信息: 使用清晰的描述

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

本项目仅供挑战杯参赛使用。

## 联系方式

如有问题，请联系项目维护者。

---

**挑战杯 XH-202619 - 基于国产开源大模型的 AI Scientist 的研发与应用**
