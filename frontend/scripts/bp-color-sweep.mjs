import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const componentsDir = path.join(__dirname, '../src/components');

const files = [
  'AgentNode.tsx',
  'QualityCheckCard.tsx',
  'FederatedCampaignPanel.tsx',
  'ClosedLoopTimeline.tsx',
  'AgentDetailPanel.tsx',
  'EvidenceChainQualityCard.tsx',
  'EvidenceDiffPanel.tsx',
  'FederatedPareto3DPanel.tsx',
  'ExternalCandidateTodoPanel.tsx',
  'HypothesisProvenanceTimeline.tsx',
  'VersionComparePanel.tsx',
  'HitlGatePanel.tsx',
  'HumanInLoopCard.tsx',
  'ReportChecklist.tsx',
  'MarkdownPreview.tsx',
  'HypothesisCard.tsx',
  'EnsembleReviewPanel.tsx',
  'PlotCritiquePanel.tsx',
  'StageHumanLoopPanel.tsx',
  'FigureReviewPanel.tsx',
  'WorkflowPage.tsx',
  'PromptPresetBar.tsx',
];

const replacements = [
  ['red-500', 'danger-500'],
  ['red-400', 'danger-400'],
  ['red-300', 'danger-300'],
  ['emerald-500', 'bp-green'],
  ['emerald-400', 'bp-green'],
  ['emerald-300', 'bp-green'],
  ['green-500', 'bp-green'],
  ['green-400', 'bp-green'],
  ['green-300', 'bp-green'],
  ['blue-500', 'bp-cyan'],
  ['blue-400', 'bp-cyan'],
  ['blue-300', 'bp-cyan'],
  ['blue-200', 'bp-cyan'],
  ['amber-500', 'bp-yellow'],
  ['amber-400', 'bp-yellow'],
  ['amber-300', 'bp-yellow'],
  ['amber-200', 'bp-yellow'],
  ['yellow-500', 'bp-yellow'],
  ['yellow-400', 'bp-yellow'],
  ['violet-500', 'bp-purple'],
  ['violet-400', 'bp-purple'],
  ['violet-300', 'bp-purple'],
  ['violet-200', 'bp-purple'],
  ['purple-500', 'bp-purple'],
  ['purple-400', 'bp-purple'],
  ['purple-300', 'bp-purple'],
  ['cyan-500', 'bp-cyan'],
  ['cyan-400', 'bp-cyan'],
  ['cyan-300', 'bp-cyan'],
];

for (const file of files) {
  const filePath = path.join(componentsDir, file);
  if (!fs.existsSync(filePath)) {
    console.warn('skip missing', file);
    continue;
  }
  let content = fs.readFileSync(filePath, 'utf8');
  for (const [from, to] of replacements) {
    content = content.split(from).join(to);
  }
  fs.writeFileSync(filePath, content, 'utf8');
  console.log('updated', file);
}
