const fs = require("fs");
const path = require("path");
const JSZip = require("C:/Users/lly18/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/jszip");

const source = "D:/Workplace/AISci/output/联邦智研.docx";
const target = "D:/Workplace/AISci/output/联邦智研_原稿定点修订版.docx";

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function decodeXml(value) {
  return value
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#([0-9]+);/g, (_, decimal) => String.fromCodePoint(parseInt(decimal, 10)))
    .replace(/&quot;/g, "\"")
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function paragraphText(paragraph) {
  return Array.from(paragraph.matchAll(/<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>/g))
    .map((match) => decodeXml(match[1]))
    .join("");
}

function pPrOf(paragraph) {
  return (paragraph.match(/<w:pPr>[\s\S]*?<\/w:pPr>/) || [""])[0];
}

function run(text, { bold = false, size = null, color = "000000" } = {}) {
  const preserve = /^\s|\s$/.test(text) ? ' xml:space="preserve"' : "";
  const sizeXml = size ? `<w:sz w:val="${size}"/><w:szCs w:val="${size}"/>` : "";
  const boldXml = bold ? "<w:b/>" : "";
  return `<w:r><w:rPr><w:rFonts w:hint="eastAsia"/>${boldXml}<w:color w:val="${color}"/>${sizeXml}<w:lang w:eastAsia="zh-CN"/></w:rPr><w:t${preserve}>${escapeXml(text)}</w:t></w:r>`;
}

function paragraphFrom(existing, runs, { retainStart = false, center = false, compact = false } = {}) {
  const existingStart = (existing.match(/^<w:p(?:\s[^>]*)?>/) || ["<w:p>"])[0];
  const start = retainStart ? existingStart : "<w:p>";
  let pPr = pPrOf(existing);
  if (center) {
    pPr = "<w:pPr><w:jc w:val=\"center\"/></w:pPr>";
  }
  if (compact) {
    pPr = "<w:pPr><w:spacing w:after=\"0\" w:line=\"260\" w:lineRule=\"auto\"/></w:pPr>";
  }
  return `${start}${pPr}${runs.map((item) => run(item.text, item)).join("")}</w:p>`;
}

function replaceParagraph(xml, expectedText, build) {
  let replaced = false;
  const result = xml.replace(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g, (paragraph) => {
    if (!replaced && paragraphText(paragraph) === expectedText) {
      replaced = true;
      return build(paragraph);
    }
    return paragraph;
  });
  if (!replaced) {
    throw new Error(`Unable to locate paragraph: ${expectedText.slice(0, 36)}`);
  }
  return result;
}

function insertAfterParagraph(xml, expectedText, fragment) {
  let inserted = false;
  const result = xml.replace(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g, (paragraph) => {
    if (!inserted && paragraphText(paragraph) === expectedText) {
      inserted = true;
      return `${paragraph}${fragment}`;
    }
    return paragraph;
  });
  if (!inserted) {
    throw new Error(`Unable to locate insertion point: ${expectedText.slice(0, 36)}`);
  }
  return result;
}

function tableCell(text, width, header) {
  const shading = header ? '<w:shd w:val="clear" w:fill="D9EAF7"/>' : "";
  const alignment = header ? '<w:jc w:val="center"/>' : "";
  return `<w:tc><w:tcPr><w:tcW w:w="${width}" w:type="dxa"/>${shading}<w:tcMar><w:top w:w="70" w:type="dxa"/><w:left w:w="85" w:type="dxa"/><w:bottom w:w="70" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tcMar></w:tcPr><w:p><w:pPr>${alignment}<w:spacing w:after="0" w:line="250" w:lineRule="auto"/></w:pPr>${run(text, { bold: header, size: 17 })}</w:p></w:tc>`;
}

function comparisonTable() {
  const widths = [1450, 2450, 2850, 2250];
  const rows = [
    ["评价维度", "现有/原有做法及不足", "AISci 机制与已有核查证据", "本项目可成立的结论"],
    ["声明级证据追溯与引用控制", "检索增强或文献助手通常给出来源或摘要，但难保证每一科学主张与有效事实一一绑定，也较少主动补充反证。", "Fact 白名单校验 cited_fact_ids，并进行支持/反对证据双向检索；第 6.1 节以 References 无虚构引用、证据链至少迭代 1 轮作为验收口径。", "实现“事实—主张—修订”可审计链；尚无同任务的虚构引用率对比，不报告比例提升。"],
    ["质量是否直接驱动流程", "常见连续评分或静态评审可描述质量状态，但评分与继续、停机、人工介入的程序决策关联较弱。", "11 种 Verdict Gate 输出 PASS/FAIL；summarize_gate_trend 记录连续失败与改善趋势，并可触发 HITL 暂停。", "将质量判断转化为可执行、可追溯的流程边界；此为机制能力对照，不等同于单一质量分数领先。"],
    ["跨阶段反馈与人工可控", "多智能体通常采用预定义阶段传递；HITL 往往停留在单点审批，反馈难精确影响后续重跑。", "5 类反馈统一为 global_constraints（最多 50 条），经目标映射和 RERUN_TARGETS 触发相应阶段；审计链记录反馈来源。", "反馈可成为下一轮输入与重跑依据，形成可审计的人机闭环；未以人工工时缩短百分比作结论。"],
    ["实验前失败风险控制", "常在实验设计或执行后才发现不可证伪、无决策价值的路径，资源保护缺少前置环节。", "FALSIFY 过滤可证伪性、有效事实、廉价测试和决策影响；高风险且无失败模式时阻断实验。", "将风险控制前移至“假设—实验”之间；尚未声明跨项目节约成本的统一统计结果。"],
  ];
  const border = '<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>';
  const grid = widths.map((width) => `<w:gridCol w:w="${width}"/>`).join("");
  const body = rows.map((row, rowIndex) => `<w:tr>${row.map((cell, columnIndex) => tableCell(cell, widths[columnIndex], rowIndex === 0)).join("")}</w:tr>`).join("");
  return `<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>${border}</w:tblBorders></w:tblPr><w:tblGrid>${grid}</w:tblGrid>${body}</w:tbl>`;
}

async function main() {
  const sourceBuffer = fs.readFileSync(source);
  const zip = await JSZip.loadAsync(sourceBuffer);
  const documentFile = zip.file("word/document.xml");
  if (!documentFile) throw new Error("word/document.xml not found");
  let xml = await documentFile.async("string");

  const abstract = "系统的技术内核是四项方法创新：① 多轮证据链迭代推理引擎（以 Fact 白名单从机制上杜绝幻觉引用）；② 判定式质量门禁（Verdict Gate，以 0/1 硬门禁替代连续评分，作为可审计质量闸）；③ 统一反馈中心 + 人在回路（HITL）的协同闭环；④ 反事实预演机制（L0 定性证伪，保护科研资源）。围绕这四项创新，系统构建了 6 个智能体、约 70 个可复用技能与 11 种阶段特定质量门禁，并在第七章给出结果展示与反馈迭代的完整量化。";
  xml = replaceParagraph(xml, abstract, (p) => paragraphFrom(p, [{
    text: "系统的技术内核是四项方法创新：① 多轮证据链迭代推理引擎（以 Fact 白名单从机制上约束幻觉引用）；② 判定式质量门禁（Verdict Gate，以 0/1 硬门禁替代连续评分，作为可审计质量闸）；③ 统一反馈中心 + 人在回路（HITL）的协同闭环；④ 反事实预演机制（L0 定性证伪，保护科研资源）。围绕这四项创新，系统构建了 6 个智能体、约 70 个可复用技能与 11 种阶段特定质量门禁。第七章将“机制对照”和“运行实测”分开陈述：前者说明与现有系统在证据治理、流程控制和风险前置上的差异，后者仅报告已完成的运行记录，避免将尚未完成同条件基线实验的内容表述为性能提升。"
  }]));

  const innovations = [
    {
      original: "创新一　多轮证据链迭代推理引擎（EvidenceChainBuilder）：构建“科学声明 ↔ 文献事实”的双向溯源与矛盾检测，以 Fact 白名单强制约束从机制层面杜绝幻觉引用，使每一条假设都可追溯、可证伪。",
      title: "创新一　多轮证据链迭代推理引擎（EvidenceChainBuilder）：",
      body: "现有检索增强或文献助手主要解决“找得到资料”，但通常难约束每一科学声明与有效事实的一一对应，也较少主动补充反证。本项目构建“科学声明 ↔ 文献事实”的双向溯源与矛盾检测，并以 Fact 白名单校验引用。评价时可核查 cited_fact_ids 的合法性、支持/反对证据与修订历史，以及最终 References 是否出现 critical issue，从而呈现由检索级溯源向声明级可证伪的机制提升。"
    },
    {
      original: "创新二　判定式质量门禁系统（Verdict Gate）：以 0/1 硬门禁替代常见的 0–100 连续评分，作为可审计的质量闸，在科研自动化评测中较为少见，构成方法层面的创新。",
      title: "创新二　判定式质量门禁系统（Verdict Gate）：",
      body: "现有系统多以连续分数或静态评审呈现质量状态，但评分本身未必驱动“继续、重跑、暂停或人工介入”的流程决策。本项目以 0/1 硬门禁替代连续评分，并为 11 类阶段特定 Gate 记录 PASS/FAIL 与趋势。评价时以门禁状态、连续失败次数、触发的 HITL 暂停和审计记录为依据，说明质量判断如何转化为可执行、可复核的决策边界。"
    },
    {
      original: "创新三　统一反馈中心 + 人在回路（Feedback Hub + HITL）：将某一阶段的发现经统一反馈中心传递给后续阶段，并在关键节点设置人工门控，实现“人机协同的闭环”，在自动化与可控性之间取得平衡。",
      title: "创新三　统一反馈中心 + 人在回路（Feedback Hub + HITL）：",
      body: "多智能体流程常采用预定义的阶段间传递，HITL 也常停留在单点审批，反馈难精确影响后续重跑。本项目将阶段发现和人工意见汇入统一反馈中心，转化为可注入的约束，并在关键节点设置人工门控。评价时可核查反馈来源、约束注入、目标阶段映射和重跑记录，说明系统形成了“反馈—约束—重跑—复核”的人机协同闭环。"
    },
    {
      original: "创新四　反事实预演机制（Counterfactual Preview）：在假设评审与实验设计之间插入 L0 级定性证伪层，过滤不可证伪或缺乏决策影响的场景，阻断无价值实验，保护科研资源。",
      title: "创新四　反事实预演机制（Counterfactual Preview）：",
      body: "常见假设生成流程往往在实验设计甚至执行后才暴露不可证伪或缺乏决策价值的风险。本项目在假设评审与实验设计之间插入 L0 级定性证伪层，过滤不可证伪、无有效事实支撑或无廉价测试方案的场景；对高风险且无法给出失败模式的路径阻断实验。评价时以 FALSIFY 过滤结果、failure_predictions 和是否允许进入实验阶段为证据，展示风险控制被前移到资源投入之前。"
    }
  ];
  for (const item of innovations) {
    xml = replaceParagraph(xml, item.original, (p) => paragraphFrom(p, [
      { text: item.title, bold: true },
      { text: item.body }
    ], { retainStart: true }));
  }

  const comparisonLead = "为明确本项目的创新边界，下表系统对比了当前具有代表性的科研智能体/系统在四项关键能力上的差异：自动假设生成（能否自主提出可验证科学假设）、证据可追溯（每条结论能否回溯到真实文献事实）、人在回路 HITL（是否有人工审核/门控节点）、闭环自迭代（能否基于反馈自动修正并循环优化）。图例：✓ 具备，△ 部分/检索级，✗ 无。";
  xml = insertAfterParagraph(xml, comparisonLead,
    paragraphFrom("<w:p><w:pPr><w:spacing w:after=\"60\"/><w:ind w:firstLine=\"425\"/><w:jc w:val=\"both\"/></w:pPr></w:p>", [{
      text: "评价边界说明：本表比较的是公开可见的功能机制与可审计能力，不等同于在统一任务、模型、提示词和成本条件下的性能排名；对外部系统的判断以公开资料可核查的功能为限。"
    }])
  );

  const comparisonConclusion = "由上表可见，现有系统均只在局部能力上取得进展：The AI Scientist（Sakana）能自动生成假设与实验，但缺乏证据溯源与人工门控，易产生\"幻觉假设\"；Deep Research 依赖检索增强，证据可追溯性仅部分成立且同样无闭环；Elicit、NotebookLM 长于文献理解与溯源，但不具备自动假设生成与自迭代闭环。相较之下，据公开资料，本项目是首个将上述四项能力统一于一体的科研自动化系统，其创新性具体体现在三处差异化设计：";
  xml = replaceParagraph(xml, comparisonConclusion, (p) => paragraphFrom(p, [{
    text: "由上表可见，现有系统通常把能力集中在科研流程的某一环节：The AI Scientist（Sakana）强调自动生成假设与实验，Deep Research 强调检索增强，Elicit 和 NotebookLM 强调文献理解与来源追溯。本项目的创新不在于简单并列四项功能，而在于以“证据约束 → 门禁决策 → 反馈重跑 → 反事实阻断”将检索、生成、审核和实验前风险控制串联为可审计链路。以下差异化设计与第 7.3 节的对照评价共同构成创新论证。"
  }], { retainStart: true }));

  const priorSummary = "综上，本项目并非单纯工程封装，而是在\"可追溯假设生成 + 判定式质量门禁（Verdict Gate） + 人机协同闭环\"上的方法组合创新，填补了现有科研智能体在证据治理与闭环可控性上的空白（详见第 3.4 节统一对比表）。";
  xml = replaceParagraph(xml, priorSummary, (p) => paragraphFrom(p, [{
    text: "综上，本项目在“可追溯假设生成 + 判定式质量门禁 + 人机协同闭环 + 反事实预演”上形成了可实现、可审计的方法组合差异化。上述结论用于描述功能机制与证据治理路径的差异，不外推为未在统一任务、模型和成本条件下验证的绝对性能排名。"
  }], { retainStart: true }));

  const acceptance = "预期验证指标：假设新颖性评分≥6.0（gate_novelty通过标准）；证据链至少1轮迭代（gate_evidence通过标准）；报告中References字段无虚构引用（quality_check.critical_issues为空）。";
  xml = replaceParagraph(xml, acceptance, (p) => paragraphFrom(p, [{
    text: "本项目验收口径（用于系统自检，不等同于外部对照结论）：假设新颖性评分≥6.0（gate_novelty 通过标准）；证据链至少 1 轮迭代（gate_evidence 通过标准）；报告中 References 字段无虚构引用（quality_check.critical_issues 为空）。"
  }], { retainStart: true }));

  const auditExport = "（3）审计链导出：完整审计链（quality_trend/events/decisions）支持jsonl格式导出，便于第三方审查和复现验证。";
  const section73 = "7.3 迭代优化效果量化";
  const sectionHeading = xml.match(new RegExp(`<w:p(?:\\s[^>]*)?>[\\s\\S]*?<\\/w:p>`, "g"))
    .find((p) => paragraphText(p) === section73);
  const bodyTemplate = xml.match(new RegExp(`<w:p(?:\\s[^>]*)?>[\\s\\S]*?<\\/w:p>`, "g"))
    .find((p) => paragraphText(p) === "系统的迭代优化通过以下机制量化展示：");
  if (!sectionHeading || !bodyTemplate) throw new Error("Unable to find section 7.3 styles");
  const supplement = [
    paragraphFrom(sectionHeading, [{ text: "7.3.1 四项创新的对照评价" }]),
    paragraphFrom(bodyTemplate, [{
      text: "为避免将“机制设计”与“统一基线下的性能提升”混同，本节按两层证据评价四项创新：第一层核查系统是否实现了相应的输入、约束、决策和审计链；第二层仅引用本项目已有的运行记录与验收口径。表 7-1 据此比较现有/原有做法与 AISci，不对尚未完成同条件实验的指标编造提升数值。"
    }]),
    comparisonTable(),
    paragraphFrom(bodyTemplate, [{
      text: "表 7-1 的结论表明，本项目的可验证创新集中在科研自动化的“证据治理、流程控制、反馈闭环和风险前置”四个连接环节；第 7.5 节报告的 Science 125 子集端到端耗时与 Token 开销，是当前可复核的运行实测，不应与外部系统直接作未经控制条件的横向性能比较。"
    }])
  ].join("");
  xml = insertAfterParagraph(xml, auditExport, supplement);

  zip.file("word/document.xml", xml);
  const settingsFile = zip.file("word/settings.xml");
  if (settingsFile) {
    let settingsXml = await settingsFile.async("string");
    if (!settingsXml.includes("<w:updateFields")) {
      settingsXml = settingsXml.replace("</w:settings>", '<w:updateFields w:val="true"/></w:settings>');
      zip.file("word/settings.xml", settingsXml);
    }
  }
  const output = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE", compressionOptions: { level: 6 } });
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, output);
  console.log(target);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
