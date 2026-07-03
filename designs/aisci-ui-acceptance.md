# AISci UI 设计验收清单

> 设计稿：`designs/aisci-ui.pen` · 规范：`designs/aisci-ui-spec.md`  
> PNG 导出：`designs/exports/`（**23 帧**，2026-06 全量导出）  
> 画布标准：**1440 × 960 px**  
> **最后同步**：2026-06 · Phase C 验收修复轮次

**图例**：`✅` 通过 · `🟡` 部分差异 · `❌` 待修 · `—` 未测 / 不适用

---

## 1. 验收流程

1. 打开 `designs/exports/<节点ID>.png` 与现网逐屏对照。
2. 启动现网：`cd frontend && pnpm dev`。
3. 按下方表格「现网 URL」访问，核对布局、令牌、三态、文案。
4. 差异详情见 **§8**；剩余项见 **§9**。

---

## 2. 全局路由页

| 验收 | Frame | 节点 ID | 现网 URL | 主组件 | PNG | 差异摘要 |
|------|-------|---------|----------|--------|-----|----------|
| 🟡 | `00-Design System` | `Ktnbv` | — | `tailwind.blueprint.js` / `index.css` | ✅ | 令牌已落地；无独立 `/design-system` 预览路由 |
| ✅ | `01-Home 首页` | `qS1FU` | `/` | `Home.tsx` | ✅ | 指标 + RecentPipeline + 项目网格 + Footer；三态 + `[AISci]` 品牌 |
| ✅ | `14-文献中心` | `Dat8t` | `/documents` | `Documents.tsx` | ✅ | PageHeader + 项目范围 + 跨项目汇总 / 单项目 LiteratureLibrary |
| ✅ | `15-报告中心` | `adKkL` | `/reports` | `Reports.tsx` | ✅ | PageHeader + 列表 + 三态 |
| ✅ | `16-设置` | `YVENb` | `/settings` | `Settings.tsx` | ✅ | LLM 配置 + 环境变量说明 |
| 🟡 | `17-创建项目` | `YBU0r` | `/projects/new` | `CreateProject.tsx` | ✅ | 模式双选 + 表单；`max-w-3xl` 略窄于 Frame 全宽 |
| ✅ | `18-UI States` | `D2Ym9` | — | `LoadingState` / `ErrorState` / `EmptyState` | ✅ | 已推广至主要 Tab + 首页 |

---

## 3. 项目工作台（12 Tab）

路由：`/projects/:id?tab=<tabId>`

| 验收 | Tab | Tab ID | Frame | 节点 ID | 主组件 | PNG | 差异摘要 |
|------|-----|--------|-------|---------|--------|-----|----------|
| 🟡 | 1 | `overview` | `02-Project Overview` | `DMGHL` | `ProjectWorkspace` | ✅ | 6 指标 + 8 阶段 + CTA「查看科研闭环总览 →」✅；外壳仍为全局 Navbar + 返回链 |
| ✅ | 2 | `closed_loop` | `03-Closed Loop` | `z5gmo` | `ResearchClosedLoopOverview` | ✅ | 质量验收 / Teaching / Discovery 独立 Collapsible；时间线 defaultOpen |
| ✅ | 3 | `questions` | `05-研究问题` | `uBzbD` | `ResearchQuestionPage` | ✅ | 双栏 + DataSpec + 三态 |
| ✅ | 4 | `literature` | `06-文献库` | `o2Fc4r` | `LiteratureLibrary` | ✅ | 三 Tab + StatCards + ChunkViewer；import_status 与操作区 bp 色 |
| 🟡 | 5 | `knowledge_graph` | `07-知识图谱` | `Kjsvn` | `KnowledgeGraphPage` | ✅ | 功能齐全；节点 Neo4j 科研色板（ intentional ） |
| ✅ | 6 | `datasets` | `08-数据集` | `JH3Wy` | `DatasetPage` | ✅ | Tab 顺序已对齐 spec §4.3 |
| ✅ | 7 | `workflow` | `04-Workflow` | `mL1IE` | `WorkflowPage` | ✅ | 辅助面板收进右侧 Detail Collapsible |
| ✅ | 8 | `prompts` | `09-Prompt管理` | `tNuCp` | `PromptManagementPage` | ✅ | 左列表 + 右编辑器 + PresetBar |
| ✅ | 9 | `hypotheses` | `10-候选假设` | `Cf9pk` | `HypothesesPage` | ✅ | xl 三栏；窄屏右栏评分说明折叠 |
| ✅ | 10 | `experiments` | `11-实验设计` | `sCy53` | `ExperimentDesignPage` | ✅ | 侧栏 FL 计划 + Primary Hypothesis Actions + bp 色 |
| ✅ | 11 | `reports` | `12-研究报告` | `N7Jsj` | `ReportPage` | ✅ | 左 TOC + Markdown 预览 + 右 Checklist/HITL |
| ✅ | 12 | `logs` | `13-运行日志` | `AFcII` | `RunLogsPage` | ✅ | 三栏 + 三态；含 `data_acquisition` 中文映射 |

---

## 4. 数据集页内 Tab（5）

| 验收 | Frame | 节点 ID | subtab | 主组件 | PNG | 差异摘要 |
|------|-------|---------|--------|--------|-----|----------|
| ✅ | `08-数据集` | `JH3Wy` | `datasets` | `DatasetPage` | ✅ | 见 §3 Tab 6 |
| ✅ | `08b-反馈中心` | `cV3ID` | `feedback` | `FeedbackHubPanel` | ✅ | `bp-purple` 外壳 |
| ✅ | `08c-数据目录` | `jUtjv` | `catalog` | `DataCatalogPanel` | ✅ | 三态完整 |
| ✅ | `08d-多模态` | `t6ReB` | `multimodal` | `MultimodalEvidencePanel` | ✅ | bp 解析状态色 |
| ✅ | `08e-DataFinder` | `ianyJ` | `data-finder` | `DataFinderPanel` 等 | ✅ | bp 语义色扫尾 |

---

## 5. UI 三态覆盖

| 状态 | 组件 | 已接入 |
|------|------|--------|
| Loading | `LoadingState` | 首页、假设、日志、报告、数据集、文献、闭环、实验、报告中心、工作台、Prompt、研究问题、数据目录 |
| Error | `ErrorState` | 同上 |
| Empty | `EmptyState` | 假设、日志、报告、数据集、首页空项目、报告中心、数据目录、多模态 |

---

## 6. 令牌速查（全站）

| 区域 | 设计 | 现网 | 验收 |
|------|------|------|------|
| 背景 | `#0A1628` | `bg-bp-base` | ✅ |
| 卡片 | `#1E293B` | `.card` / `bg-bp-surface` | ✅ |
| 主强调 | `#38BDF8` | `text-bp-cyan` | ✅ |
| 字体 | JetBrains Mono | `font-bp` | ✅ |
| 圆角 | 2px | `rounded-bp` | 🟡 部分 `rounded-lg` 残留（低优先级） |
| 工作台外壳 | Navbar→MetaBar→Tabs→Body | 全局 Navbar + `ProjectWorkspaceHeader` | 🟡 结构略异 |
| 品牌 | `[AISci]` | Navbar / Footer / README / package.json | ✅ |

---

## 7. PNG 导出索引（23 帧）

| PNG | Frame |
|-----|-------|
| `Ktnbv.png` | Design System |
| `qS1FU.png` | Home |
| `Dat8t.png` | 文献中心 |
| `adKkL.png` | 报告中心 |
| `YVENb.png` | 设置 |
| `YBU0r.png` | 创建项目 |
| `D2Ym9.png` | UI States |
| `DMGHL.png` | 项目概览 |
| `z5gmo.png` | 科研闭环 |
| `uBzbD.png` | 研究问题 |
| `o2Fc4r.png` | 文献库 |
| `Kjsvn.png` | 知识图谱 |
| `JH3Wy.png` | 数据集 |
| `mL1IE.png` | 工作流 |
| `tNuCp.png` | Prompt 管理 |
| `Cf9pk.png` | 候选假设 |
| `sCy53.png` | 实验设计 |
| `N7Jsj.png` | 研究报告 |
| `AFcII.png` | 运行日志 |
| `cV3ID.png` | 数据集·反馈 |
| `jUtjv.png` | 数据集·目录 |
| `t6ReB.png` | 数据集·多模态 |
| `ianyJ.png` | 数据集·DataFinder |

---

## 8. 逐项差异标注（剩余）

### 8.1 全局

**Ktnbv** — 🟡 无 `/design-system` 预览页（令牌已在 CSS/Tailwind）

**YBU0r** — 🟡 表单区 `max-w-3xl`，Frame 为全宽

### 8.2 工作台

**DMGHL** — 🟡 全局 Navbar + 返回链，非设计稿内嵌工作台 Navbar

**Kjsvn** — 🟡 节点色 Neo4j 色板（有意保留）

**Cf9pk** — 🟡 窄屏三栏 → 两栏 + 折叠评分说明（响应式兜底）

### 8.3 跨项目文献

**Dat8t** — ✅ 客户端汇总各项目文档数 + 跳转；🟡 无后端单 API 合并浏览全部文献条目

### 8.4 B-3 扫尾

主 Tab 与闭环/假设/工作流相关 **22+ 组件** 已统一 `bp-*` / `danger-*`；可复用 `frontend/scripts/bp-color-sweep.mjs`。

仍有意保留：**知识图谱画布节点** Neo4j 科研色板（非 Tailwind utility）。

---

## 9. 修复记录与待办

### 已完成（P1–P3 + 文档同步轮）

| 项 | 文件 |
|----|------|
| 报告预览 | `ReportPage.tsx` / `ReportPdfPreview.tsx` |
| 数据集 Tab 顺序 | `DatasetPage.tsx` |
| Feedback / DataFinder / 文献 bp 色 | `FeedbackHubPanel` / `DataFinderPanel` / `LiteratureLibrary` |
| 首页三态 + 品牌 | `Home.tsx` / `Navbar.tsx` |
| 概览 CTA | `ProjectWorkspace.tsx` |
| 运行日志 stage | `RunLogsPage.tsx` |
| 工作流面板收拢 | `WorkflowPage.tsx` |
| 实验设计侧栏 | `ExperimentDesignPage.tsx` |
| 跨项目文献 | `Documents.tsx` / `CrossProjectLiteratureSummary.tsx` |
| 闭环 Teaching/Quality 拆分 | `DiscoveryLoopPanel.tsx` / `ResearchClosedLoopOverview.tsx` |
| AISci 品牌 | `Navbar` / `README.md` / `package.json` / 各页面文案 |
| B-3 组件色扫尾 | `frontend/scripts/bp-color-sweep.mjs` + 22 个组件 |

### 可选后续（P4）

| 项 | 说明 |
|----|------|
| `/design-system` 预览路由 | 展示 `Ktnbv` 组件库 |
| 工作台 Navbar 结构 | 隐藏全局 Navbar 或双模式外壳 |
| `rounded-lg` 全站 → `rounded-bp` | 视觉统一 |
| 跨项目文献后端聚合 API | 单页合并列表 |

---

*与 `aisci-ui-spec.md` §10 同步维护*
