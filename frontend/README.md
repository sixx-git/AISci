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

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
pnpm build        # 生产构建
```

## 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 项目搜索、筛选与列表；入口创建项目 |
| 创建项目 | `/projects/new`（或首页引导） | 通用 / 联邦学习模式、FL 档位与领域 |
| 项目工作台 | `/projects/:id` | 多 Tab 科研全流程 |
| 预测 | `/predict` | 评分表 / 影响力预测（BFF → pingfenbiao） |
| 文献 | `/documents` | 文献上传、arXiv 检索与导入 |
| 报告 | `/reports` | 研究报告浏览与导出 |
| Skills | `/skills` | Skill 启用与目录 |

**项目工作台主 Tab**（`src/config/projectTabs.ts`）：项目概览 · 研究问题 · 文献库 · 智能体工作流 · 候选假设 · **迭代实验** · 研究报告  

高级深链：Prompt 管理 · 运行日志。旧「数据集」Tab 已重定向到「迭代实验」（数据绑定在迭代实验内完成）。

## 核心组件（按功能）

### Pipeline 与闭环

| 组件 | 说明 |
|------|------|
| `WorkflowPage.tsx` | Pipeline 运行、阶段进度、闭环面板 |
| `PipelineProgress.tsx` | 阶段进度条 |
| `ClosedLoopTimeline.tsx` | CQS 趋势、闭环事件/决策、审计链导出 |
| `HitlGateModal.tsx` / `HitlGateContinueBar.tsx` | HITL Gate 弹窗与继续条 |
| `DiscoveryLoopPanel.tsx` | 历史 Discovery run 只读展示（自动环已退役） |
| `StageHumanLoopPanel.tsx` | 阶段级人工审核（工作流主 HITL 入口） |

### 假设与证据

| 组件 | 说明 |
|------|------|
| `HypothesesPage.tsx` | 假设列表、主假设选择 |
| `HypothesisCard.tsx` | 假设卡片（详情 / 溯源时间线 Tab） |
| `HypothesisProvenanceTimeline.tsx` | fact → 多模态 → 数据集 → spec 溯源 |
| `HypothesisTreePanel.tsx` | 假设树剪枝与分支评分 |
| `EvidenceChainDrawer.tsx` | 证据链抽屉 |
| `EvidenceDiffPanel.tsx` | 迭代前后证据 Diff |
| `VerifiableChecksPanel.tsx` | 可验证 spec 检查项 |
| `EnsembleReviewPanel.tsx` | 集成评审结果 |

### 迭代实验与联邦

| 组件 / 页面 | 说明 |
|------|------|
| `iterative-experiment/*` | 迭代实验列表与详情（shaxiang 桥接） |
| `ExperimentDetail.tsx` | 数据绑定、脚本设计、运行；**FL 模板 → 后台 job → LLM 设计脚本**（非一键粘贴）；独立联邦仿真控制台 |
| `CreateProject.tsx` | 联邦模式：HFL/VFL、标准 Non-IID 档位、领域勾选 |
| `ProjectWorkspace.tsx` | 概览展示已挂载 FL Pack 版本与实验档位 |
| `StageHumanLoopPanel.tsx` | 智能体工作流：阶段输出编辑 / 对话修订 / 从此阶段重跑 |

人工反馈两路：
- **迭代实验 Tab**：`submitFeedback`（存反馈）/ `redesignFromFeedback`（立即重设计，后台 job）/ `applyFlScript`（模板作反馈）
- **智能体工作流 Tab**：`human-loop` 阶段保存、对话、HITL Gate 继续、`rerun-from-stage`

专题文档：[FL_STARTER_PACK.md](../docs/FL_STARTER_PACK.md)、[FL_EXPERIMENT_PARADIGMS.md](../docs/FL_EXPERIMENT_PARADIGMS.md)。

### 文献、报告与其他

| 组件 | 说明 |
|------|------|
| `LiteratureLibrary.tsx` | 文献库、PDF 解析索引 |
| `ReportPage.tsx` | 报告预览与导出 |
| `QualityCheckCard.tsx` | 报告质量检查 |

> 已下线/移除的前端面：独立数据集页、Data Finder 面板、Knowledge Graph 页、FederatedCampaignPanel 等；相关能力若仍存在，多在后端服务层或 Pipeline 内部使用。

## API 服务模块

| 模块 | 主要接口 |
|------|----------|
| `pipelineService.ts` | Pipeline 运行、状态、审计链导出 |
| `hypothesisService.ts` | 假设列表、证据链、溯源时间线 |
| `iterativeExperimentService.ts` | 迭代实验 CRUD / 长任务 job 轮询（`designScript` / `redesignFromFeedback` / `applyFlScript` / `runToCompletion`） / `listFlScriptTemplates` |
| `humanLoopService.ts` | 工作流阶段人工反馈、对话、HITL Gate、从此阶段重跑 |
| `literatureService.ts` | 文献检索与导入 |
| `projectService.ts` | 项目管理（含 `fl_setting` / `fl_domains` / `fl_experiment_profile`；模式切换会同步 Pack） |
| `reportService.ts` | 报告下载 |
| `predictService.ts` | 预测页 BFF |

## 项目结构

```
frontend/
├── src/
│   ├── components/     # UI 组件（工作流、假设、迭代实验、predict/ 等）
│   ├── pages/          # Home、CreateProject、ProjectWorkspace、Predict、Documents、Reports…
│   ├── services/       # API 封装
│   ├── types/          # TypeScript 类型
│   ├── lib/            # api.ts、utils.ts、hitlGateModalStorage 等
│   └── config/         # projectTabs、pipelineStageNavigation、promptStages 等
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## 更多信息

- [项目根目录 README](../README.md)
- [后端 README](../backend/README.md)
