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
4. 运行测试脚本验证连通性：
   ```bash
   cd backend
   python scripts/test_qwen_client.py
   ```

### Q: 报错 "Client.__init__() got an unexpected keyword argument 'proxies'"
A: 这是由于 openai / httpx 版本不兼容导致的。请执行：
```bash
pip uninstall -y openai httpx
pip install "openai>=1.55.3,<3.0" "httpx==0.27.2"
```
然后重启后端。

**原因说明**：httpx 0.28+ 移除了 `proxies` 参数，而 openai >= 1.55 需要 httpx <= 0.27 才能兼容。本项目固定 httpx==0.27.2 避免此问题。

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
- 运行端到端验收检查：
  ```bash
  python scripts/check_e2e.py
  ```
- 开始使用 AI Scientist!

---

## 端到端验收

项目提供了自动化验收脚本 `scripts/check_e2e.py`，用于检查后端所有核心接口是否正常工作。

```bash
# 确保后端已启动（注意：必须在 backend/ 目录下启动，否则 .env 无法正确加载）
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端中运行验收
python scripts/check_e2e.py
```

脚本检查项包括：
1. 后端健康检查 `/health`
2. 项目列表 `/api/v1/projects`
3. 千问客户端诊断 `/api/v1/diagnose/qwen-client`
4. 文献搜索接口 `/api/v1/literature/sources` 和 arXiv 搜索
5. 数据集接口 `/api/v1/datasets`
6. Pipeline 运行接口
7. 报告接口 `/api/v1/reports`
8. Agent 接口可达性
9. 核心 Skill 文件完整性
10. 环境变量配置检查

LLM 检查仅验证 API Key 是否配置，不实际消耗 token。

## 最终报告验收标准

生成的研究报告必须满足以下赛题规范（XH-202619）：

| 检查项 | 要求 |
|--------|------|
| **12 字段完整性** | Paper Title / Abstract / Problem Statement / Rationale / Technical Details / Datasets / Source / Target / Methods / Experiments / Results / References 均存在 |
| **Technical Details** | 必须明确提及 Qwen/千问 和阿里云百炼作为核心技术 |
| **References** | 必须来自真实文献，不得包含 unknown / 未知作者 / placeholder / ViT Paper / Cross-modal Paper |
| **Results** | 必须区分 actual_results / simulated_results / expected_results |
| **Datasets** | 必须有真实数据来源 URL 或明确标记为"拟采集" |
| **Charts/Plots** | 每张图表必须标记 `is_generated_from_real_data` 和 `source_dataset_id` |
| **Non-Qwen Models** | 报告中不得出现 GPT-4、Llama、Claude 等非 Qwen 模型名 |

## Reference 真实性要求

- **禁止 LLM 自行编造 References**，所有引用必须来自文献库（Document / Evidence / citation_map）
- 未验证的引用将在报告生成时自动清除
- 导入文献方式：
  1. arXiv URL 直接导入
  2. BibTeX 批量导入
  3. 本地上传 PDF + 自动解析
- 报告中 References 为 0 时，会明确显示："缺少真实引用，需先导入 arXiv/BibTeX/PDF 文献。"

## Windows PDF 导出依赖

在 Windows 环境下，PDF 导出功能需要以下依赖：
- `requirements.txt` 中已包含 `weasyprint` 依赖
- 如遇到 WeasyPrint 安装问题，可参考 [WeasyPrint Windows 安装指南](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)
- PDF 导出失败不会影响 Markdown 和 JSON 格式的报告，其他功能正常使用

## 千问 / 百炼配置说明

- API Key 获取：访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
- 在 `.env` 中配置 `QWEN_API_KEY=your_key_here`
- 可选模型：`qwen-max`（推荐）、`qwen-plus`、`qwen-turbo`
- 运行 `python scripts/check_e2e.py` 可自动诊断千问客户端连通性
