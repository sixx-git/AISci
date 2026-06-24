# AISci UI 设计规范

> 设计稿：`designs/aisci-ui.pen`（Blueprint 风格）  
> 对齐现网：`frontend/src/` · Tab 定义见 `config/projectTabs.ts`  
> 画布标准：**1440 × 960 px**（2026-06 精修版）

---

## 1. 设计原则

| 项 | 约定 |
|----|------|
| 字体 | **JetBrains Mono** 全站（标题/正文/代码注释） |
| 视觉 | 深蓝底 `#0A1628` + 青色描边 `#38BDF8`，Blueprint 网格底纹 |
| 注释 | 区块以 `// 模块名` 灰色小字标注，对应现网组件名 |
| 布局 | 工作台 Frame 统一：**Navbar → ProjectMetaBar → Tabs → Body** |
| 状态 | Loading / Error / Empty 参考 Frame `18-UI States` |

---

## 2. Design Tokens

| Token | 值 | 用途 |
|-------|-----|------|
| `$bp-bg` | `#0A1628` | 页面背景 |
| `$bp-panel` | `#0F172A` | 输入框、暗面板 |
| `$bp-surface` | `#1E293B` | 卡片表面 |
| `$bp-text` | `#E2E8F0` | 主文字 |
| `$bp-muted` | `#64748B` | 次要文字、注释 |
| `$bp-cyan` | `#38BDF8` | 主强调、链接、激活 Tab |
| `$bp-cyan-dim` | `#38BDF866` | 分隔线、弱描边 |
| `$bp-green` | `#22C55E` | 成功、运行中、通过 |
| `$bp-yellow` | `#FACC15` | HITL 暂停、警告 |
| `$bp-purple` | `#A855F7` | Discovery、证据链 |

参考 Frame：`00-Design System`（`Ktnbv`）

### 2.1 Tailwind / CSS 映射（现网）

| Pencil Token | CSS 变量 | Tailwind 类 |
|--------------|----------|-------------|
| `$bp-bg` | `--bp-bg` | `bg-bp-base` |
| `$bp-panel` | `--bp-panel` | `bg-bp-panel` |
| `$bp-surface` | `--bp-surface` | `bg-bp-surface` |
| `$bp-text` | `--bp-text` | `text-bp-text` |
| `$bp-muted` | `--bp-muted` | `text-bp-muted` |
| `$bp-cyan` | `--bp-cyan` | `bg-bp-cyan` / `text-bp-cyan` / `border-bp-cyan` |
| `$bp-cyan-dim` | `--bp-cyan-dim` | `border-bp-cyan-dim` |
| `$bp-green` | `--bp-green` | `text-bp-green` |
| `$bp-yellow` | `--bp-yellow` | `text-bp-yellow` |
| `$bp-purple` | `--bp-purple` | `text-bp-purple` |
| — | `--bp-panel-glass` | `bg-bp-panel-glass`（MetricBox `#0F172A99`） |
| — | `--bp-cyan-tint` | `bg-bp-cyan-tint`（激活 Tab `#38BDF822`） |

- **TS 单源**：`frontend/tailwind.blueprint.js`（PostCSS 加载）+ `frontend/src/config/designTokens.ts`（应用内引用）
- **全局样式**：`frontend/src/index.css`（`:root` + `.btn-primary` 等对齐 `comp/BtnPrimary`）
- **Tailwind 扩展**：`frontend/tailwind.config.js` → `theme.extend.bp.*`
- **圆角**：`rounded-bp` = 2px · **面板内边距**：`p-bp-panel` = 14px
- **字体**：`font-bp` = JetBrains Mono（Blueprint 默认正文字体）

### 2.2 语义色（Phase B-3）

| 语义 | Token / 类 | 场景 |
|------|------------|------|
| 成功 / 已完成 | `text-bp-green` · `bg-bp-green/10` | Pipeline 完成、Run 成功、支持证据 |
| 运行中 / 主强调 | `text-bp-cyan` · `bg-bp-cyan-tint` | 激活 Tab、Pipeline 运行、选中行 |
| 警告 / HITL | `text-bp-yellow` · `bg-bp-yellow/10` | 暂停、低证据、完备性提醒 |
| 失败 / 偏题 | `text-danger-400` · `bg-danger-500/10` | 错误、偏题假设 |
| 发现 / 证据链 | `text-bp-purple` | Discovery 模式、图谱高亮 |

**避免**：在新代码中使用 `text-blue-400`、`bg-primary-500/10`、`bg-gray-850`（非 Tailwind 类）等遗留色；运行态统一 `bp-cyan` 而非 `blue-*`。

---

## 3. 可复用组件（Component Library）

| 组件 ID | 名称 | 用途 | 现网对应 |
|---------|------|------|----------|
| `Jnsxl` | `comp/BtnPrimary` | 主按钮（运行 Pipeline、创建项目） | `Button variant="primary"` |
| `p35FF` | `comp/BtnSecondary` | 次按钮（上传文献、导出） | `Button variant="secondary"` |
| `C8tu6m` | `comp/MetricBox` | 指标卡（数值 + 标签） | 首页/概览 StatCard |
| `HePEC` | `comp/StatusBadge` | 状态徽章（运行中/草稿） | `StatusBadge` |
| `q2kHcM` | `comp/StageRow` | Pipeline 阶段行 | 工作流节点列表 |
| `avl0y` | `comp/AuditBlock` | 审计 JSON 块 | 闭环审计链 |

### 组件覆盖规则

- 按钮：优先 `ref: Jnsxl` / `p35FF`，通过 `descendants` 改文案
- 指标：4 列 `MetricBox` 横排，`width: fill_container`
- 面板：圆角 2px、`strokeWidth: 1`、`padding: 14`、`fill: #0F172A66`

---

## 4. Frame 索引

### 4.1 全局路由页

| Frame | 节点 ID | 路由 | 说明 |
|-------|---------|------|------|
| `00-Design System` | `Ktnbv` | — | Token + 组件预览 |
| `01-Home 首页` | `qS1FU` | `/` | 项目工作台、统计、卡片网格、Footer |
| `14-文献中心` | `Dat8t` | `/documents` | 跨项目文献库 |
| `15-报告中心` | `adKkL` | `/reports` | 跨项目报告浏览 |
| `16-设置` | `YVENb` | `/settings` | EmptyState 占位 |
| `17-创建项目` | `YBU0r` | `/projects/new` | 表单 + FL 提示 |
| `18-UI States` | `D2Ym9` | — | Loading / Error / Empty 三态 |

### 4.2 项目工作台（12 Tab）

设计 Frame 编号 ≠ Tab 顺序；Tab 顺序以 `PROJECT_TABS` 为准。

| Tab # | Tab ID | 标签 | 设计 Frame | 节点 ID |
|-------|--------|------|------------|---------|
| 1 | `overview` | 项目概览 | `02-Project Overview` | `DMGHL` |
| 2 | `closed_loop` | 科研闭环总览 | `03-Closed Loop` | `z5gmo` |
| 3 | `questions` | 研究问题 | `05-研究问题` | `uBzbD` |
| 4 | `literature` | 文献库 | `06-文献库` | `o2Fc4r` |
| 5 | `knowledge_graph` | 知识图谱 | `07-知识图谱` | `Kjsvn` |
| 6 | `datasets` | 数据集 | `08-数据集` | `JH3Wy` |
| 7 | `workflow` | 智能体工作流 | `04-Workflow` | `mL1IE` |
| 8 | `prompts` | Prompt 管理 | `09-Prompt管理` | `tNuCp` |
| 9 | `hypotheses` | 候选假设 | `10-候选假设` | `Cf9pk` |
| 10 | `experiments` | 实验设计 | `11-实验设计` | `sCy53` |
| 11 | `reports` | 研究报告 | `12-研究报告` | `N7Jsj` |
| 12 | `logs` | 运行日志 | `13-运行日志` | `AFcII` |

### 4.3 数据集页内 Tab（子 Frame）

| Frame | 节点 ID | `pageTab` | 主组件 |
|-------|---------|-----------|--------|
| `08-数据集` | `JH3Wy` | `datasets` | FL 识别、DataContext、建模、数据集卡片 |
| `08b-反馈中心 Tab` | `cV3ID` | `feedback` | `FeedbackHubPanel` |
| `08c-数据目录 Tab` | `jUtjv` | `catalog` | `DataCatalogPanel` |
| `08d-多模态 Tab` | `t6ReB` | `multimodal` | `MultimodalEvidencePanel` |
| `08e-DataFinder Tab` | `ianyJ` | `data-finder` | `DataFinderPanel` + FigureReview + ExternalCandidateTodo |

页内 Tab 文案（现网 `DatasetPage.tsx`）：

1. 项目数据集  
2. 反馈中心  
3. 数据目录  
4. 多模态证据  
5. 多源数据查找与整合  

---

## 5. 工作台外壳结构

每个 Tab Frame（`02`–`13`）共享：

```
┌─ Navbar (56px) ─────────────────────────────────────────┐
│ ← 返回 │ 项目名 │ StatusBadge │ Spacer │ 上传文献 │ 运行 Pipeline │
├─ ProjectMetaBar ──────────────────────────────────────┤
│ [领域] [模式] [当前阶段] · 描述 · 创建于 YYYY-MM-DD    │
├─ Tabs (12) ───────────────────────────────────────────┤
│ 项目概览 │ 科研闭环总览 │ … │ (当前 Tab 高亮)          │
├─ Body (fill_container) ───────────────────────────────┤
│ // 区块注释                                            │
│ … 页面内容 …                                           │
└───────────────────────────────────────────────────────┘
```

现网对应：`ProjectWorkspace.tsx`（头部 + Tab 导航 + Tab 内容）

---

## 6. 各页次级面板 ↔ 现网组件

### Tab 1 · 项目概览 `DMGHL`

| 区块 | 现网 |
|------|------|
| 6× MetricBox | `ProjectOverview` 统计 |
| Pipeline 8 阶段 | `overviewPipelineNodes` |
| 查看科研闭环总览 → | 跳转 `?tab=closed_loop` |

### Tab 2 · 科研闭环 `z5gmo`

| 面板 | 现网组件 |
|------|----------|
| Run Selector | 运行记录下拉 |
| ClosedLoopTimeline | 闭环事件时间线 |
| VersionComparePanel | `VersionComparePanel` |
| EvidenceDiffPanel | `EvidenceDiffPanel` |
| VerifiableChecksPanel | `VerifiableChecksPanel` |
| FeedbackHubPanel | `FeedbackHubPanel` |
| TeachingAutoRefinementPanel | Teaching 自动修正 |
| QualityAcceptancePanel | 质量验收 |

### Tab 7 · 工作流 `mL1IE`

| 区块 | 现网 |
|------|------|
| RunModeConfig | Teaching 模式、num_ideas、沙箱 |
| WorkflowActionBar | 运行 / 从阶段重跑 |
| Pipeline Node List (左) | 9 阶段节点 |
| Detail Panel (右) | `AgentDetailPanel`、日志、HITL 等 |
| HitlGatePanel | `HitlGatePanel`（Detail 内） |
| FederatedCampaignPanel | `FederatedCampaignPanel` |
| DiscoveryLoopPanel | `DiscoveryLoopPanel` |

Pipeline 9 阶段：问题理解 → 文献挖掘 → **多源数据采集** → 知识缺口 → 假设生成 → 假设评估 → 实验设计 → 小样验证 → 报告生成

### Tab 4 · 文献库 `o2Fc4r`

页内 Tab：`upload` / `arxiv` / `library`  
组件：StatCards、Upload Dropzone、ChunkViewerPanel、Empty/Loading 占位

### Tab 5 · 知识图谱 `Kjsvn`

KG Top Bar（构建/增量重建/缩放/标签/导出）、Graph Canvas、Relation Filter、Graph Stats、EntityDetailPanel

### Tab 9 · 候选假设 `Cf9pk`

| 区域 | 组件 |
|------|------|
| 左 | `HypothesisTreePanel` |
| 中 | 假设卡 + 五维评分 + 偏题折叠 |
| overlay | `EvidenceChainDrawer`（抽屉 + backdrop） |
| 行内 | LoadingState / EmptyState |

### Tab 10 · 实验设计 `sCy53`

| 列 | 组件 |
|----|------|
| 主栏 | 实验目标、Baselines、Metrics、步骤、风险 |
| 侧栏 | FL Experiment Plan、Primary Hypothesis Actions、VerifiabilityChecklist |

### Tab 11 · 研究报告 `N7Jsj`

左：MarkdownPreview + 章节目录  
右：ReportChecklist、QualityCheckCard、EvidenceChainQualityCard、HITL

### Tab 12 · 运行日志 `AFcII`

| 列 | 组件 |
|----|------|
| 左 | Run 列表 |
| 中 | `RunLogDetail`（output / input / params / error） |
| 右 | 阶段日志流 |

---

## 7. 全局顶栏

| 页面 | Navbar 结构 |
|------|-------------|
| 首页 / 文献 / 报告 | `[AISci]` + Tab 导航 + `API 管理 · qwen-max ▾` |
| 工作台 02–13 | 见 §5 |
| 设置 | LLM 配置 + 环境变量说明 | `pages/Settings.tsx` |

现网：`Navbar.tsx` + `ApiManagementPanel`

---

## 8. 画布布局（Y 坐标参考）

| Y | 行内容 |
|---|--------|
| 0 | `00-Design System` · `01-Home` · `17-创建项目` |
| 1008 | `14-文献中心` · `15-报告中心` · `16-设置` · `18-UI States` |
| 2016 | 工作台 Tab 1–5（02–06） |
| 3024 | 工作台 Tab 6–10（07–11） |
| 4032 | 工作台 Tab 11–12（12–13） |
| 5040 | 数据集子 Tab b/c/e |
| 6048 | 数据集子 Tab d（多模态） |

行间距：**48 px**；Frame 高度：**960 px**。

---

## 9. Pencil MCP 操作备忘

| 操作 | 说明 |
|------|------|
| 读设计 | **必须**用 Pencil MCP，勿直接改 `.pen` JSON |
| `batch_get` | 按节点 ID 读结构 |
| `batch_design` | `Insert` / `Update` / `Delete` / `Move` |
| `Move(id, parent, index)` | index 不得超过父节点子数 |
| text 节点 | 不支持 `padding`；用外层 frame |
| `textGrowth` | 仅 `auto` / `fixed-width` / `fixed-width-height` |
| `get_screenshot` | 按 Frame ID 验收 |

---

## 10. 对齐状态（2026-06）

| 阶段 | 范围 | 状态 |
|------|------|------|
| P0 | Tab 文案、Pipeline 8 阶段、核心 5 屏 | ✅ |
| P1 | MetaBar、Navbar 双按钮、图谱/日志/假设/数据集主视图 | ✅ |
| P2 | 数据集 5 Tab、工作流 Detail 收拢、报告中心、UI States | ✅ |
| Phase C | 设置页、UI 三态推广、假设三栏、验收清单 | 🟡 |

### Phase C 进度（2026-06）

| 项 | 状态 |
|----|------|
| `/settings` LLM 配置页 | ✅ |
| `LoadingState` / `ErrorState` / `EmptyState` 主要 Tab | ✅ |
| 候选假设三栏（`Cf9pk`） | ✅ |
| 知识图谱 Blueprint 画布 | ✅ |
| 验收清单 | ✅ `designs/aisci-ui-acceptance.md` |
| Pencil PNG 批量导出 | 🟡 MCP 路径受限，见验收清单 §1 |

### 后续可选

- Pencil `export_nodes` 全量 PNG 至 `designs/exports/`
- 图谱节点色与 Neo4j 科研色板微调
- 各 Tab 像素级逐块对照（MetaBar 高度、Tab 间距）

---

*本文档由设计稿 `aisci-ui.pen` 自动归纳，与现网 `frontend/src` 同步维护。*
