const fs = require("fs");
const path = require("path");
const JSZip = require("C:/Users/lly18/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/jszip");

const input = "D:/Workplace/AISci/output/联邦智研_原稿定点修订版.docx";
const output = "D:/Workplace/AISci/output/联邦智研_原稿定点修订版_含示意图.docx";
const schematicDir = "D:/Workplace/AISci/output/innovation_schematics";

const figures = [
  {
    source: "fig_innovation_1_evidence_chain.png",
    media: "innovation_fig_1_evidence_chain.png",
    relId: "rId14",
    docPrId: 51,
    caption: "图A-1：证据链迭代推理引擎：运行机制与数据传输",
    title: "Evidence chain iteration engine",
    description: "Fact 白名单、支持与反证检索、假设修订及证据链构建的运行机制与数据传输示意图"
  },
  {
    source: "fig_innovation_2_verdict_gate.png",
    media: "innovation_fig_2_verdict_gate.png",
    relId: "rId15",
    docPrId: 52,
    caption: "图A-2：Verdict Gate：阶段质量判定、通信与人工放行机制",
    title: "Verdict Gate quality decision",
    description: "阶段输出、规则归一化、11 类质量门禁、PASS/FAIL 通信和 HITL 重跑机制示意图"
  },
  {
    source: "fig_innovation_3_feedback_hub.png",
    media: "innovation_fig_3_feedback_hub.png",
    relId: "rId16",
    docPrId: 53,
    caption: "图A-3：Feedback Hub + HITL：跨阶段反馈传输与重跑机制",
    title: "Feedback Hub and HITL",
    description: "反馈来源、反馈中心、全局约束、后续 Prompt 上下文和目标阶段重跑的传输示意图"
  },
  {
    source: "fig_innovation_4_counterfactual.png",
    media: "innovation_fig_4_counterfactual.png",
    relId: "rId17",
    docPrId: 54,
    caption: "图A-4：L0 反事实预演：实验前风险过滤与约束注入机制",
    title: "Counterfactual preview",
    description: "反事实场景生成、FALSIFY 过滤、可控性判定、实验阻断或约束注入示意图"
  }
];

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function paragraphText(paragraph) {
  return Array.from(paragraph.matchAll(/<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>/g))
    .map((match) => match[1]
      .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
      .replace(/&#([0-9]+);/g, (_, decimal) => String.fromCodePoint(parseInt(decimal, 10)))
      .replace(/&quot;/g, "\"")
      .replace(/&apos;/g, "'")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&"))
    .join("");
}

function findParagraph(xml, expectedText) {
  const paragraphs = xml.match(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g) || [];
  const found = paragraphs.find((paragraph) => paragraphText(paragraph) === expectedText);
  if (!found) throw new Error(`Unable to locate paragraph: ${expectedText}`);
  return found;
}

function pPrOf(paragraph) {
  return (paragraph.match(/<w:pPr>[\s\S]*?<\/w:pPr>/) || ["<w:pPr/>"])[0];
}

function withPageBreak(pPr) {
  if (pPr.includes("<w:pageBreakBefore")) return pPr;
  const style = pPr.match(/<w:pStyle\b[^>]*\/>/);
  if (style) return pPr.replace(style[0], `${style[0]}<w:pageBreakBefore/>`);
  return pPr.replace("<w:pPr>", "<w:pPr><w:pageBreakBefore/>");
}

function textRun(text, { bold = false, size = 22 } = {}) {
  const boldXml = bold ? "<w:b/>" : "";
  const preserve = /^\s|\s$/.test(text) ? ' xml:space="preserve"' : "";
  return `<w:r><w:rPr><w:rFonts w:hint="eastAsia"/>${boldXml}<w:sz w:val="${size}"/><w:szCs w:val="${size}"/><w:lang w:eastAsia="zh-CN"/></w:rPr><w:t${preserve}>${escapeXml(text)}</w:t></w:r>`;
}

function simpleParagraph(text, pPr, { bold = false, pageBreak = false } = {}) {
  const effectivePPr = pageBreak ? withPageBreak(pPr) : pPr;
  return `<w:p>${effectivePPr}${textRun(text, { bold })}</w:p>`;
}

function drawingParagraph(figure) {
  const cx = 5486400;
  const cy = 3430000;
  const safeName = escapeXml(figure.title);
  const safeDescription = escapeXml(figure.description);
  const drawing = `<w:drawing xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="${figure.docPrId}" name="${safeName}" descr="${safeDescription}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="${safeName}"/><pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr><pic:blipFill><a:blip r:embed="${figure.relId}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>`;
  return `<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="120"/></w:pPr><w:r><w:rPr><w:noProof/></w:rPr>${drawing}</w:r></w:p>`;
}

function replaceParagraph(xml, expectedText, replacement) {
  let replaced = false;
  const result = xml.replace(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g, (paragraph) => {
    if (!replaced && paragraphText(paragraph) === expectedText) {
      replaced = true;
      return replacement;
    }
    return paragraph;
  });
  if (!replaced) throw new Error(`Unable to replace paragraph: ${expectedText}`);
  return result;
}

function insertBeforeParagraph(xml, expectedText, fragment) {
  let inserted = false;
  const result = xml.replace(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g, (paragraph) => {
    if (!inserted && paragraphText(paragraph) === expectedText) {
      inserted = true;
      return `${fragment}${paragraph}`;
    }
    return paragraph;
  });
  if (!inserted) throw new Error(`Unable to insert before paragraph: ${expectedText}`);
  return result;
}

async function main() {
  const zip = await JSZip.loadAsync(fs.readFileSync(input));
  let documentXml = await zip.file("word/document.xml").async("string");
  let relationshipsXml = await zip.file("word/_rels/document.xml.rels").async("string");

  const oldReference = "证据链迭代推理引擎的流程如图 4-1 所示，详细流程图见附录。";
  const referenceParagraph = findParagraph(documentXml, oldReference);
  documentXml = replaceParagraph(documentXml, oldReference, simpleParagraph(
    "证据链迭代推理引擎的流程如图 4-1 所示，详细流程图见附录；四项核心创新的运行机制、数据传输和通信约束见附录一（续）图 A-1 至图 A-4。",
    pPrOf(referenceParagraph)
  ));

  const appendixTwo = "附录二：科学影响力预测系统技术细节";
  const appendixHeading = findParagraph(documentXml, appendixTwo);
  const captionTemplate = findParagraph(documentXml, "图4-1：证据链迭代推理引擎流程图");
  const headingPPr = pPrOf(appendixHeading);
  const captionPPr = pPrOf(captionTemplate);
  const section = [];
  section.push(simpleParagraph("附录一（续）：核心创新机制示意图", headingPPr, { bold: true, pageBreak: true }));
  figures.forEach((figure, index) => {
    section.push(simpleParagraph(figure.caption, captionPPr, { bold: true, pageBreak: index > 0 }));
    section.push(drawingParagraph(figure));
  });

  documentXml = insertBeforeParagraph(documentXml, appendixTwo, section.join(""));

  figures.forEach((figure) => {
    const imagePath = path.join(schematicDir, figure.source);
    if (!fs.existsSync(imagePath)) throw new Error(`Missing schematic: ${imagePath}`);
    zip.file(`word/media/${figure.media}`, fs.readFileSync(imagePath));
    const relationship = `<Relationship Id="${figure.relId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${figure.media}"/>`;
    relationshipsXml = relationshipsXml.replace("</Relationships>", `${relationship}</Relationships>`);
  });

  zip.file("word/document.xml", documentXml);
  zip.file("word/_rels/document.xml.rels", relationshipsXml);
  const outputBuffer = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE", compressionOptions: { level: 6 } });
  fs.writeFileSync(output, outputBuffer);
  console.log(output);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
