# AISci - 快速入门指南

## 5 分钟快速开始

### 前置要求

- **Python 3.10 / 3.11 / 3.12**（推荐）
- **暂不建议 Python 3.13**：部分依赖可能存在兼容问题
- **Node.js 18+**
- **pnpm**（推荐 9.x）
- （可选）**XeLaTeX**：用于研究报告 PDF 编译，见 [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md)

---

## 快速设置（推荐）

### Windows 用户

```batch
# 1. 设置后端（项目根目录创建 venv，安装 backend\requirements.txt）
scripts\setup_backend.bat

# 2. 设置前端（新开一个终端）
scripts\setup_frontend.bat

# 3. 配置环境变量
copy .env.example backend\.env
# 编辑 backend\.env，填入 QWEN_API_KEY
# 如暂时无 Key，设置 USE_MOCK_LLM=true

# 4. 启动开发环境（后端 :8000 + 前端 :5173）
scripts\run_dev.bat
```

完整栈（含预测服务）可用：

```batch
scripts\launch_stack.bat full
```

### Linux / Mac 用户

```bash
# 1. 设置后端
bash scripts/setup_backend.sh

# 2. 设置前端（新开一个终端）
bash scripts/setup_frontend.sh

# 3. 配置环境变量
cp .env.example backend/.env
# 编辑 backend/.env，填入 QWEN_API_KEY
# 如暂时无 Key，设置 USE_MOCK_LLM=true

# 4. 启动开发环境
bash scripts/run_dev.sh
```

### 预测 Tab（评分表 / 影响力预测）

顶栏「预测」依赖独立服务 **pingfenbiao**（默认 `127.0.0.1:8765`）。前端经 AISci 后端 BFF：`/api/v1/pingfenbiao/*` → `:8765`。

需同时启动：**后端 :8000** + **pingfenbiao :8765** + **前端 :5173**。

```batch
# Windows：新开终端
scripts\run_pingfenbiao.bat
```

或：

```bash
cd pingfenbiao-main/pingfenbiao-main/web
pip install -r requirements.txt
# 另需安装各 rubric-auto-gen*/requirements.txt（首次）
uvicorn app:app --host 127.0.0.1 --port 8765
```

配置 `DASHSCOPE_API_KEY`（可与 `QWEN_API_KEY` 相同；写在 pingfenbiao 的 `.env` 或环境变量中）。

---

## 启动后访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端界面 |
| http://localhost:5173/predict | 预测（评分表 / 影响力，需 pingfenbiao :8765） |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc API 文档 |
| http://localhost:8000/health | 后端健康检查 |

---

## 详细设置步骤

### 1. 配置环境变量

后端优先读取 **`backend/.env`**（也兼容项目根目录 `.env`）：

```bash
# Windows
copy .env.example backend\.env

# Linux/Mac
cp .env.example backend/.env
```

至少配置：

```env
# 千问 API（必需，或开启 USE_MOCK_LLM）
QWEN_API_KEY=your_actual_api_key_here
QWEN_MODEL=qwen3.6-plus

# 数据库（默认 SQLite，零配置）
DATABASE_URL=sqlite:///./data/aiscientist.db

# 向量存储（默认 zvec）
VECTOR_BACKEND=zvec
VECTOR_INDEXES_PATH=./storage/vector_indexes

# 迭代实验引擎（默认启用 shaxiang）
AISCI_USE_SHAXIANG=true

# CORS：开发前端为 Vite :5173
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
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

Mock 模式下，各阶段智能体会使用模拟数据依次执行，可跑通完整 7 阶段 Pipeline 并生成报告，适合快速体验和前端开发调试。

---

## 项目结构说明

```
AISci/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── agents/       # 阶段智能体 + CoordinatorAgent
│   │   ├── api/          # 路由（含 iterative_experiments、pingfenbiao_proxy）
│   │   ├── core/         # 配置、闭环控制、质量评分、溯源
│   │   ├── services/     # Pipeline、迭代实验、报告净化、Qwen 客户端等
│   │   ├── integrations/ # shaxiang bridge 等
│   │   ├── skills/       # 科研 Skill 工具层（40+）
│   │   └── main.py
│   ├── prompts/          # Markdown Prompt + presets/
│   ├── requirements.txt  # 后端依赖权威清单
│   └── tests/            # pytest（含 test_batch* 回归）
├── frontend/             # React + Vite（:5173）
│   └── src/
│       ├── components/   # 工作流、迭代实验、predict/ 等
│       ├── pages/        # Home、Predict、Documents、Reports、ProjectWorkspace…
│       ├── services/     # API 服务模块
│       └── types/        # TypeScript 类型
├── pingfenbiao-main/     # 预测独立服务 :8765
├── shaxiang-main/        # 迭代实验沙箱引擎
├── scripts/              # setup / run_dev / launch_stack / check_e2e
├── storage/              # 审计链、证据链、报告产物等
└── .env.example          # 环境变量模板
```

---

## 主要功能

### 1. 7 阶段智能科研 Pipeline

```
研究问题 → 文献挖掘 → 知识缺口 → 假设生成 → 假设评审 → 迭代实验 → 报告生成
```

一键运行，每阶段记录输入、输出、Prompt、模型参数、Token 用量和耗时。数据绑定与脚本迭代在「迭代实验」阶段（shaxiang）完成。

### 2. 项目工作台

- 创建和管理科研项目（通用 / 联邦学习资源包）
- 上传文献（PDF / DOCX / TXT / MD / CSV）
- 输入研究问题，自动向量化文献并检索（默认 zvec）
- 实时查看 Pipeline 运行进度和日志
- 主 Tab：概览 · 研究问题 · 文献 · 工作流 · 假设 · **迭代实验** · 报告  
- 高级深链：Prompt 管理 · 运行日志

### 3. 报告生成与质量检查

- 自动生成 12 字段完整研究报告
- 正文净化与证据对齐（摘要不得与 smoke/阶段性/否定证据冲突）
- 引用真实性校验（禁止编造 / 错配 arXiv）
- 指标键默认保留英文（如 `fixed accuracy`）
- 支持 Markdown / LaTeX PDF 导出

### 4. 文献管理

- 上传文献并自动向量化索引
- 语义检索（zvec；兼容检测旧 FAISS 索引）
- 文献证据绑定与引用溯源（`fact_id` + `source_chunk_id`）

### 5. 预测 Tab

- 评分表生成 / 报告打分 / 科学影响力预测（pingfenbiao，经 `/api/v1/pingfenbiao` BFF）

### 6. 科研闭环

- **CQS 质量趋势** — 综合质量分与闭环事件/决策
- **HITL Gate** — 关键节点人工审核暂停与恢复
- **Feedback Hub** — 全局约束；实验类反馈可重跑 `iterative_experiment`
- **假设溯源** — 假设卡片「溯源时间线」
- **审计链导出** — 工作流页或 `GET /api/v1/pipeline/audit-export/{run_id}`
- **大家长 Agent** — 跨阶段 Hint、报告内容自动修复

---

## 端到端验收

```bash
# 确保后端已启动（在 backend/ 目录）
cd backend
# 推荐使用项目根目录 venv
# Windows: ..\venv\Scripts\activate
# Linux/Mac: source ../venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 新终端（项目根目录）运行验收
python scripts/check_e2e.py
```

脚本检查项包括：
- 后端健康检查 `/health`
- 千问客户端诊断 `/health/llm`
- 项目列表、文献源、Pipeline 接口
- 报告接口、Agent 接口可达性
- 核心 Skill 文件完整性
- `.env` / `backend/.env` 配置

### 批次回归测试（可选）

```bash
cd backend
python -m pytest tests/test_batch*.py -v
```

覆盖 CQS、verifiable spec、Data Finder、闭环决策、Feedback Hub、溯源审计等能力。详见 [backend/tests/README.md](./backend/tests/README.md)。

---

## 常见问题

### Q: 提示「未找到 Python」
A: 请安装 Python 3.10 / 3.11 / 3.12（暂不建议 3.13），并确保添加到 PATH。

### Q: 提示「未找到 Node.js」
A: 请从 https://nodejs.org/ 下载并安装 Node.js 18+，并安装 pnpm（`corepack enable` 或 `npm i -g pnpm`）。

### Q: 千问 API 调用失败
A:
1. 确认 `backend/.env` 中 API Key 正确  
2. 确认账户有足够额度  
3. 检查网络（可尝试 `QWEN_FORCE_IPV4=true`）  
4. 或设置 `USE_MOCK_LLM=true`

### Q: 报错 `Client.__init__() got an unexpected keyword argument 'proxies'`
A: openai / httpx 版本不兼容。请在已激活的 venv 中执行：
```bash
pip uninstall -y openai httpx
pip install "openai>=1.55.3,<3.0" "httpx==0.27.2"
```
然后重启后端。

### Q: 前端能开但接口跨域失败
A: 确认 `CORS_ORIGINS` 包含 `http://localhost:5173`（当前 Vite 端口），且请求打到 `:8000`。

### Q: 迭代实验提示 shaxiang 相关错误
A: 确认 `AISCI_USE_SHAXIANG=true`，且 `shaxiang-main/` 目录完整；引擎数据库位于 `shaxiang-main/shaxiang-main/data/experiments.db`。

### Q: 端口被占用
A:
- 后端默认：`8000`（`BACKEND_PORT`）
- 前端默认：`5173`（`frontend/vite.config.ts`）
- pingfenbiao 默认：`8765`

### Q: 报告 PDF 编译失败
A: 安装 TeX Live / MiKTeX 并确保 `xelatex` 在 PATH 中，参见 [LATEX_EXPORT_SETUP.md](./LATEX_EXPORT_SETUP.md)。无 LaTeX 时仍可查看结构化报告与 Markdown。

---

## 手动启动（不使用脚本）

### 后端

```bash
# 在项目根目录
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
# → http://localhost:5173
```

---

## 最终报告验收标准

生成的研究报告必须满足以下规范：

| 检查项 | 要求 |
|--------|------|
| 12 字段完整性 | Paper Title / Abstract / Problem Statement / Rationale / Technical Details / Datasets / Source / Target / Methods / Experiments / Results / References 均存在 |
| Technical Details | 必须明确提及 Qwen/千问和阿里云百炼 |
| References | 必须来自真实文献，不得包含 unknown / placeholder / 错配 arXiv |
| Results | 必须区分 actual_results / simulated_results / expected_results |
| Datasets | 必须有真实数据来源 URL 或明确标记为「拟采集」 |
| Charts/Plots | 每张图表应标记真实数据来源相关字段 |
| Non-Qwen Models | 报告中不得出现 GPT-4、Llama、Claude 等非 Qwen 模型名 |
| 证据对齐 | 摘要结论须与 smoke/阶段性/否定性实测同向，不得过度正面包装 |

## Reference 真实性要求

- 禁止 LLM 自行编造 References，所有引用必须来自文献库 / 已核验 citation_map
- 未验证或题名-ID 错配的引用会在生成/净化时清除或改写
- 导入文献方式：arXiv URL / BibTeX / 本地上传 PDF
- References 为 0 时，会明确提示缺少真实引用

## 下一步

- 阅读 [README.md](./README.md) 了解架构与创新机制
- 查看 [backend/README.md](./backend/README.md)、[frontend/README.md](./frontend/README.md)
- 查看 [API 文档](http://localhost:8000/docs)
- 运行端到端验收：`python scripts/check_e2e.py`
- 运行批次回归：`cd backend && python -m pytest tests/test_batch*.py -v`
- 阅读 [DATABASE.md](./backend/DATABASE.md)、[backend/prompts/README.md](./backend/prompts/README.md)
- 联邦学习： [docs/FL_STARTER_PACK.md](./docs/FL_STARTER_PACK.md)
