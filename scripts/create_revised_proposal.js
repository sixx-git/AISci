const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  ImageRun,
  Header,
  Footer,
  AlignmentType,
  LevelFormat,
  TableOfContents,
  HeadingLevel,
  BorderStyle,
  WidthType,
  ShadingType,
  VerticalAlign,
  PageNumber,
  PageBreak,
} = require("C:/Users/lly18/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/docx");

const ROOT = "D:/Workplace/AISci";
const OUTPUT = path.join(ROOT, "output", "联邦智研_申报书_修改稿.docx");
const FIG_DIR = path.join(ROOT, "output", "innovation_schematics");
const FULL_WIDTH = 9026;

const COLORS = {
  navy: "1F4E79",
  blue: "D9EAF7",
  blue2: "EAF3F8",
  green: "E2F0D9",
  orange: "FCE4D6",
  purple: "EDE7F6",
  gray: "F2F2F2",
  line: "B7C9D6",
  text: "222222",
  muted: "666666",
};

const children = [];

function run(text, opts = {}) {
  return new TextRun({
    text: String(text),
    font: opts.font || "Microsoft YaHei",
    size: opts.size || 21,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || COLORS.text,
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    alignment: opts.alignment,
    style: opts.style,
    spacing: opts.spacing || { after: 120, line: 360, lineRule: "auto" },
    indent: opts.indent,
    pageBreakBefore: opts.pageBreakBefore,
    children: [run(text, opts)],
  });
}

function addPara(text, opts = {}) {
  String(text).split("\n").forEach((line) => children.push(para(line, opts)));
}

function addHeading(level, text) {
  const heading = level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
  children.push(new Paragraph({
    heading,
    spacing: { before: level === 1 ? 300 : 180, after: 160, line: 300, lineRule: "auto" },
    children: [run(text, { bold: true, size: level === 1 ? 31 : level === 2 ? 27 : 23, color: level === 1 ? COLORS.navy : COLORS.text })],
  }));
}

function addPageBreak() {
  children.push(new Paragraph({ children: [new PageBreak()] }));
}

function addBullet(text) {
  children.push(new Paragraph({
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 80, line: 330, lineRule: "auto" },
    children: [run(text)],
  }));
}

function addNumber(text) {
  children.push(new Paragraph({
    numbering: { reference: "number-list", level: 0 },
    spacing: { after: 80, line: 330, lineRule: "auto" },
    children: [run(text)],
  }));
}

function addSource(text) {
  children.push(para(`来源/证据边界：${text}`, {
    style: "SourceNote",
    size: 17,
    color: COLORS.muted,
    italics: true,
    spacing: { after: 130, line: 280, lineRule: "auto" },
  }));
}

function cellParagraph(text, opts = {}) {
  return new Paragraph({
    alignment: opts.alignment || AlignmentType.LEFT,
    spacing: { after: 0, line: 260, lineRule: "auto" },
    children: [run(text, { size: opts.size || 17, bold: opts.bold || false, color: opts.color || COLORS.text })],
  });
}

function tableCell(text, width, opts = {}) {
  const lines = String(text).split("\n");
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 90, bottom: 90, left: 110, right: 110 },
    shading: { fill: opts.fill || "FFFFFF", type: ShadingType.CLEAR },
    verticalAlign: opts.verticalAlign || VerticalAlign.CENTER,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: COLORS.line },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: COLORS.line },
      left: { style: BorderStyle.SINGLE, size: 1, color: COLORS.line },
      right: { style: BorderStyle.SINGLE, size: 1, color: COLORS.line },
    },
    children: lines.map((line) => cellParagraph(line, opts)),
  });
}

function addTable(headers, rows, widths, opts = {}) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((header, i) => tableCell(header, widths[i], {
      fill: opts.headerFill || COLORS.blue,
      bold: true,
      size: opts.headerSize || 17,
      alignment: AlignmentType.CENTER,
    })),
  });
  const bodyRows = rows.map((row) => new TableRow({
    children: row.map((value, i) => tableCell(value, widths[i], {
      fill: opts.bodyFill || "FFFFFF",
      size: opts.bodySize || 16,
      alignment: opts.bodyAlignment || AlignmentType.LEFT,
    })),
  }));
  children.push(new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...bodyRows],
  }));
  children.push(para("", { spacing: { after: 80, line: 120, lineRule: "auto" } }));
}

function addFigure(filename, caption, source) {
  const file = path.join(FIG_DIR, filename);
  if (!fs.existsSync(file)) throw new Error(`Missing figure: ${file}`);
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 80 },
    children: [new ImageRun({
      type: "png",
      data: fs.readFileSync(file),
      transformation: { width: 560, height: 350 },
      altText: { title: caption, description: caption, name: filename },
    })],
  }));
  children.push(para(caption, { alignment: AlignmentType.CENTER, bold: true, size: 18, spacing: { after: 50 } }));
  addSource(source);
}

// Cover
children.push(para("联邦智研（AISci）", { style: "CoverTitle", alignment: AlignmentType.CENTER, size: 42, bold: true, color: COLORS.navy, spacing: { before: 500, after: 180 } }));
children.push(para("——基于 Qwen 的多智能体科研自动化系统", { style: "CoverSubtitle", alignment: AlignmentType.CENTER, size: 25, color: COLORS.muted, spacing: { after: 360 } }));
children.push(para("大学生创新创业大赛申报书（修改稿）", { style: "CoverDocTitle", alignment: AlignmentType.CENTER, size: 32, bold: true, spacing: { after: 520 } }));
addTable(
  ["申报信息", "内容"],
  [
    ["参赛赛道", "高教主赛道·人工智能+"],
    ["参赛组别", "创意组"],
    ["项目类型", "人工智能"],
    ["作品方向", "A. 科学假设生成与研究计划设计"],
    ["技术底座", "Qwen（千问）/ 阿里云百炼"],
  ],
  [2600, 6426],
  { headerFill: COLORS.blue, bodySize: 20, headerSize: 19 },
);
children.push(para("本修改稿在原申报书基础上重组论证链，突出“现有做法—具体不足—本项目创新—指标化评估—证据边界”。原始申报书文件保持不变。", {
  style: "CoverNote",
  alignment: AlignmentType.CENTER,
  size: 18,
  color: COLORS.muted,
  spacing: { before: 500, after: 0, line: 300, lineRule: "auto" },
}));
addPageBreak();

// Contents
children.push(para("目录", { style: "TOCTitle", alignment: AlignmentType.CENTER, size: 30, bold: true, color: COLORS.navy, spacing: { before: 160, after: 220 } }));
children.push(new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }));
addPageBreak();

// Abstract
addHeading(1, "摘要");
addPara("研究背景与问题。大语言模型能够提升文献阅读、信息抽取和文本生成效率，但现有科研智能体通常把“能生成内容”作为主要目标，尚未充分解决三类决定科研可用性的约束：第一，生成的科学声明是否能回溯到真实、具体的文献事实；第二，阶段输出何时可以继续、何时必须暂停，是否有可审计的判定边界；第三，实验反馈、人工修改和新增证据能否沿着正确的阶段重新进入系统。由此形成的核心矛盾是：科研自动化需要更高的自主性，而科学结论又必须接受证据、质量和人工决策的约束。");
addPara("项目方案。联邦智研（AISci）以 Qwen 为底座，将“问题理解→文献挖掘→知识缺口→假设生成→假设评审→迭代实验→报告生成”封装为七阶段 Pipeline，并围绕上述矛盾设计四项相互配合的方法创新：一是以 Fact 白名单和双向证据检索构建 Evidence Chain Builder；二是以 0/1 阶段特定 Verdict Gate 替代没有明确决策含义的连续评分；三是以 Feedback Hub + HITL 将反馈结构化为可注入约束并支持从指定阶段重跑；四是在实验设计前加入 L0 反事实预演，对不可证伪、无证据、无低成本检验或缺少决策影响的场景进行过滤。");
addPara("评估与已有结果。申报书中的系统对比采用能力边界矩阵，不把公开产品功能描述误写为受控实验结果；项目自身结果只引用已有运行记录。当前记录包括：Science 125 问题基准子集 n=10 的端到端运行，平均耗时 167.5 s，范围 39.3–196.6 s，累计 Token 4,033,770，记录阶段 802 个；系统实现了 7 阶段 Pipeline、6 个 Agent、约 70 个 Skill、11 类阶段特定 Gate，以及审计链和反馈重跑机制。对于尚未完成同数据、同模型、同提示词的基线对照，本文明确标记为“待补测”，不虚构提升百分比。");
addPara("项目价值。AISci 的核心贡献不是将多个 LLM 工具简单拼接，而是把科研自动化中的“证据合法性、质量决策和反馈可控性”转化为系统级约束，使假设生成结果具有可追溯、可暂停、可修订和可复现的工程条件。", { style: "KeyParagraph" });
addSource("原申报书摘要、第三章至第七章；项目运行记录中的 Science 125 子集与端到端开销统计。上述 167.5 s、39.3–196.6 s、4,033,770 Token、802 个阶段为原稿已记录数据，不代表与外部系统的受控性能比较。 ");

addHeading(1, "核心创新与评估证据总览");
addPara("本项目的创新点按同一逻辑展开：先说明同类做法已经解决了什么，再指出其在科研场景中的具体不足，随后给出 AISci 针对该不足的机制设计，最后给出能够被检查的指标和当前证据。这样可以把“功能清单”转化为“问题—方法—证据”的创新论证。");
addTable(
  ["创新点", "同类做法及不足", "AISci 针对性机制", "评价指标", "当前证据状态"],
  [
    ["证据链迭代推理", "RAG/Agentic RAG 侧重检索到证据，但引用对象、声明与事实的绑定可能仍由模型自由生成。", "Fact 白名单、支持/反证双向检索、stance 分类、引用完整性检查、证据链审计。", "合法 fact 引用率；证据链完备度；双向证据平衡分；引用完整性 Gate。", "机制已实现；原稿提供 n=10 验收口径，缺少逐样本基线提升率。"],
    ["Verdict Gate", "连续分数能排序，却不能直接说明是否继续、暂停或重跑；不同阶段阈值含义也不一致。", "11 类阶段特定 0/1 Gate，记录 PASS/FAIL、原因、阻塞项和证据引用，并支持停滞暂停。", "Gate 覆盖率；判定可复现率；连续失败停滞触发率；审计完整率。", "11 类 Gate 与趋势追踪已实现；待补齐跨基线统计。"],
    ["Feedback Hub + HITL", "硬编码阶段传递或静态人工审核难以把反馈精确作用到目标阶段。", "多源反馈统一转为约束文本，写入 global_constraints，按目标映射注入上下文并支持指定阶段重跑。", "反馈注入完整率；目标阶段命中率；重跑成功率；人工修改采纳率。", "Feedback Hub、目标映射、审计与重跑接口已实现。"],
    ["L0 反事实预演", "不少流程直接从假设进入实验，缺少对不可证伪和高风险失败模式的低成本筛查。", "FALSIFY 过滤器检查可证伪性、fact 证据、cheap test、decision impact 和风险；高风险且无失败模式时阻断实验。", "有效场景保留率；高风险不可控阻断率；对照方案覆盖率；实验前过滤耗时。", "过滤逻辑与约束注入已实现；尚无大规模场景统计。"],
  ],
  [1300, 1900, 2300, 1800, 1726],
  { bodySize: 15 },
);
addSource("评估指标是对已有系统字段、Gate、审计事件和运行记录的整理；没有现成对照数据的项目，不在本稿中强行填入数值。 ");

addHeading(1, "一、研究问题与解决方法");
addHeading(2, "1.1 研究背景与主要矛盾");
addPara("科研信息获取、证据核验和实验设计之间存在明显的流程断裂：检索工具可以返回大量文献片段，生成模型可以给出看似合理的假设，实验工具可以运行脚本，但三者之间缺少统一的证据对象、质量判定和反馈协议。结果是“文本能够生成”不等于“研究结论可以使用”。");
addPara("本项目聚焦的主要矛盾是“自动化效率与科学可靠性的矛盾”。如果完全依赖模型自主生成，系统可能出现幻觉引用、证据单边、不可执行计划和高风险实验；如果全部依赖人工核对，自动化又退化为检索和写作助手。因此，需要把可靠性要求编码进数据结构、阶段门禁和反馈路由，而不是仅在最终文本上做一次人工检查。", { style: "KeyParagraph" });
addPara("形式化地，给定研究问题 Q、文献事实集合 E、数据与实验约束 D，系统需要生成候选假设 H、实验计划 P 和审计记录 A，使得：H 中的引用能够映射到 E；P 能够回答 H 的可验证子问题；每个阶段都有明确的继续/暂停/重跑决策；反馈能够回到正确的阶段并留下可复核记录。", { style: "FormulaParagraph" });
addSource("研究问题与解决逻辑来自原申报书第一章，并结合项目代码中的 Pipeline、EvidenceChain、Verdict Gate、Feedback Hub 和 Counterfactual 模块重新表述。 ");

addHeading(2, "1.2 现有做法、具体不足与本项目切入点");
addTable(
  ["现有做法", "已经解决的问题", "在本项目场景中的不足", "AISci 的切入点"],
  [
    ["文献检索与 RAG", "扩大检索范围、召回相关段落、辅助生成引用。", "检索结果不等于事实对象；模型仍可能把未验证内容写入假设，无法保证每条声明都可追溯。", "将事实显式注册为 fact_id，生成与修订只能引用 Fact 白名单，并保留来源 chunk_id。"],
    ["自主科研智能体", "自动提出假设、编写代码、运行实验并循环修改。", "自动链路可能缺少证据门禁和人工暂停点；实验失败后不一定能解释是哪条证据或约束导致。", "将证据链、Verdict Gate、HITL 和 Feedback Hub 作为运行时机制，而不是附加页面。"],
    ["文献理解/对话工具", "支持用户阅读、提问、整理和人工校正。", "通常是静态会话或文档级理解，反馈不能自动作用于后续假设、实验和报告阶段。", "将人工修改结构化为约束，按目标阶段注入并支持 rerun_from_stage。"],
    ["连续评分与人工经验", "能够给候选结果排序，便于快速筛选。", "分数缺少统一的通过含义；不同阶段的 70 分不能直接转化为继续或暂停决策。", "用阶段特定的 0/1 Gate 输出 PASS/FAIL、原因、阻塞项和证据引用。"],
    ["直接进入实验设计", "减少流程步骤，快速形成实验草案。", "不可证伪、缺少证据或无法影响决策的场景可能消耗后续实验资源。", "在实验设计前增加 L0 FALSIFY 层，优先过滤高风险且不可控路径。"],
  ],
  [1700, 2200, 2700, 2426],
  { bodySize: 16 },
);
addSource("此表是基于原申报书第三章相关工作对比、项目代码结构和公开产品能力边界形成的系统分析，不是同数据集上的性能实验。 ");

addHeading(2, "1.3 核心研究问题与目标");
addPara("核心研究问题：如何构建一个人机协作的多智能体系统，使其能够基于真实文献证据生成可验证的科学假设，并在质量不达标、证据不足或实验风险不可控时自动暂停、补证据或从指定阶段重跑？");
addNumber("证据溯源：建立科学声明、文献事实、数据字段和最终假设之间的可追溯映射，避免把模型生成内容误当作外部事实。");
addNumber("质量决策：把新颖性、证据、可执行性、沙箱、图表、HITL 等要求转化为阶段特定的判定式 Gate，并记录可审计原因。");
addNumber("反馈闭环：把实验结果、文献补充、Data Finder 发现、人工审核和用户输入统一为约束，精确触发后续阶段或指定阶段的重跑。");
addNumber("实验风险：在实验设计前进行 L0 反事实预演，筛除无法证伪、缺少证据或无法影响决策的场景，降低无价值实验的概率。");

addHeading(2, "1.4 技术路线与解决思路");
addPara("系统以七阶段 Pipeline 为主线：问题理解→文献挖掘→知识缺口→假设生成→假设评审→迭代实验→报告生成。四项创新分别位于证据治理、质量决策、反馈传输和实验前筛查四个关键位置，形成“生成—核验—判定—反馈—重跑”的闭环，而不是四个相互独立的功能模块。");
addTable(
  ["阶段", "核心输入", "核心输出", "质量/反馈作用"],
  [
    ["Problem Understanding", "研究问题文本", "主要矛盾、研究对象、边界、目标", "把模糊问题转为可研究对象"],
    ["Literature Mining", "问题、关键词、文献库", "facts、evidence、citation_map", "为 Fact 白名单提供事实来源"],
    ["Knowledge Gap", "文献事实、不确定点", "knowledge_gaps、矛盾点、机会", "形成假设的证据缺口"],
    ["Hypothesis Generation", "知识缺口、证据", "候选假设、fact_ids、可验证规格", "领域对齐与候选排序"],
    ["Hypothesis Review", "候选假设、文献上下文", "新颖性、可行性、反事实预演", "Verdict Gate 与 L0 过滤"],
    ["Iterative Experiment", "数据、计划、约束", "脚本、执行结果、分析反馈", "沙箱/可执行性 Gate 与反馈回流"],
    ["Report Generation", "全流程中间产物", "结构化报告、引用、合规检查", "审计导出和最终质量检查"],
  ],
  [1700, 2200, 2700, 2426],
  { bodySize: 16 },
);

addHeading(1, "二、系统架构与流程设计");
addHeading(2, "2.1 三层架构");
addPara("系统采用 Agent—Skill—Infrastructure 三层结构。Agent 层负责阶段编排与 Qwen 调用；Skill 层提供文献检索、证据推理、数据清洗、反事实筛查、图表检查等可复用能力；Infrastructure 层负责 FastAPI 服务、SQLite 数据库、zvec 向量检索、PyMuPDF/PDF 解析、审计链和前端工作台。");
addTable(
  ["架构层", "实现", "职责", "可复核对象"],
  [
    ["Agent", "6 个独立 Agent 类 + Prompt 模板", "流程编排、输入输出 Schema、LLM 调用", "Agent 输出 JSON、模型参数、Prompt 版本"],
    ["Skill", "约 70 个模块，覆盖 8 个科研子领域", "检索、证据、数据、推理、反事实和报告检查", "SkillResult、warnings、metadata"],
    ["Infrastructure", "FastAPI + SQLite + zvec + PyMuPDF + React/Vite", "API、存储、向量搜索、前端展示与审计", "API 日志、audit/{run_id}.jsonl、数据库记录"],
  ],
  [1700, 2600, 2900, 1826],
  { bodySize: 16 },
);
addPara("当前服务接口覆盖 Pipeline 启动、证据链迭代、溯源时间线、反馈提交、人工审核、指定阶段重跑和迭代实验等路径。接口的意义不只是提供前端按钮，而是把阶段之间的数据传递和审计对象固定下来，使四项创新可以被调用、检查和复现。", { style: "KeyParagraph" });
addSource("依据：backend/README.md 中的 API、存储和架构说明；原申报书第二章、第三章和第九章。 ");

addHeading(2, "2.2 数据传输与审计协议");
addPara("每个阶段使用标准化 JSON 结构传递 input_data、output_data、prompt_used、model_parameters、token_count、duration_ms 和 CallLog。EvidenceChain 使用 fact_id、source_chunk_id、supporting_evidence、counter_evidence 和 revision_history；Feedback Hub 使用 source、target、payload、constraints、trigger_rerun 和 applied；Verdict Gate 使用 passed、gate_id、reasons、blockers 和 evidence_refs。这样，模块之间传输的是可检查的数据对象，而不是不可解释的自由文本。");
addTable(
  ["对象", "关键字段", "传输方向", "质量含义"],
  [
    ["Fact", "fact_id、source_chunk_id、claim", "Literature Mining → Hypothesis / Evidence Chain", "约束引用合法性和来源定位"],
    ["Evidence Chain", "supporting、counter、balance、completeness、revision_history", "Evidence Chain → Review / Report", "同时保存支持与反证，避免单边证据"],
    ["Gate Result", "passed、gate_id、reasons、blockers", "每阶段 → Pipeline 控制器", "决定 continue、pause 或 rerun"],
    ["Feedback Entry", "source、target、constraints、trigger_rerun", "HITL/Data/Literature → Hub → 后续阶段", "把反馈变成可定位约束"],
    ["Audit Event", "input、output、prompt、model、token、duration", "全链路 → JSONL 审计", "支持复现和第三方检查"],
  ],
  [1800, 3000, 2300, 1926],
  { bodySize: 16 },
);

addHeading(1, "三、项目工作流程与人机协作");
addHeading(2, "3.1 七阶段 Pipeline");
addPara("用户从前端输入科学问题后，通过 POST /api/v1/pipeline/run 启动流程；前端 PipelineProgress 展示阶段状态，RunLogDetail 查看阶段输入输出与审计信息。每个阶段的输出先经过相应 Gate，再决定是否进入下一阶段。");
addNumber("问题理解：识别主要矛盾、研究对象、边界和预期输出。");
addNumber("文献挖掘：从本地文献库、arXiv 和开放数据源中召回片段，提取结构化事实并绑定 chunk_id。");
addNumber("知识缺口：分析事实覆盖范围、不确定点和冲突，形成可研究的知识空白。");
addNumber("假设生成：生成候选假设，绑定 supporting_fact_ids，执行领域对齐与 Margin-Weighted Tournament。");
addNumber("假设评审：开展新颖性、可行性、Ensemble 和 L0 反事实预演，输出 Gate 判定。");
addNumber("迭代实验：绑定数据集，执行 Plan→Execute→Analyze→Reflect 闭环，并通过可执行性和沙箱 Gate。");
addNumber("报告生成：聚合 12 个标准字段，进行引用、数据、图表和结果类型检查，导出报告与审计链。");

addHeading(2, "3.2 HITL 与科学自迭代");
addPara("当某阶段 Gate 失败、证据强度不足或连续多轮没有改善时，Pipeline 自动暂停并进入人工审核。用户可以查看和编辑阶段输出、提交结构化反馈、与阶段结果对话，或从 literature_mining、hypothesis_generation、hypothesis_review、iterative_experiment 等阶段重跑。人工审核不是对模型结果的简单“点赞”，而是将修订意见写入 Feedback Hub，作为后续阶段可以读取的约束。");
addPara("当触发 evidence_weak、review_reject 或 validation_feedback 时，ScienceIterationOrchestrator 记录本轮驱动来源、数据变化、计划变化和主假设变化，随后执行补文献、重建证据链、重跑假设树和再评审。VersionComparePanel 展示迭代前后的评分 delta、证据增量和计划变化。", { style: "KeyParagraph" });
addSource("依据：原申报书第三章 3.2、3.3、7.2、7.3；backend/app/services/feedback_hub_service.py、science_iteration_service.py 和 pipeline API。 ");

addHeading(1, "四、四项核心创新及运行机制");
addPara("本章是本次修改的重点。每一项创新均按“别人怎样做—不足是什么—我们解决什么明确问题—怎样运行—如何评估”的顺序展开。表中的定量数值只使用项目已有记录；尚未完成匹配基线实验的地方，明确写出证据边界。", { style: "KeyParagraph" });

addHeading(2, "4.1 多轮证据链迭代推理引擎：从“检索到证据”推进到“声明可追溯”");
addPara("现有做法及不足。RAG 或 Agentic RAG 主要优化“检索—增强—生成”的路径，能够帮助模型找到相关片段，但检索到的片段并不会自动成为合法事实对象。若声明、引用和事实之间没有固定 ID 和反向映射，模型仍可能拼接多个片段、遗漏反证，或在修订时生成无法核验的引用。对科研假设而言，真正需要回答的问题不是“有没有引用”，而是“每条关键声明是否绑定到可定位事实，是否经过反证检索，是否能解释为何收敛”。");
addPara("针对性创新。EvidenceChainBuilder 将科学声明、文献事实、支持证据、反证证据和假设版本组织成结构化链条。LLM 只能引用 fact_whitelist 中存在的 fact_id；每轮迭代同时检索支持证据与反证据，再进行 stance 分类、证据接地和引用完整性检查。链条保存 evidence_balance_score、chain_completeness、citation_reliability、support_count、counter_count 和 revision_history，使假设从“有引用的文本”变成“可被审计的证据对象”。");
addNumber("提取科学声明：将假设拆分为可核验的 claim。");
addNumber("检索支持证据和反证据：保留双向证据，而不是只找支持材料。");
addNumber("判定证据立场：使用已有 stance、反证关键词和中英混合相关性评分。");
addNumber("执行 Fact 白名单约束：修订后再次过滤 cited_fact_ids，拒绝未授权引用。");
addNumber("检查接地与完整性：记录引用、来源、证据平衡、完备度和版本历史。");
addFigure("fig_innovation_1_evidence_chain.png", "图 4-1 证据链迭代推理引擎：Fact 白名单、双向证据与降级路径", "原申报书第四章 4.1；脚本 output/innovation_schematics/fig_innovation_1_evidence_chain.png。 ");
addTable(
  ["指标", "计算/判定方式", "常见做法可观察状态", "AISci 当前可验证状态"],
  [
    ["合法 fact 引用率", "有效 cited_fact_ids / 全部 cited_fact_ids", "通常只记录检索结果或文本引用，缺少统一白名单。", "已实现白名单过滤；验收要求未授权引用为 0，逐样本提升率待补测。"],
    ["证据链完备度", "support、counter、revision_history 按链条规则计分", "支持证据与反证证据不一定同时保存。", "EvidenceChainBuilder 输出 chain_completeness、support_count、counter_count。"],
    ["引用完整性 Gate", "引用映射、来源定位和报告字段全部满足才通过", "多为最终文本检查，失败后不一定回到证据阶段。", "gate_evidence 与 ReportQualityCheckSkill 可阻断报告生成。"],
    ["可复核性", "能否由 fact_id 回到 source_chunk_id 和审计事件", "公开工具常停留在 URL/段落级引用。", "事实、声明、版本和审计事件均有结构化字段。"],
  ],
  [1700, 2700, 2200, 2426],
  { bodySize: 16 },
);
addSource("代码依据：backend/app/skills/evidence_reasoning/evidence_chain_builder_skill.py、evidence_retrieval_skill.py、counter_evidence_retrieval_skill.py、citation_integrity_check_skill.py。 ");

addHeading(2, "4.2 判定式质量门禁：从“分数排序”推进到“可执行决策”");
addPara("现有做法及不足。连续评分适合排序候选项，却不天然提供流程决策：一个输出得到 70 分，不能直接说明它是否满足证据、数据、可执行性或人工审核条件；不同阶段的分数也不能简单横向比较。若没有明确的 PASS/FAIL 和阻塞原因，自动化系统很难在失败时暂停或选择正确的修复路径。");
addPara("针对性创新。Verdict Gate 将阶段质量要求写成布尔判定。系统当前配置 11 类阶段特定 Gate，包括新颖性、Ensemble、证据链、可执行性、沙箱、图表、覆盖度、HITL、验收、CoT 和联邦双门槛。每个 Gate 输出 passed、gate_id、reasons、blockers 和 evidence_refs；趋势追踪记录连续失败次数和改善趋势，连续失败且无改善时触发 HITL 暂停。由此，质量分数负责解释和排序，Gate 负责控制流程。");
addTable(
  ["指标", "定义", "项目中的实现/记录", "创新展示方式"],
  [
    ["Gate 覆盖率", "已配置且实际执行的 Gate 数 / 适用 Gate 数", "11 类阶段特定 Gate；每个阶段按适用条件执行。", "将“有质量检查”转化为可盘点的门禁覆盖范围。"],
    ["判定可复现率", "同一输入、规则和证据下得到相同 PASS/FAIL 的比例", "Gate 输出布尔结果、原因和证据引用；规则逻辑可被回放。", "从主观分数转为可审计决策。"],
    ["停滞触发率", "连续失败且无改善时正确触发暂停的事件比例", "summarize_gate_trend 跟踪失败次数和改善趋势。", "把“继续尝试”变为有停止边界的闭环。"],
    ["审计完整率", "包含输入、输出、规则、原因和证据引用的 Gate 事件占比", "审计链支持 jsonl 导出。", "支持第三方复核和问题定位。"],
  ],
  [1700, 2500, 2600, 2226],
  { bodySize: 16, headerFill: COLORS.purple },
);
addFigure("fig_innovation_2_verdict_gate.png", "图 4-2 Verdict Gate：阶段质量判定、通信与人工放行机制", "原申报书第四章 4.2；脚本 output/innovation_schematics/fig_innovation_2_verdict_gate.png。 ");
addSource("代码依据：backend/app/core/quality_scoring.py、iteration_control.py、closed_loop_quality_service.py；原申报书第四章 4.2、七章 7.1–7.4。当前证据支持“机制已实现”和“11 类 Gate 已配置”，不等同于已完成跨系统性能对照。 ");

addHeading(2, "4.3 统一反馈中心 + HITL：从“人工意见”推进到“可路由约束”");
addPara("现有做法及不足。硬编码阶段传递能够实现固定流程，但难以覆盖新增的数据来源和非线性重跑；静态 HITL 只能在页面上修改结果，人工意见未必能进入后续 Prompt，也无法说明应从哪一阶段重跑。反馈如果没有来源、目标、载荷和审计状态，就难以验证是否真正改变了系统行为。");
addPara("针对性创新。Feedback Hub 将 HITL、Data Finder、Provenance、Literature、User 等来源的消息统一转换为约束文本，保存 source、target、payload、constraints、trigger_rerun 和 applied。global_constraints 最多保留 50 条，并通过 STAGE_TO_FEEDBACK_TARGET 与 RERUN_TARGETS 映射到目标阶段；后续阶段通过 get_active_constraints 注入上下文，必要时调用 rerun_from_stage。人工审核因此成为闭环控制的一部分，而不是独立的意见收集页面。");
addTable(
  ["指标", "定义", "当前实现状态", "需要如何读结果"],
  [
    ["反馈注入完整率", "成功写入 Hub 且被后续阶段读取的有效约束 / 有效反馈条目", "submit_feedback、get_active_constraints、applied 字段已实现。", "需要从审计事件汇总；当前报告不虚构总体百分比。"],
    ["目标阶段命中率", "实际重跑阶段与 target 映射一致的事件 / 触发重跑事件", "RERUN_TARGETS 和 STAGE_TO_FEEDBACK_TARGET 已实现。", "可由 rerun_from_stage 与 audit 记录计算。"],
    ["反馈来源覆盖度", "实际接入来源种类 / 设计来源种类", "基础五类来源，代码兼容 kg、multimodal 扩展来源。", "展示系统能否吸收不同证据和人工输入。"],
    ["人工修订可追溯率", "有 human_modified_output、反馈和后续版本关联的审核事件 / 审核事件", "HITL API、stage_chat、save_stage_human_output 和审计字段已存在。", "需要用实际运行日志补充样本统计。"],
  ],
  [1700, 2700, 2500, 2126],
  { bodySize: 16, headerFill: COLORS.green },
);
addFigure("fig_innovation_3_feedback_hub.png", "图 4-3 Feedback Hub + HITL：跨阶段反馈传输与指定阶段重跑", "原申报书第四章 4.3；脚本 output/innovation_schematics/fig_innovation_3_feedback_hub.png。 ");
addSource("代码依据：backend/app/services/feedback_hub_service.py、backend/app/api/feedback.py、backend/app/api/human_loop.py、backend/app/api/pipeline.py。 ");

addHeading(2, "4.4 L0 反事实预演：从“直接做实验”推进到“先筛风险”");
addPara("现有做法及不足。许多自动化科研流程在候选假设通过文本评审后，直接进入实验设计或代码生成。对于不可证伪、证据不足、没有低成本检验或即使成立/失败也不会改变决策的场景，后续实验难以产生有效信息。此类问题不应等到沙箱执行失败后才发现，而应在实验设计之前以较低成本筛查。");
addPara("针对性创新。CounterfactualPreview 在 Hypothesis Review 与 Iterative Experiment 之间加入 L0 定性层。FALSIFY 过滤器依次检查 intervention、question、predicted_outcome、falsifiable、cheap_test、evidence_fact_ids、decision_impact 和与主假设的对齐关系；保留的场景被转成实验设计约束，尤其是高风险场景的对照组建议。当存在高风险场景但 failure_predictions 为空时，系统将 proceed_to_iterative_experiment 置为 False，要求补证据、补失败模式或重新评审。");
addTable(
  ["指标", "定义", "项目实现", "结论边界"],
  [
    ["有效场景保留率", "通过 FALSIFY 的场景数 / LLM 原始场景数", "记录 raw_scenario_count 与 filtered_count。", "可以逐运行计算；当前没有汇总样本分布。"],
    ["高风险不可控阻断率", "高风险且无失败模式的场景被阻断数 / 同类场景数", "高风险 + failure_predictions 为空时 proceed=False。", "机制上有明确判定，效果仍需场景集对照。"],
    ["证据绑定率", "保留场景中含有效 evidence_fact_ids 的场景 / 保留场景数", "valid_fact_ids 与 evidence_fact_ids 交叉检查。", "可直接从 preview JSON 统计。"],
    ["实验约束注入率", "被转成 experiment 约束的有效预演结果 / 有效预演结果", "build_counterfactual_feedback_constraints 负责转换。", "需要结合后续实验审计链统计。"],
  ],
  [1700, 2700, 2600, 2026],
  { bodySize: 16, headerFill: COLORS.orange },
);
addFigure("fig_innovation_4_counterfactual.png", "图 4-4 L0 反事实预演：实验前风险过滤与约束注入", "原申报书第四章 4.4；脚本 output/innovation_schematics/fig_innovation_4_counterfactual.png。 ");
addSource("代码依据：backend/app/skills/counterfactual/counterfactual_preview_skill.py 及 backend/prompts/counterfactual_preview.md。L0 是定性过滤层，不应表述为定量仿真或真实实验替代。 ");

addHeading(2, "4.5 两项配套机制：可执行性 Gate 与 Pairwise 假设选择");
addPara("实验计划可执行性 Gate 解决“文本上合理、数据上无法执行”的问题：系统从假设、方法和步骤中提取数据列、步骤、指标和阻塞项，与可用数据列进行精确与模糊匹配，并要求 score≥60、无 blockers、有 steps、有 metrics。Pairwise 锦标赛则对候选假设进行 O(n²) 全配对比较，以新颖性、可验证性、证据一致性和可行性四个维度进行 Margin-Weighted 评分。这两项机制不是本申报书的四项核心创新，但为四项创新提供了实验前筛选和候选排序支撑。", { style: "KeyParagraph" });
addSource("原申报书第四章 4.5、4.6；相关实现位于 backend/app/skills/experiment、reasoning 和 pipeline 服务模块。 ");

addHeading(1, "五、数据来源、案例与对照评估");
addHeading(2, "5.1 文献与数据来源");
addTable(
  ["来源", "使用方式", "在评估中的作用", "边界"],
  [
    ["arXiv", "关键词检索、PDF 下载与事实抽取", "验证多源文献到 fact_id/citation_map 的链路", "开放论文库，不代表所有领域覆盖"],
    ["HuggingFace Datasets", "检索元数据、导入样例行", "支持数据列匹配和实验计划可执行性检查", "样例行不等同于完整实验数据"],
    ["Zenodo / Figshare / Kaggle / OpenAlex / NCBI GEO", "元数据发现和数据集定位", "扩展数据来源和文献元数据", "部分接口依赖网络或公开权限"],
    ["用户上传", "PDF、CSV、TXT 文献和数据进入项目库", "验证私有资料与公共资料的统一治理", "数据质量由用户输入决定"],
    ["Science 125", "英中平行科学问题基准，项目已整理至 output/sjtu-125-questions", "验证跨学科问题理解、文献挖掘和假设生成流程", "本项目采用子集运行记录，不代表完整 125 题全量结果"],
    ["FL Starter Pack", "14 个数据集元数据、31 篇核心论文事实和领域标签", "验证联邦学习模式下的内容注入和仿真流程", "支持的是本地/可选后端仿真，不是多机构真实部署"],
  ],
  [1800, 2700, 2600, 1926],
  { bodySize: 16 },
);
addSource("原申报书第五章；backend/data/reference/fl、output/sjtu-125-questions 和 backend README。 ");

addHeading(2, "5.2 代表系统能力边界对照");
addPara("下表回答“别人怎样做、缺少什么、AISci 增加了什么”。勾选表示公开资料或系统实现中可观察到的能力，不表示统一数据集上的准确率比较。该表用于论证创新边界，性能结论以后续受控实验为准。");
addTable(
  ["系统/方法", "自动假设生成", "证据可追溯", "HITL 门控", "闭环自迭代", "对照说明"],
  [
    ["The AI Scientist（Sakana）", "有", "弱/未统一", "无", "有", "自动生成与实验闭环突出，但本项目关注的 Fact 白名单和阶段门禁不在其公开主线中。"],
    ["Deep Research 类系统", "有", "部分", "无", "弱", "检索与综合能力强，但通常不提供面向 Pipeline 的布尔 Gate 和指定阶段重跑。"],
    ["Elicit", "弱", "有", "无", "无", "文献检索与综述组织突出，不以自动假设生成和实验闭环为主。"],
    ["NotebookLM", "无/弱", "有", "有", "无", "支持基于资料的对话和人工校正，但不负责自动实验闭环。"],
    ["原有常规 Pipeline", "可有", "部分", "静态", "硬编码", "能串联模块，但反馈、证据和质量决策未必具有统一协议。"],
    ["AISci 当前版", "有", "Fact + provenance", "有", "有", "四项机制统一进入运行时：证据治理、Gate、Feedback Hub、L0 预演。"],
  ],
  [1900, 1200, 1400, 1200, 1200, 2126],
  { bodySize: 15 },
);
addSource("对照对象和能力维度沿用原申报书第三章 3.4、3.5；由于未取得统一实验环境和内部实现，表格不提供跨产品数值排名。 ");

addHeading(2, "5.3 指标化评估口径");
addPara("为避免把“评估指标”写成没有数据支撑的目标，本稿将指标分成三类：第一类是可以由当前结构化输出直接计算的运行指标；第二类是项目已经记录的规模和资源开销；第三类是需要补做匹配基线后才能得出提升率的对照指标。只有第一、第二类中的已有记录被写成当前结果，第三类保留为待补测项。");
addTable(
  ["指标类别", "指标", "数据来源", "当前可写结论"],
  [
    ["证据可靠性", "合法 fact 引用率、引用完整性 Gate、chain_completeness、citation_reliability", "EvidenceChain JSON、ReportQualityCheck JSON、审计链", "机制已实现；可逐运行计算；当前文档没有可信的外部基线百分比。"],
    ["质量决策", "Gate 覆盖率、PASS/FAIL 可复现率、停滞暂停触发率", "Gate result、quality_trend、closed_loop_decisions", "11 类 Gate 已配置，审计对象已固定；跨基线结果待补测。"],
    ["反馈闭环", "反馈注入完整率、目标命中率、指定阶段重跑成功率", "feedback_hub.json、rerun metadata、audit JSONL", "Feedback Hub 与路由已实现，可从日志汇总。"],
    ["实验风险", "有效场景保留率、高风险不可控阻断率、约束注入率", "Counterfactual preview JSON、experiment audit", "FALSIFY 判定和阻断逻辑已实现；场景级汇总待补测。"],
    ["系统开销", "端到端耗时、Token、阶段耗时、阶段记录数", "Science 125 子集运行记录", "已有 n=10 的具体记录，见 5.4。"],
  ],
  [1800, 2600, 2600, 2026],
  { bodySize: 16 },
);

addHeading(2, "5.4 当前项目运行记录与资源开销");
addPara("在 Science 125 基准子集 n=10 的已有运行记录中，端到端 Pipeline 平均耗时 167.5 s，最快 39.3 s，最慢 196.6 s；全链路 Token 消耗 4,033,770，平均每阶段约 5,030，最大单阶段 26,000，共记录 802 个阶段。该结果证明当前系统已经能够运行完整科研流程并留下阶段级数据，但它本身不等于相对于外部系统的性能提升。");
addTable(
  ["阶段", "平均耗时（s）", "最大耗时（s）", "记录样本数", "解释"],
  [
    ["LITERATURE_MINING", "402.5", "2160.6", "137", "文献召回、PDF 解析和事实提取主导时延。"],
    ["HYPOTHESIS_REVIEW", "260.2", "607.2", "131", "多维评审、Ensemble 和反事实预演增加调用。"],
    ["REPORT_GENERATION", "161.2", "362.2", "129", "报告聚合、引用核验和质量检查。"],
    ["HYPOTHESIS_GENERATION", "143.3", "7064.0", "132", "候选生成和锦标赛存在长尾调用。"],
    ["KNOWLEDGE_GAP", "79.1", "1046.8", "133", "知识缺口分析受检索上下文规模影响。"],
    ["PROBLEM_UNDERSTANDING", "34.2", "79.9", "139", "问题结构化相对稳定。"],
  ],
  [2200, 1500, 1500, 1300, 2526],
  { bodySize: 16 },
);
addSource("数据来源：原申报书第七章 7.5 的 Science 125 子集运行记录。原稿注明迭代实验阶段在沙箱内执行，未纳入上述端到端统计。 ");

addHeading(2, "5.5 三个代表性案例");
addTable(
  ["案例", "输入与过程", "输出与评价", "证据状态"],
  [
    ["Science 125 科学假设生成", "选取不同学科的 10 个典型问题，运行七阶段 Pipeline。", "检查新颖性、证据链迭代、报告完整性和引用关键问题；已有端到端开销记录。", "实测运行记录；质量提升需补充逐题明细。"],
    ["评分表系统影响力评估", "3 个生成器在 FL 与 PEFT 两个领域完成 6 组测试。", "原稿记录 6 组均生成 task.json 与 rubric_scores.json，总分 88–118，评分维度 41–56。", "项目记录的功能验证；不是外部产品对照。"],
    ["联邦学习仿真", "Non-IID 范式，Dirichlet α=0.1，FedAvg/FedProx，支持 local_pack、Flower、FedML 可选后端。", "验证 FL Starter Pack 内容注入、实验脚本设计和仿真链路。", "仿真验证；不是多机构真实联邦部署。"],
  ],
  [1900, 2600, 2800, 1726],
  { bodySize: 16 },
);

addHeading(2, "5.6 结果表述边界");
addTable(
  ["可以明确表述", "不能在当前材料中直接表述", "补强方式"],
  [
    ["系统已实现四项机制、七阶段 Pipeline、审计链、HITL、指定阶段重跑和 L0 过滤。", "不能直接写成“比所有现有系统准确率高”“首次实现”或“提升 X%”。", "使用统一问题集、同模型、同提示词和同人工评审标准，增加受控基线。"],
    ["已有 n=10 运行记录和具体耗时、Token、阶段样本数。", "不能把运行规模等同于假设质量提升或科学发现能力。", "补充人工盲评、引用合法性逐条统计、任务完成率和失败类型。"],
    ["11 类 Gate、5 类基础反馈来源、最大 50 条约束、结构化审计字段已在实现中出现。", "不能把配置数量等同于决策有效性。", "对每类 Gate 统计误放行、误阻断和人工修订结果。"],
    ["FL Starter Pack 支持本地/可选后端仿真。", "不能表述为真实多机构联邦学习部署或真实隐私安全证明。", "补充多客户端、通信轮次、收敛指标和隐私攻击实验。"],
  ],
  [3100, 3100, 2826],
  { bodySize: 16, headerFill: COLORS.orange },
);

addHeading(1, "六、应用示范：科学影响力预测系统");
addHeading(2, "6.1 设计动机与能力边界");
addPara("科学影响力预测是 AISci 的延伸应用，不替代四项核心创新。它用于说明主 Pipeline 生成报告后，还可以对论文文本质量、引用网络、生命周期和偏差风险进行结构化分析。系统通过 OpenAlex 元数据、引用网络特征、PDF 文本特征和早期生命周期预测形成四维评估，并输出预测区间、偏差方向和可信度等级。");
addTable(
  ["维度", "内容", "约束"],
  [
    ["D1 文本质量", "方法严谨性、创新性、写作清晰度、数据透明度和跨领域潜力。", "权重 60%，避免高引用掩盖文本质量。"],
    ["D2 声誉与网络", "期刊、作者、机构、当前引用数和领域百分位等外部信号。", "权重 40%，避免完全依赖声誉。"],
    ["D3 未来影响", "1/3/5 年引用投影、高影响概率和增长轨迹。", "对早期论文采用保守策略并展示不确定性。"],
    ["D4 偏差与公平", "期刊、作者、领域热度、时间、语言地域和方法论偏差。", "标注偏差方向、量级和缓解措施。"],
  ],
  [1700, 4600, 2726],
  { bodySize: 16 },
);
addHeading(2, "6.2 与主系统的连接");
addPara("主 Pipeline 完成报告生成后，用户可以通过 pingfenbiao_proxy API 提交 DOI、标题或 PDF。前端 ImpactDetailView 展示四维评分、引用预测曲线、偏差分析和综合评级；JobStatusPanel 跟踪长耗时任务。该应用示范复用 Qwen 运行时，但其预测结果属于高不确定性分析，必须附带置信度和风险提示，不能写成确定性影响力结论。");
addSource("原申报书第八章及附录二。应用示范属于 AISci 的扩展能力，本文不把它作为四项核心创新的直接实验证据。 ");

addHeading(1, "七、源代码、可复现性与项目基础");
addHeading(2, "7.1 项目结构");
addTable(
  ["目录/组件", "主要内容", "与申报书的关系"],
  [
    ["backend/app/agents", "ProblemUnderstanding、LiteratureMining、KnowledgeGap、HypothesisGeneration、HypothesisReview、ReportGeneration", "实现七阶段中的核心 Agent 编排。"],
    ["backend/app/skills", "文献、证据、数据、推理、反事实、实验和报告质量 Skill", "承载四项创新的可复用模块。"],
    ["backend/app/core 与 services", "质量评分、闭环控制、溯源、反馈、科学迭代、实验服务", "实现 Gate、反馈路由和审计。"],
    ["backend/prompts", "阶段 Prompt、Counterfactual Prompt、预设范式", "固定模型输入约束和版本。"],
    ["frontend", "Pipeline、证据链、质量检查、HITL、迭代实验和影响力页面", "提供可视化操作和反馈入口。"],
    ["storage/audit", "run_id 对应的 JSONL 审计链", "支持过程复现和第三方核查。"],
  ],
  [2400, 3900, 2726],
  { bodySize: 16 },
);
addHeading(2, "7.2 环境与启动");
addPara("后端要求 Python 3.10+，前端要求 Node.js 18+。系统提供 setup_backend、setup_frontend 和 run_dev 脚本；后端通过 FastAPI 提供服务，前端基于 React 18、Vite 5 和 TailwindCSS 3。Qwen 通过 DashScope 兼容模式调用，测试可使用 USE_MOCK_LLM 关闭真实模型消耗。具体启动方式保留在项目 README 和 scripts 目录中。");
addHeading(2, "7.3 测试与复现边界");
addPara("项目测试目录覆盖健康检查、文档解析、向量检索、Agent、Pipeline、证据推理、HITL、闭环质量、Feedback Hub、溯源审计、反事实预演和 FL Starter Pack 等模块。原项目文档将回归测试按 Batch 1–7 组织。本文将其作为代码层验证依据，但不把“测试文件存在”直接等同于“所有测试均通过”；正式提交前应附上一次固定版本、固定环境的 pytest 输出和失败项说明。");
addSource("依据：backend/tests/README.md、backend/README.md、原申报书第九章。当前环境未安装 pytest，因此本次文档生成未重新执行测试套件。 ");

addHeading(1, "八、总结与展望");
addPara("联邦智研（AISci）针对科研自动化中“生成快但难核验、评分有但难决策、反馈有但难回流、实验能设计但风险发现过晚”的问题，构建了以 Qwen 为底座的多智能体科研自动化系统。项目的核心创新可以归结为四个互补的运行时约束：Fact 白名单保证证据引用合法，Verdict Gate 保证质量决策可执行，Feedback Hub + HITL 保证反馈可路由，L0 反事实预演保证实验前风险可筛查。");
addPara("现有项目运行记录已经证明系统具备完整 Pipeline、阶段审计和资源统计能力；能力边界对照也说明 AISci 的差异不在于单独拥有“检索、生成、人工审核或迭代”某一功能，而在于将四者统一到同一套数据对象、门禁和反馈协议中。下一步应优先补齐四类受控对照：无 Fact 白名单与有 Fact 白名单的引用合法性对照；连续评分与 Verdict Gate 的误放行/误阻断对照；硬编码传递与 Feedback Hub 的反馈命中率对照；无 L0 与有 L0 的高风险实验阻断和人工复核成本对照。");
addPara("后续工作包括：扩展跨学科基准和真实领域专家评审；将 L0 定性预演升级为 L1 定量仿真；记录更多真实实验反馈；完善多客户端联邦学习的通信、收敛和隐私评估；在固定版本下公开审计链、指标脚本和失败案例，使项目创新从机制描述进一步落实为可重复的对照证据。", { style: "KeyParagraph" });

addHeading(1, "附录 A 机制图与证据索引");
addTable(
  ["图号", "图名", "对应创新", "文件"],
  [
    ["图 4-1", "证据链迭代推理引擎", "Fact 白名单、支持/反证、证据链收敛", "fig_innovation_1_evidence_chain.png/.svg"],
    ["图 4-2", "Verdict Gate", "阶段质量判定、通信与人工放行", "fig_innovation_2_verdict_gate.png/.svg"],
    ["图 4-3", "Feedback Hub + HITL", "跨阶段反馈传输与重跑", "fig_innovation_3_feedback_hub.png/.svg"],
    ["图 4-4", "L0 反事实预演", "实验前风险过滤与约束注入", "fig_innovation_4_counterfactual.png/.svg"],
  ],
  [1200, 2600, 3000, 2226],
  { bodySize: 16 },
);

addHeading(1, "附录 B 关键主张与证据追踪表");
addTable(
  ["主张", "证据位置", "证据类型", "可信度/边界"],
  [
    ["AISci 采用七阶段科研 Pipeline", "原申报书 2.2、3.1；backend README", "架构说明、代码目录、API", "高；属于系统实现事实"],
    ["Evidence Chain 使用支持与反证并保存完备度", "原申报书 4.1；EvidenceChainBuilderSkill", "方法说明、代码字段", "高；不等于外部基线提升"],
    ["系统配置 11 类 Verdict Gate", "原申报书 4.2、7.1；quality scoring/closed loop", "配置与审计结构", "高；需要补充实际触发分布"],
    ["Feedback Hub 支持约束持久化与目标阶段重跑", "原申报书 4.3；feedback_hub_service、pipeline API", "代码与接口", "高；效果需从运行日志统计"],
    ["L0 FALSIFY 可过滤高风险不可控场景", "原申报书 4.4；counterfactual_preview_skill", "过滤逻辑与阻断条件", "高；尚无大规模场景结果"],
    ["Science 125 子集 n=10 平均耗时 167.5 s", "原申报书 7.5", "项目运行记录", "中高；需附原始日志以便复核"],
    ["AISci 优于所有现有科研智能体", "不作此主张", "无统一受控基线", "不成立；正式实验后再判断"],
  ],
  [2500, 2700, 1700, 2126],
  { bodySize: 16, headerFill: COLORS.purple },
);

const doc = new Document({
  creator: "AISci project",
  title: "联邦智研（AISci）大学生创新创业大赛申报书（修改稿）",
  description: "基于原申报书、项目代码和已有运行记录重组的修改稿",
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21, color: COLORS.text } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 36, bold: true, color: COLORS.navy }, paragraph: { alignment: AlignmentType.CENTER, spacing: { after: 200 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Microsoft YaHei", size: 31, bold: true, color: COLORS.navy }, paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Microsoft YaHei", size: 27, bold: true, color: COLORS.text }, paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Microsoft YaHei", size: 23, bold: true, color: COLORS.text }, paragraph: { spacing: { before: 150, after: 100 }, outlineLevel: 2 } },
      { id: "CoverTitle", name: "Cover Title", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 42, bold: true, color: COLORS.navy }, paragraph: { alignment: AlignmentType.CENTER } },
      { id: "CoverSubtitle", name: "Cover Subtitle", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 25, color: COLORS.muted }, paragraph: { alignment: AlignmentType.CENTER } },
      { id: "CoverDocTitle", name: "Cover Document Title", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 32, bold: true }, paragraph: { alignment: AlignmentType.CENTER } },
      { id: "CoverNote", name: "Cover Note", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 18, color: COLORS.muted }, paragraph: { alignment: AlignmentType.CENTER } },
      { id: "TOCTitle", name: "TOC Title", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 30, bold: true, color: COLORS.navy }, paragraph: { alignment: AlignmentType.CENTER } },
      { id: "SourceNote", name: "Source Note", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 17, italics: true, color: COLORS.muted }, paragraph: { indent: { left: 360, right: 360 }, spacing: { after: 130 } } },
      { id: "KeyParagraph", name: "Key Paragraph", basedOn: "Normal", run: { font: "Microsoft YaHei", size: 22, bold: true, color: COLORS.navy }, paragraph: { indent: { firstLine: 480 }, spacing: { after: 150, line: 380, lineRule: "auto" } } },
      { id: "FormulaParagraph", name: "Formula Paragraph", basedOn: "Normal", run: { font: "Consolas", size: 20, color: COLORS.text }, paragraph: { indent: { left: 480, right: 480 }, shading: { fill: COLORS.gray, type: ShadingType.CLEAR }, spacing: { before: 100, after: 150, line: 340, lineRule: "auto" } } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullet-list", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "number-list", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        pageNumbers: { start: 1, formatType: "decimal" },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 0 }, children: [run("联邦智研（AISci）申报书修改稿", { size: 16, color: COLORS.muted })] })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0 }, children: [run("第 ", { size: 16, color: COLORS.muted }), new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 16, color: COLORS.muted }), run(" 页", { size: 16, color: COLORS.muted })] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUTPUT, buffer);
  console.log(`Wrote ${OUTPUT}`);
});
