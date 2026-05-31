# AI Scientist Frontend

基于 React 18 + TypeScript + Vite 5 + TailwindCSS 3 构建的智能科研助手前端。

## 技术栈

- React 18 + TypeScript
- Vite 5
- TailwindCSS 3
- React Router 6
- Axios
- lucide-react（图标）
- react-markdown（Markdown 渲染）
- recharts（图表）

## 快速开始

### 安装依赖

```bash
cd frontend
pnpm install
```

### 开发模式

```bash
pnpm dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
pnpm build
```

## 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 首页总览 |
| 项目列表 | `/projects` | 浏览和管理所有科研项目 |
| 创建项目 | `/projects/new` | 新建科研项目 |
| 项目工作台 | `/projects/:id` | 项目主页面，包含 PDF 上传、研究问题输入、Pipeline 运行和结果展示 |
| 文档管理 | `/documents` | 文献上传、向量化与语义检索 |
| 工作流 | `/workflow` | 8 阶段 Pipeline 流程可视化 |
| 报告 | `/reports` | 研究报告浏览与导出（Markdown / PDF） |

## 项目结构

```
frontend/
├── src/
│   ├── components/          # 32 个 UI 组件
│   │   ├── Navbar.tsx       # 全局导航栏
│   │   ├── PageHeader.tsx   # 页面标题栏
│   │   ├── Card.tsx         # 通用卡片
│   │   ├── Button.tsx       # 通用按钮
│   │   ├── EmptyState.tsx   # 空状态提示
│   │   ├── StatCard.tsx     # 统计卡片
│   │   ├── StatusBadge.tsx  # 状态徽章
│   │   ├── ScoreBar.tsx     # 评分进度条
│   │   ├── HypothesisCard.tsx           # 假设卡片
│   │   ├── HypothesesPage.tsx           # 假设列表页
│   │   ├── ExperimentDesignTable.tsx    # 实验设计表格
│   │   ├── ExperimentDesignPage.tsx     # 实验设计页
│   │   ├── ResearchQuestionPage.tsx     # 研究问题页
│   │   ├── LiteratureEvidence.tsx       # 文献证据
│   │   ├── LiteratureLibrary.tsx        # 文献库
│   │   ├── PipelineProgress.tsx         # Pipeline 进度
│   │   ├── RunLogTable.tsx              # 运行日志表
│   │   ├── RunLogDetail.tsx             # 运行日志详情
│   │   ├── RunLogsPage.tsx              # 运行日志页
│   │   ├── QualityCheckCard.tsx         # 质量检查卡片
│   │   ├── ReportChecklist.tsx          # 报告检查清单
│   │   ├── ReportPage.tsx              # 报告预览页
│   │   ├── MarkdownPreview.tsx          # Markdown 预览
│   │   ├── EvidenceChainDrawer.tsx      # 证据链抽屉
│   │   ├── EvidenceChainQualityCard.tsx # 证据链质量卡片
│   │   ├── ExportActions.tsx            # 导出操作按钮
│   │   ├── AgentNode.tsx               # Agent 节点
│   │   ├── AgentDetailPanel.tsx         # Agent 详情面板
│   │   ├── WorkflowActionBar.tsx        # 工作流操作栏
│   │   ├── WorkflowPage.tsx            # 工作流页面
│   │   ├── HumanInLoopCard.tsx          # 人工审核卡片
│   │   ├── ScoresVisualization.tsx      # 评分可视化
│   │   ├── DatasetPage.tsx             # 数据集页面
│   │   └── ...
│   ├── pages/              # 8 个页面组件
│   │   ├── Home.tsx
│   │   ├── Projects.tsx
│   │   ├── CreateProject.tsx
│   │   ├── ProjectWorkspace.tsx
│   │   ├── Documents.tsx
│   │   ├── Workflow.tsx
│   │   ├── Reports.tsx
│   │   └── Settings.tsx
│   ├── services/           # 10 个 API 服务模块
│   │   ├── index.ts             # 统一导出
│   │   ├── projectService.ts    # 项目 API
│   │   ├── documentService.ts   # 文档 API
│   │   ├── pipelineService.ts   # Pipeline API
│   │   ├── hypothesisService.ts # 假设 API
│   │   ├── experimentService.ts # 实验设计 API
│   │   ├── reportService.ts     # 报告 API
│   │   ├── literatureService.ts # 文献 API
│   │   ├── datasetService.ts    # 数据集 API
│   │   └── vectorService.ts     # 向量检索 API
│   ├── types/              # TypeScript 类型定义
│   │   └── index.ts
│   ├── config/             # 环境配置
│   ├── lib/                # 工具函数（api.ts、utils.ts）
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```