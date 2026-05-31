# AI Scientist - 快速入门指南

## 🚀 5 分钟快速开始

### 前置要求

- **Python 3.10 / 3.11 / 3.12**（推荐）
- **暂不建议 Python 3.13**：部分依赖（SQLAlchemy、FAISS、sentence-transformers）可能存在兼容问题
- **Node.js 18+**
- **pnpm**（推荐 9.x）

---

## 快速设置（推荐）

### Windows 用户

```batch
# 1. 设置后端
scripts\setup_backend.bat

# 2. 设置前端（新开一个终端）
scripts\setup_frontend.bat

# 3. 配置 .env 文件
copy .env.example backend\.env
# 编辑 backend\.env，填入 QWEN_API_KEY
# 如暂时无 Key，设置 USE_MOCK_LLM=true

# 4. 启动开发环境
scripts\run_dev.bat
```

### Linux/Mac 用户

```bash
# 1. 设置后端
bash scripts/setup_backend.sh

# 2. 设置前端（新开一个终端）
bash scripts/setup_frontend.sh

# 3. 配置 .env 文件
cp .env.example backend/.env
# 编辑 backend/.env，填入 QWEN_API_KEY
# 如暂时无 Key，设置 USE_MOCK_LLM=true

# 4. 启动开发环境
bash scripts/run_dev.sh
```

---

## 启动后访问

| 地址 | 说明 |
|------|------|
| http://localhost:3000 | 前端界面 |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |

---

## 详细设置步骤

### 1. 配置环境变量

复制 `.env.example` 为 `backend/.env`：

```bash
# Windows
copy .env.example backend\.env

# Linux/Mac
cp .env.example backend/.env
```

编辑 `backend/.env`，至少配置以下内容：

```env
# 千问 API（必需，或开启 USE_MOCK_LLM）
QWEN_API_KEY=your_actual_api_key_here

# 数据库（默认 SQLite，零配置）
DATABASE_URL=sqlite:///./data/aiscientist.db

# 向量存储
VECTOR_STORE_PATH=./storage/faiss_index
```

### 2. 获取千问 API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 注册 / 登录账号
3. 创建 API Key
4. 将 API Key 填入 `backend/.env` 的 `QWEN_API_KEY`

**没有 Key？** 设置 `USE_MOCK_LLM=true`，所有 LLM 调用返回模拟数据，可完整跑通 Pipeline 和前端交互。

### 3. 使用 Mock 模式（无需 API Key）

```env
USE_MOCK_LLM=true
```

Mock 模式下，8 个智能体会使用模拟数据依次执行，可跑通完整 Pipeline 流程并生成报告，适合快速体验和前端开发调试。

---

## 项目结构说明

```
AISci/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── agents/     # 8 个智能体（独立类 + Prompt + JSON Schema）
│   │   ├── api/        # API 路由
│   │   ├── core/       # 配置和数据库
│   │   ├── models/     # SQLAlchemy 数据模型
│   │   ├── schemas/    # Pydantic 请求/响应 Schema
│   │   ├── services/   # 业务逻辑 + Qwen 客户端 + 向量存储
│   │   ├── skills/     # 科研 Skill 工具层
│   │   └── main.py
│   ├── prompts/         # 8 个 Markdown Prompt 模板
│   └── tests/           # pytest 测试
├── frontend/            # React + Vite 前端
│   └── src/
│       ├── components/  # 32 个 UI 组件
│       ├── pages/       # 8 个页面
│       ├── services/    # 10 个 API 服务模块
│       └── types/       # TypeScript 类型定义
├── scripts/             # 自动化脚本
│   ├── setup_backend.bat/sh    # 后端环境搭建
│   ├── setup_frontend.bat/sh   # 前端环境搭建（pnpm install）
│   ├── run_dev.bat/sh          # 一键启动前后端
│   └── check_e2e.py            # 端到端验收脚本
├── storage/             # 运行时数据（FAISS 索引、报告、上传文件）
└── .env.example         # 环境变量模板
```

---

## 主要功能

### 1. 8 阶段智能科研 Pipeline

```
研究问题 → 文献挖掘 → 知识缺口分析 → 假设生成 → 假设评估 → 实验设计 → 小样验证 → 报告生成
```

一键运行，每阶段记录输入、输出、Prompt、模型参数、Token 用量和耗时。

### 2. 项目工作台

- 创建和管理科研项目
- 上传文献（PDF / DOCX / TXT / MD / CSV）
- 输入研究问题，自动向量化文献并检索
- 实时查看 Pipeline 运行进度和日志

### 3. 报告生成与质量检查

- 自动生成 12 字段完整研究报告
- 比赛规范完整性检查（12 字段合规、引用真实性、模型标注）
- 证据链质量评估
- 支持 Markdown / PDF 导出

### 4. 文献管理

- 上传文献并自动向量化索引
- FAISS 语义检索
- 文献证据绑定与引用溯源

---

## 端到端验收

```bash
# 确保后端已启动（必须在 backend/ 目录下启动）
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端中运行验收
python scripts/check_e2e.py
```

脚本检查项包括：
- 后端健康检查 `/health`
- 千问客户端诊断 `/health/llm`
- 项目列表、文献源、数据集、Pipeline 接口
- 报告接口、Agent 接口可达性
- 核心 Skill 文件完整性
- `.env` 配置文件

---

## 常见问题

### Q: 提示"未找到 Python"
A: 请安装 Python 3.10 / 3.11 / 3.12（暂不建议 3.13），并确保添加到 PATH

### Q: 提示"未找到 Node.js"
A: 请从 https://nodejs.org/ 下载并安装 Node.js 18+

### Q: 千问 API 调用失败
A:
1. 确认 API Key 正确
2. 确认账户有足够额度
3. 检查网络连接
4. 或设置 `USE_MOCK_LLM=true` 使用 Mock 模式

### Q: 报错 "Client.__init__() got an unexpected keyword argument 'proxies'"
A: 这是由于 openai / httpx 版本不兼容导致的。请执行：
```bash
pip uninstall -y openai httpx
pip install "openai>=1.55.3,<3.0" "httpx==0.27.2"
```
然后重启后端。

### Q: 端口被占用
A:
- 后端默认端口：8000（可在 `backend/.env` 中修改）
- 前端默认端口：3000（可在 `vite.config.ts` 中修改）

---

## 手动启动（不使用脚本）

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
pnpm install
pnpm dev
```

---

## 最终报告验收标准

生成的研究报告必须满足以下赛题规范：

| 检查项 | 要求 |
|--------|------|
| 12 字段完整性 | Paper Title / Abstract / Problem Statement / Rationale / Technical Details / Datasets / Source / Target / Methods / Experiments / Results / References 均存在 |
| Technical Details | 必须明确提及 Qwen/千问和阿里云百炼作为核心技术 |
| References | 必须来自真实文献，不得包含 unknown / 未知作者 / placeholder |
| Results | 必须区分 actual_results / simulated_results / expected_results |
| Datasets | 必须有真实数据来源 URL 或明确标记为"拟采集" |
| Charts/Plots | 每张图表必须标记 `is_generated_from_real_data` 和 `source_dataset_id` |
| Non-Qwen Models | 报告中不得出现 GPT-4、Llama、Claude 等非 Qwen 模型名 |

## Reference 真实性要求

- 禁止 LLM 自行编造 References，所有引用必须来自文献库
- 未验证的引用将在报告生成时自动清除
- 导入文献方式：arXiv URL 直接导入 / BibTeX 批量导入 / 本地上传 PDF
- 报告中 References 为 0 时，会明确显示缺少真实引用

## 下一步

- 阅读 [README.md](./README.md) 了解更多详情
- 查看 [API 文档](http://localhost:8000/docs)
- 运行端到端验收：`python scripts/check_e2e.py`
- 开始使用 AI Scientist！