/** 知识图谱 Cytoscape 样式、布局与教育阶段视图预设（Blueprint 画布 + 科研节点色） */
import cytoscape, { type Core, type ElementDefinition, type LayoutOptions, type StylesheetStyle } from 'cytoscape';
import fcose from 'cytoscape-fcose';
import type { EducationLevel, KgCommunity, KgEdge, KgNode } from '@/services/knowledgeGraphService';
import { pencilVariables } from '@/config/designTokens';

export const NEO4J_BG = pencilVariables['bp-bg'];
export const NEO4J_GREEN = pencilVariables['bp-cyan'];
export const NEO4J_BORDER = pencilVariables['border-default'];

export const NODE_COLORS: Record<string, string> = {
  Paper: '#68bdf6',
  Method: '#00dc82',
  Dataset: '#ffd86e',
  Metric: '#f85a65',
  Task: '#4d8bff',
  Problem: '#ff9f43',
  Hypothesis: '#d9a5f9',
  Evidence: '#57c7a9',
  Result: '#78f5d8',
  Limitation: '#ff6b6b',
  FedAlgorithm: '#00dc82',
  NonIIDType: '#ffb347',
  default: '#8b949e',
};

export const TYPE_LABELS_ZH: Record<string, string> = {
  Paper: '论文',
  Method: '方法',
  Dataset: '数据集',
  Metric: '指标',
  Task: '任务',
  Problem: '问题',
  Hypothesis: '假设',
  Evidence: '证据',
  Result: '结果',
  Limitation: '局限',
  FedAlgorithm: '联邦算法',
  NonIIDType: 'Non-IID 类型',
};

/** 简化视图保留的核心概念类型 */
export const SIMPLIFIED_NODE_TYPES = new Set([
  'Paper',
  'Method',
  'Dataset',
  'Task',
  'Problem',
  'Result',
  'FedAlgorithm',
  'NonIIDType',
]);

export type LabelDisplayMode = 'auto' | 'always' | 'never';
export type KgViewMode = 'simplified' | 'standard' | 'research';

export interface KgViewPreset {
  mode: KgViewMode;
  label: string;
  hint: string;
  allowedNodeTypes: Set<string> | null;
  showCommunityCompounds: boolean;
  maxCommunities: number;
  showEdgeLabelsOnSelect: boolean;
  defaultLabelMode: LabelDisplayMode;
  labelZoomThreshold: number;
  nodeSize: number;
  maxVisibleNodes: number | null;
}

let fcoseRegistered = false;

export function ensureFcoseRegistered(): void {
  if (!fcoseRegistered) {
    cytoscape.use(fcose);
    fcoseRegistered = true;
  }
}

export function getEducationViewPreset(level: EducationLevel): KgViewPreset {
  switch (level) {
    case 'primary':
    case 'secondary':
      return {
        mode: 'simplified',
        label: level === 'primary' ? '科普简化' : '中学简化',
        hint: '仅显示论文、方法、任务等核心概念，细节见侧栏社区卡片',
        allowedNodeTypes: SIMPLIFIED_NODE_TYPES,
        showCommunityCompounds: false,
        maxCommunities: 0,
        showEdgeLabelsOnSelect: false,
        defaultLabelMode: 'never',
        labelZoomThreshold: 0.85,
        nodeSize: 52,
        maxVisibleNodes: level === 'primary' ? 28 : 36,
      };
    case 'undergraduate':
      return {
        mode: 'standard',
        label: '本科标准',
        hint: '完整节点类型，fcose 力导向布局',
        allowedNodeTypes: null,
        showCommunityCompounds: false,
        maxCommunities: 0,
        showEdgeLabelsOnSelect: false,
        defaultLabelMode: 'auto',
        labelZoomThreshold: 0.7,
        nodeSize: 44,
        maxVisibleNodes: null,
      };
    case 'graduate':
    case 'researcher':
      return {
        mode: 'research',
        label: '科研全景',
        hint: '社区聚类轮廓、选中边显示关系、可导出 PNG',
        allowedNodeTypes: null,
        showCommunityCompounds: true,
        maxCommunities: 6,
        showEdgeLabelsOnSelect: true,
        defaultLabelMode: 'auto',
        labelZoomThreshold: 0.65,
        nodeSize: 40,
        maxVisibleNodes: null,
      };
    default:
      return getEducationViewPreset('undergraduate');
  }
}

export function labelMaxLen(educationLevel: EducationLevel): number {
  switch (educationLevel) {
    case 'primary':
      return 10;
    case 'secondary':
      return 14;
    case 'undergraduate':
      return 18;
    case 'graduate':
      return 22;
    case 'researcher':
      return 28;
    default:
      return 18;
  }
}

export function truncateLabel(text: string, maxLen: number): string {
  const t = (text || '').trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}

function capNodesByDegree(nodes: KgNode[], edges: KgEdge[], max: number): KgNode[] {
  if (nodes.length <= max) return nodes;
  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, 0);
  for (const e of edges) {
    if (degree.has(e.source)) degree.set(e.source, (degree.get(e.source) || 0) + 1);
    if (degree.has(e.target)) degree.set(e.target, (degree.get(e.target) || 0) + 1);
  }
  return [...nodes]
    .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0))
    .slice(0, max);
}

/** 按教育阶段视图预设裁剪节点（在用户手动筛选之前） */
export function applyViewPresetToGraph(
  nodes: KgNode[],
  edges: KgEdge[],
  preset: KgViewPreset,
): { nodes: KgNode[]; edges: KgEdge[] } {
  let filtered = nodes;
  if (preset.allowedNodeTypes) {
    filtered = nodes.filter((n) => preset.allowedNodeTypes!.has(n.type));
  }
  if (preset.maxVisibleNodes != null && filtered.length > preset.maxVisibleNodes) {
    filtered = capNodesByDegree(filtered, edges, preset.maxVisibleNodes);
  }
  const nodeIds = new Set(filtered.map((n) => n.id));
  const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
  return { nodes: filtered, edges: filteredEdges };
}

function assignCommunityParents(
  nodes: KgNode[],
  communities: KgCommunity[] | undefined,
  preset: KgViewPreset,
): { parentMap: Map<string, string>; compoundLabels: Map<string, string> } {
  const parentMap = new Map<string, string>();
  const compoundLabels = new Map<string, string>();
  if (!preset.showCommunityCompounds || !communities?.length) {
    return { parentMap, compoundLabels };
  }

  const nodeIds = new Set(nodes.map((n) => n.id));
  const sorted = [...communities].sort((a, b) => b.node_count - a.node_count);

  for (const comm of sorted.slice(0, preset.maxCommunities)) {
    const members = (comm.node_ids || []).filter((id) => nodeIds.has(id) && !parentMap.has(id));
    if (members.length < 2) continue;
    const zhType = TYPE_LABELS_ZH[comm.dominant_type] || comm.dominant_type;
    compoundLabels.set(comm.community_id, `${zhType} · ${members.length}`);
    for (const id of members) parentMap.set(id, comm.community_id);
  }
  return { parentMap, compoundLabels };
}

export function buildGraphElements(
  nodes: KgNode[],
  edges: KgEdge[],
  communities: KgCommunity[] | undefined,
  preset: KgViewPreset,
  educationLevel: EducationLevel,
): ElementDefinition[] {
  const maxLen = labelMaxLen(educationLevel);
  const { parentMap, compoundLabels } = assignCommunityParents(nodes, communities, preset);
  const compoundIds = new Set(compoundLabels.keys());

  const elements: ElementDefinition[] = [];

  compoundIds.forEach((cid) => {
    elements.push({
      data: {
        id: cid,
        displayLabel: compoundLabels.get(cid) || cid,
        isCompound: true,
      },
      classes: 'community',
    });
  });

  for (const n of nodes) {
    elements.push({
      data: {
        id: n.id,
        parent: parentMap.get(n.id),
        displayLabel: truncateLabel(n.label || n.type, maxLen),
        fullLabel: n.label,
        type: n.type,
        nodeData: n,
      },
    });
  }

  for (const e of edges) {
    elements.push({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        relation: e.relation,
        edgeData: e,
      },
    });
  }

  return elements;
}

export function getKgStylesheets(preset: KgViewPreset): StylesheetStyle[] {
  const size = preset.nodeSize;
  const sheets: StylesheetStyle[] = [
    {
      selector: 'node',
      style: {
        shape: 'ellipse',
        width: size,
        height: size,
        'background-color': (ele) => NODE_COLORS[ele.data('type')] || NODE_COLORS.default,
        'background-opacity': 0.95,
        'border-width': 3,
        'border-color': (ele) => NODE_COLORS[ele.data('type')] || NODE_COLORS.default,
        'border-opacity': 0.5,
        label: 'data(displayLabel)',
        color: '#e6edf3',
        'font-size': preset.mode === 'simplified' ? '11px' : '10px',
        'font-weight': 'normal',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 10,
        'text-wrap': 'wrap',
        'text-max-width': preset.mode === 'simplified' ? '120px' : '100px',
        'line-height': 1.25,
        'text-opacity': 0,
        'text-background-color': '#161b22',
        'text-background-opacity': 0.94,
        'text-background-padding': '4px',
        'text-background-shape': 'roundrectangle',
        'text-border-color': '#30363d',
        'text-border-width': 1,
        'text-border-opacity': 0.55,
      },
    },
    {
      selector: 'node.community',
      style: {
        shape: 'roundrectangle',
        'background-color': '#00dc82',
        'background-opacity': 0.05,
        'border-width': 2,
        'border-color': '#30363d',
        'border-style': 'dashed',
        'border-opacity': 0.7,
        padding: '28px',
        label: 'data(displayLabel)',
        color: '#8b949e',
        'font-size': '9px',
        'text-valign': 'top',
        'text-halign': 'center',
        'text-margin-y': -6,
        'text-opacity': 0.85,
        width: 1,
        height: 1,
      },
    },
    {
      selector: 'node.hover',
      style: {
        'border-width': 4,
        'border-color': NEO4J_GREEN,
        'border-opacity': 1,
        'text-opacity': 1,
        'z-index': 10,
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': '#ffffff',
        'border-opacity': 1,
        'text-opacity': 1,
        'z-index': 20,
      },
    },
    {
      selector: 'node.show-label',
      style: {
        'text-opacity': 1,
      },
    },
    {
      selector: 'node.dim',
      style: {
        opacity: 0.3,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': '#3d444d',
        'target-arrow-color': NEO4J_GREEN,
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.75,
        'curve-style': 'bezier',
        opacity: 0.7,
        label: '',
      },
    },
    {
      selector: 'edge:selected',
      style: {
        width: 2.5,
        'line-color': NEO4J_GREEN,
        'target-arrow-color': NEO4J_GREEN,
        opacity: 1,
        ...(preset.showEdgeLabelsOnSelect
          ? {
              label: 'data(relation)',
              color: '#c9d1d9',
              'font-size': '8px',
              'text-rotation': 'autorotate',
              'text-margin-y': -10,
              'text-background-color': '#161b22',
              'text-background-opacity': 0.85,
              'text-background-padding': '2px',
            }
          : {}),
      },
    },
    {
      selector: 'edge.highlight',
      style: {
        'line-color': NEO4J_GREEN,
        'target-arrow-color': NEO4J_GREEN,
        opacity: 1,
        width: 2,
      },
    },
  ];
  return sheets;
}

/** fcose 力导向布局（方案 A） */
export function getKgLayout(nodeCount: number, hasCompounds: boolean): LayoutOptions {
  ensureFcoseRegistered();
  const scale = Math.max(1, Math.sqrt(nodeCount / 16));
  return {
    name: 'fcose',
    animate: true,
    animationDuration: 520,
    fit: true,
    padding: hasCompounds ? 100 : 80,
    nodeDimensionsIncludeLabels: true,
    packComponents: true,
    randomize: true,
    quality: nodeCount > 60 ? 'default' : 'proof',
    nodeRepulsion: () => 9500 * scale,
    idealEdgeLength: () => 130 * scale,
    edgeElasticity: () => 0.42,
    nestingFactor: hasCompounds ? 0.14 : 0.08,
    gravity: 0.22,
    numIter: nodeCount > 50 ? 2800 : 2200,
    tile: hasCompounds,
    tilingPaddingVertical: 40,
    tilingPaddingHorizontal: 40,
  } as LayoutOptions;
}

export const LABEL_ZOOM_THRESHOLD = 0.7;

export function syncGraphLabels(
  cy: Core,
  labelMode: LabelDisplayMode,
  zoomThreshold: number,
): void {
  const zoom = cy.zoom();
  const zoomOk = zoom >= zoomThreshold;
  cy.nodes().not('.community').forEach((node) => {
    let show = false;
    if (labelMode === 'never') show = false;
    else if (labelMode === 'always') show = true;
    else show = node.hasClass('hover') || node.selected() || zoomOk;
    node.toggleClass('show-label', show);
  });
}

export function focusCommunityOnCanvas(cy: Core, communityId: string): void {
  const compound = cy.getElementById(communityId);
  if (compound.length) {
    cy.animate({ fit: { eles: compound, padding: 64 } }, { duration: 420 });
    compound.addClass('hover');
    window.setTimeout(() => compound.removeClass('hover'), 1200);
    return;
  }
  const comm = cy.nodes(`[parent = "${communityId}"]`);
  if (comm.length) {
    cy.animate({ fit: { eles: comm, padding: 72 } }, { duration: 420 });
  }
}

export function exportGraphPng(cy: Core, filename: string): void {
  const png = cy.png({ bg: NEO4J_BG, full: true, scale: 2 });
  const link = document.createElement('a');
  link.href = png;
  link.download = filename;
  link.click();
}
