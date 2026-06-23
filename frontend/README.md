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
| 首页 | `/` | 项目搜索、筛选与列表 |
| 项目工作台 | `/projects/:id` | 多 Tab：科研闭环总览、工作流、假设、文献、数据集、实验、报告等 |
| 文献 | `/documents` | 文献上传、arXiv 检索、向量化与语义检索 |
| 报告 | `/reports` | 研究报告浏览与导出 |

项目工作台 Tab 包括：**项目概览**、**科研闭环总览**、**研究问题**、**文献库**、**知识图谱**、**数据集**、**智能体工作流**、**Prompt 管理**、**候选假设**、**实验设计**、**研究报告**、**运行日志** 等。

## 核心组件（按功能）

### Pipeline 与闭环

| 组件 | 说明 |
|------|------|
| `WorkflowPage.tsx` | Pipeline 运行、阶段进度、闭环面板 |
| `PipelineProgress.tsx` | 阶段进度条 |
| `ClosedLoopTimeline.tsx` | CQS 趋势、闭环事件/决策、**审计链导出** |
| `HitlGatePanel.tsx` | HITL Gate 暂停与恢复 |
| `ExecutionTierBadge.tsx` | execution_tier / data_authenticity 标注 |
| `DiscoveryLoopPanel.tsx` | Discovery 迭代与因果链 |
| `StageHumanLoopPanel.tsx` | 阶段级人工审核 |

### 假设与证据

| 组件 | 说明 |
|------|------|
| `HypothesesPage.tsx` | 假设列表、主假设选择 |
| `HypothesisCard.tsx` | 假设卡片（详情 / **溯源时间线** Tab） |
| `HypothesisProvenanceTimeline.tsx` | fact → 多模态 → 数据集 → spec 溯源 |
| `HypothesisTreePanel.tsx` | 假设树剪枝与分支评分 |
| `EvidenceChainDrawer.tsx` | 证据链抽屉 |
| `EvidenceDiffPanel.tsx` | 迭代前后证据 Diff |
| `VerifiableChecksPanel.tsx` | 可验证 spec 检查项 |
| `EnsembleReviewPanel.tsx` | 集成评审结果 |

### 数据与 Data Finder

| 组件 | 说明 |
|------|------|
| `DatasetPage.tsx` | 数据集管理（上传 / Catalog / Feedback Hub Tab） |
| `DataFinderPanel.tsx` | 多源数据查找、表格抽取、Merge、Bundle 下载 |
| `DataCatalogPanel.tsx` | 项目 Data Catalog |
| `FeedbackHubPanel.tsx` | Feedback Hub 全局约束 |
| `FigureReviewPanel.tsx` | 图表 VLM 抽取复核 |

### 文献、报告与其他

| 组件 | 说明 |
|------|------|
| `LiteratureLibrary.tsx` | 文献库、PDF 解析索引 |
| `ReportPage.tsx` | 报告预览与导出 |
| `QualityCheckCard.tsx` | 报告 12 字段质量检查 |
| `KnowledgeGraphPage.tsx` | 知识图谱查询与推理 |
| `MultimodalEvidencePanel.tsx` | 多模态证据 |
| `FederatedCampaignPanel.tsx` | 联邦 Campaign Pilot |

## API 服务模块

| 模块 | 主要接口 |
|------|----------|
| `pipelineService.ts` | Pipeline 运行、状态、**审计链导出** |
| `hypothesisService.ts` | 假设列表、证据链、**溯源时间线** |
| `dataFinderService.ts` | Data Finder 搜索/抽取/Merge/Bundle |
| `datasetService.ts` | 数据集、**Data Catalog** |
| `literatureService.ts` | 文献检索与导入 |
| `projectService.ts` | 项目管理 |
| `reportService.ts` | 报告下载 |

## 项目结构

```
frontend/
├── src/
│   ├── components/     # UI 组件（60+）
│   ├── pages/          # 页面组件
│   ├── services/       # API 封装
│   ├── types/          # TypeScript 类型
│   ├── lib/            # api.ts、utils.ts
│   └── config/
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## 更多信息

- [项目根目录 README](../README.md)
- [后端 README](../backend/README.md)
