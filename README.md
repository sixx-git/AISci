# AI Scientist - 基于 Qwen 的智能科研助手

<p align="center">
  <b>挑战杯 XH-202619</b> |
  基于千问大模型的智能科研系统
</p>

---

## 📖 快速开始

**第一次使用？** 请查看 [快速入门指南](./QUICKSTART.md) 以获得详细的分步说明。

### 🚀 一键启动 (推荐)

#### Windows 用户
```batch
# 1. 设置后端
scripts\setup_backend.bat

# 2. 设置前端
scripts\setup_frontend.bat

# 3. 编辑 .env 文件 (填入你的配置)

# 4. 初始化数据库
python scripts\init_db.py

# 5. 启动开发环境
scripts\run_dev.bat
```

#### Linux/Mac 用户
```bash
# 1. 设置后端
bash scripts/setup_backend.sh

# 2. 设置前端
bash scripts/setup_frontend.sh

# 3. 编辑 .env 文件 (填入你的配置)

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动开发环境
bash scripts/run_dev.sh
```

启动成功后访问：
- **前端界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs

---

## 📋 项目简介

本项目是为**挑战杯 XH-202619**开发的基于 Qwen/千问大模型的 AI Scientist 系统。系统集成了智能文献检索、自动研究报告生成、学术对话等功能，旨在通过 AI 技术提升科研效率。

### ✨ 主要功能

1. **🤖 智能研究报告生成**
   - 基于研究主题自动生成文献综述
   - 支持多种研究类型（文献综述、研究 proposal、实验设计等）
   - 关键词提取和分析

2. **💬 学术对话**
   - 与 AI 进行专业的学术讨论
   - 基于 RAG 的文献检索增强
   - 会话历史记录

3. **📚 文献管理**
   - 支持多种格式上传 (TXT, PDF, DOCX, CSV, MD)
   - 自动向量化和索引
   - 智能语义检索

---

## 🛠️ 技术栈

| 组件 | 技术选型 |
|------|---------|
| **后端框架** | FastAPI |
| **前端框架** | React + Vite |
| **UI 组件库** | Ant Design |
| **数据库** | MySQL / SQLite |
| **ORM** | SQLAlchemy |
| **向量检索** | FAISS |
| **嵌入模型** | Sentence-Transformers |
| **大模型** | 阿里千问 (Qwen) |

---

## 📁 项目结构

```
AISci/
├── backend/              # FastAPI 后端
│   └── app/
│       ├── api/         # API 路由
│       │   ├── research.py
│       │   ├── chat.py
│       │   └── documents.py
│       ├── core/        # 配置和数据库
│       ├── models/      # 数据模型
│       ├── schemas/     # Pydantic 模型
│       ├── services/    # 业务逻辑
│       └── main.py
├── frontend/            # React + Vite 前端
│   └── src/
│       ├── components/  # UI 组件
│       ├── pages/       # 页面组件
│       └── services/    # API 服务
├── data/                # 数据目录
├── storage/             # 存储 (FAISS 索引、上传文件)
├── scripts/             # 自动化脚本
│   ├── setup_backend.bat/sh
│   ├── setup_frontend.bat/sh
│   ├── run_dev.bat/sh
│   └── init_db.py
├── docs/                # 文档
├── tests/               # 测试
├── requirements.txt     # Python 依赖
├── .env.example        # 环境变量模板
├── QUICKSTART.md       # 快速入门
└── README.md
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

复制 `.env.example` 为 `.env` 并填入配置：

```env
# 应用配置
APP_NAME=AI Scientist
DEBUG=True
VERSION=0.1.0

# 后端服务
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 数据库
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aiscientist
# 或使用 SQLite (无需安装数据库)
# DATABASE_URL=sqlite:///./data/aiscientist.db

# 千问 API (必需)
QWEN_API_KEY=your_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

# 向量检索
VECTOR_STORE_PATH=./storage/faiss_index
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# 文件上传
UPLOAD_DIR=./storage/documents
MAX_UPLOAD_SIZE=52428800
ALLOWED_EXTENSIONS=txt,pdf,docx,md,csv

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 获取千问 API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 注册/登录账号
3. 创建 API Key
4. 将 API Key 填入 `.env` 文件

---

## 🖥️ 手动启动 (不使用脚本)

### 后端启动

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
cd ..
python scripts/init_db.py
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

---

## 📊 API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/research/generate` | 生成研究报告 |
| POST | `/api/v1/chat/message` | 发送聊天消息 |
| POST | `/api/v1/documents/upload` | 上传文档 |
| GET | `/api/v1/documents/list` | 获取文档列表 |

---

## 🗺️ 开发路线图

### Phase 1: MVP 核心功能 ✅
- [x] 项目基础架构
- [x] FastAPI 后端
- [x] React 前端
- [x] 数据库模型
- [x] 千问 API 集成
- [x] FAISS 向量检索
- [x] 研究报告生成
- [x] 学术对话
- [x] 文献上传
- [x] 自动化脚本

### Phase 2: 功能增强
- [ ] 用户认证系统
- [ ] 项目管理
- [ ] 研究报告导出 (PDF/Word)
- [ ] 文献元数据提取
- [ ] 多轮对话优化

### Phase 3: 高级特性
- [ ] 文献引用网络分析
- [ ] 研究趋势可视化
- [ ] 实验数据可视化
- [ ] 多语言支持
- [ ] 模型微调支持

### Phase 4: 生产就绪
- [ ] 性能优化
- [ ] 缓存机制
- [ ] 完整测试
- [ ] CI/CD 流程
- [ ] Docker 容器化
- [ ] 部署文档

---

## 🔧 开发指南

### 后端开发

后端采用分层架构：
- `api/` - API 路由层，处理 HTTP 请求
- `services/` - 业务逻辑层，核心功能实现
- `models/` - 数据模型层，数据库表定义
- `schemas/` - Pydantic 模式，请求/响应验证

### 前端开发

前端采用组件化开发：
- `pages/` - 页面组件
- `components/` - 可复用组件
- `services/` - API 调用封装

### 代码规范

- Python: 遵循 PEP 8
- JavaScript/React: 使用 ESLint
- 提交信息: 使用清晰的描述

---

## ❓ 常见问题

### Q: 提示 "未找到 Python"
A: 请先安装 Python 3.9 或更高版本，并确保添加到 PATH

### Q: 提示 "未找到 Node.js"
A: 请从 https://nodejs.org/ 下载并安装 Node.js 18+

### Q: MySQL 连接失败
A: 
1. 确认 MySQL 服务正在运行
2. 检查用户名和密码
3. 确认数据库已创建
4. 或改用 SQLite (注释掉 MySQL 配置，取消 SQLite 注释)

### Q: 千问 API 调用失败
A: 
1. 确认 API Key 正确
2. 确认账户有足够额度
3. 检查网络连接

更多问题请查看 [快速入门指南](./QUICKSTART.md)

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

本项目仅供挑战杯参赛使用。

---

## 📞 联系方式

如有问题，请联系项目维护者。

---

<p align="center">
  <b>挑战杯 XH-202619</b><br>
  基于国产开源大模型的 AI Scientist 的研发与应用
</p>
