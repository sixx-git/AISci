# AISci UI 设计验收清单

> 设计稿：`designs/aisci-ui.pen` · 规范：`designs/aisci-ui-spec.md`  
> 导出目录：`designs/exports/`（Pencil `export_nodes` 或手动导出 PNG）  
> 画布标准：**1440 × 960 px**

---

## 1. 验收流程

1. 在 Pencil 中打开 `aisci-ui.pen`，按下方表格导出对应 Frame PNG 至 `designs/exports/`。
2. 启动现网：`cd frontend && pnpm dev`，按「现网 URL」逐屏对照。
3. 检查项：布局结构、Blueprint 令牌（背景/描边/字体）、语义色、Loading/Error/Empty 三态、页内 Tab 文案。
4. 在「验收」列打勾：`✅` 通过 · `🟡` 部分 · `❌` 待修 · `—` 未测。

### Pencil MCP 导出示例

```text
export_nodes
  filePath: designs/aisci-ui.pen
  outputDir: designs/exports
  format: png
  nodeIds: [qS1FU, YVENb, ...]
```

若 MCP 报路径错误，可在 Pencil 内手动导出，或使用已成功路径 `designs/exports`（相对仓库根）。

---

## 2. 全局路由页

| 验收 | Frame | 节点 ID | 现网 URL | 主组件 | PNG 文件名 |
|------|-------|---------|----------|--------|------------|
| ☐ | `00-Design System` | `Ktnbv` | — | `tailwind.blueprint.js` / `index.css` | `Ktnbv.png` |
| ☐ | `01-Home 首页` | `qS1FU` | `/` | `pages/Home.tsx` | `qS1FU.png` |
| ☐ | `14-文献中心` | `Dat8t` | `/documents` | `pages/Documents.tsx` | `Dat8t.png` |
| ☐ | `15-报告中心` | `adKkL` | `/reports` | `pages/Reports.tsx` | `adKkL.png` |
| ☐ | `16-设置` | `YVENb` | `/settings` | `pages/Settings.tsx` | `YVENb.png` |
| ☐ | `17-创建项目` | `YBU0r` | `/projects/new` | `pages/CreateProject.tsx` | `YBU0r.png` |
| ☐ | `18-UI States` | `D2Ym9` | — | `LoadingState` / `ErrorState` / `EmptyState` | `D2Ym9.png` |

---

## 3. 项目工作台（12 Tab）

路由模板：`/projects/:id?tab=<tabId>`

| 验收 | Tab # | Tab ID | Frame | 节点 ID | 主组件 |
|------|-------|--------|-------|---------|--------|
| ☐ | 1 | `overview` | `02-Project Overview` | `DMGHL` | `ProjectWorkspace` 概览 |
| ☐ | 2 | `closed_loop` | `03-Closed Loop` | `z5gmo` | `ResearchClosedLoopOverview` |
| ☐ | 3 | `questions` | `05-研究问题` | `uBzbD` | `ResearchQuestionPage` |
| ☐ | 4 | `literature` | `06-文献库` | `o2Fc4r` | `LiteratureLibrary` |
| ☐ | 5 | `knowledge_graph` | `07-知识图谱` | `Kjsvn` | `KnowledgeGraphPage` |
| ☐ | 6 | `datasets` | `08-数据集` | `JH3Wy` | `DatasetPage` |
| ☐ | 7 | `workflow` | `04-Workflow` | `mL1IE` | `WorkflowPage` |
| ☐ | 8 | `prompts` | `09-Prompt管理` | `tNuCp` | `PromptManagementPage` |
| ☐ | 9 | `hypotheses` | `10-候选假设` | `Cf9pk` | `HypothesesPage` |
| ☐ | 10 | `experiments` | `11-实验设计` | `sCy53` | `ExperimentDesignPage` |
| ☐ | 11 | `reports` | `12-研究报告` | `N7Jsj` | `ReportPage` |
| ☐ | 12 | `logs` | `13-运行日志` | `AFcII` | `RunLogsPage` |

---

## 4. 数据集页内 Tab（5）

路由：`/projects/:id?tab=datasets&subtab=<subtab>`

| 验收 | Frame | 节点 ID | `subtab` / 页内 Tab | 主组件 |
|------|-------|---------|---------------------|--------|
| ☐ | `08-数据集` | `JH3Wy` | `datasets` / 项目数据集 | `DatasetPage` 主面板 |
| ☐ | `08b-反馈中心` | `cV3ID` | `feedback` | `FeedbackHubPanel` |
| ☐ | `08c-数据目录` | `jUtjv` | `catalog` | `DataCatalogPanel` |
| ☐ | `08d-多模态` | `t6ReB` | `multimodal` | `MultimodalEvidencePanel` |
| ☐ | `08e-DataFinder` | `ianyJ` | `data-finder` | `DataFinderPanel` |

---

## 5. UI 三态（现网组件）

| 状态 | 组件路径 | 已接入页面（2026-06） |
|------|----------|----------------------|
| Loading | `workspace/LoadingState.tsx` | 假设、运行日志、报告、数据集、文献、闭环、实验、报告中心、工作台、Prompt、研究问题、数据目录 |
| Error | `workspace/ErrorState.tsx` | 同上 + 多模态（行内） |
| Empty | `EmptyState.tsx` | 假设、运行日志、报告、数据集、首页、报告中心、数据目录、多模态 |

参考设计 Frame：`18-UI States`（`D2Ym9`）

---

## 6. 关键对照点（逐屏速查）

| 区域 | 设计约定 | 现网检查 |
|------|----------|----------|
| 背景 | `#0A1628` · `bg-bp-base` | 全站 `App.tsx` 外壳 |
| 卡片 | `#1E293B` · `bg-bp-surface` / `.card` | Card 组件 |
| 主强调 | `#38BDF8` · `text-bp-cyan` | Tab 激活、链接、主按钮 |
| 成功 | `#22C55E` · `text-bp-green` | Pipeline 完成、Run 成功 |
| 警告 | `#FACC15` · `text-bp-yellow` | HITL、低证据 |
| 失败 | `text-danger-400` | 错误、偏题 |
| 字体 | JetBrains Mono · `font-bp` | `index.css` body |
| 圆角 | 2px · `rounded-bp` | 按钮、输入框、面板 |
| 工作台外壳 | Navbar → MetaBar → Tabs → Body | `ProjectWorkspaceHeader` + `ProjectTabNav` |

---

## 7. 导出批次建议

| 批次 | 节点 ID 列表 | 用途 |
|------|--------------|------|
| A · 全局 | `Ktnbv`, `qS1FU`, `Dat8t`, `adKkL`, `YVENb`, `YBU0r`, `D2Ym9` | 首页/设置/三态 |
| B · 工作台 1 | `DMGHL`, `z5gmo`, `uBzbD`, `o2Fc4r`, `Kjsvn` | Tab 1–5 |
| C · 工作台 2 | `JH3Wy`, `mL1IE`, `tNuCp`, `Cf9pk`, `sCy53` | Tab 6–10 |
| D · 工作台 3 | `N7Jsj`, `AFcII` | Tab 11–12 |
| E · 数据集子 Tab | `cV3ID`, `jUtjv`, `t6ReB`, `ianyJ` | 数据集 5 Tab |

---

*与 `aisci-ui-spec.md` 同步维护；Phase C 验收完成后更新各 Frame「验收」列为 ✅。*
