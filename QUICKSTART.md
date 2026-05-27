# AI Scientist - 快速入门指南

## 🚀 5 分钟快速开始

### 前置要求

- **Python 3.10 / 3.11 / 3.12** (推荐)
- **暂不建议 Python 3.13**：部分依赖（SQLAlchemy、FAISS、sentence-transformers）可能存在兼容问题
- **Node.js 18+**
- **MySQL 8.0+** (可选，默认使用 SQLite)

---

## 快速设置 (推荐)

### Windows 用户

```batch
# 1. 设置后端
scripts\setup_backend.bat

# 2. 设置前端 (新开一个终端)
scripts\setup_frontend.bat

# 3. 配置 .env 文件 (编辑项目根目录下的 .env)

# 4. 初始化数据库
python scripts\init_db.py

# 5. 启动开发环境
scripts\run_dev.bat
```

### Linux/Mac 用户

```bash
# 1. 设置后端
bash scripts/setup_backend.sh

# 2. 设置前端 (新开一个终端)
bash scripts/setup_frontend.sh

# 3. 配置 .env 文件 (编辑项目根目录下的 .env)

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动开发环境
bash scripts/run_dev.sh
```

---

## 详细设置步骤

### 1. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件，至少配置以下内容：

```env
# 千问 API (必需)
QWEN_API_KEY=your_actual_api_key_here

# 数据库配置
# 方式 A: SQLite (默认，无需安装数据库)
DATABASE_URL=sqlite:///./data/aiscientist.db

# 方式 B: MySQL (可选，需要安装 MySQL)
# DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/aiscientist
```

### 2. 获取千问 API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 注册/登录账号
3. 创建 API Key
4. 将 API Key 填入 `.env` 文件

### 3. 创建 MySQL 数据库 (如果使用 MySQL)

如果选择使用 MySQL 而不是默认的 SQLite，需要先创建数据库：

```sql
CREATE DATABASE aiscientist CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 初始化数据库

```bash
python scripts/init_db.py
```

### 5. 启动开发环境

**Windows:**
```batch
scripts\run_dev.bat
```

**Linux/Mac:**
```bash
bash scripts/run_dev.sh
```

### 6. 访问应用

- **前端界面**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

---

## 项目结构说明

```
AISci/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/        # API 路由
│   │   ├── core/       # 配置和数据库
│   │   ├── models/     # 数据模型
│   │   ├── schemas/    # Pydantic 模型
│   │   ├── services/   # 业务逻辑
│   │   └── main.py
├── frontend/            # React + Vite 前端
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
├── data/                # 数据文件
├── storage/             # 存储 (上传的文件、FAISS 索引)
├── scripts/             # 自动化脚本
├── tests/               # 测试文件
├── requirements.txt     # Python 依赖
└── .env.example        # 环境变量模板
```

---

## 主要功能

### 1. 智能研究报告
- 输入研究主题和关键词
- AI 自动生成专业的研究报告
- 支持多种研究类型

### 2. 学术对话
- 与 AI 进行专业学术交流
- 基于上传的文献进行 RAG 检索
- 会话历史记录

### 3. 文献管理
- 上传文献 (支持 TXT, PDF, DOCX, CSV, MD)
- 自动向量化和索引
- 智能语义检索

---

## 常见问题

### Q: 提示 "未找到 Python"
A: 请安装 Python 3.10 / 3.11 / 3.12（暂不建议 3.13），并确保添加到 PATH

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

### Q: 端口被占用
A: 
- 后端默认端口: 8000 (可在 .env 中修改)
- 前端默认端口: 3000 (可在 vite.config.js 中修改)

---

## 手动启动 (不使用脚本)

### 后端

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

---

## 下一步

- 阅读 [README.md](./README.md) 了解更多详情
- 查看 [API 文档](http://localhost:8000/docs)
- 开始使用 AI Scientist!

祝使用愉快! 🎉
