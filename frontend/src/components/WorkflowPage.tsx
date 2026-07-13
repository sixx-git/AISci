import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, AlertTriangle, Brain, BookOpen, GitBranch, Lightbulb, ShieldCheck, FlaskConical, ClipboardCheck, FileText, RefreshCw, Database, ArrowRight } from 'lucide-react';
import { Card } from '@/components/Card';
import { AgentNode } from '@/components/AgentNode';
import { AgentDetailPanel } from '@/components/AgentDetailPanel';
import { WorkflowActionBar } from '@/components/WorkflowActionBar';
import { ExecutionTierBadge } from '@/components/ExecutionTierBadge';
import { StageHumanLoopPanel } from '@/components/StageHumanLoopPanel';
import { IterationHistoryPanel } from '@/components/IterationHistoryPanel';
import { VerifiableChecksPanel } from '@/components/VerifiableChecksPanel';
import { PlotCritiquePanel } from '@/components/PlotCritiquePanel';
import { CollapsiblePanel } from '@/components/workspace/CollapsiblePanel';
import { LoopConfigPanel, DEFAULT_LOOP_CONFIG, loopConfigToRunOptions, ITERATION_MODE_HINTS, type LoopConfigState } from '@/components/LoopConfigPanel';
import { WorkflowAdvancedLinks } from '@/components/WorkflowAdvancedLinks';
import { RunHistoryPanel } from '@/components/RunHistoryPanel';
import { HitlGateModal } from '@/components/HitlGateModal';
import { Button } from '@/components/Button';
import { buildProjectTabUrl } from '@/lib/projectNavigation';
import { extractValidationDataGuidance, formatValidationBlockedSummary } from '@/lib/validationDataGuidance';
import { ValidationDataGuidanceCard } from '@/components/ValidationDataGuidanceCard';
import { getHitlGateReviewTarget } from '@/config/hitlGateReview';
import {
  buildHitlGateEventKey,
  hasSeenHitlGateModal,
  markHitlGateModalSeen,
} from '@/lib/hitlGateModalStorage';
import { pipelineService } from '@/services/pipelineService';
import { humanLoopService } from '@/services/humanLoopService';
import { activeRunKey, activeRunStatusKey } from '@/lib/storageKeys';
import type {
  AgentNodeData,
  AgentStatus,
  PlotQualityData,
  HitlGateInfo,
  PipelineRunExtraMetadata,
  PipelineRunResult,
  PipelineStageLog,
} from '@/types';

interface WorkflowPageProps {
  projectId?: string;
  researchQuestion?: string;
  compact?: boolean;
  onPipelineCompleted?: (result: PipelineRunResult) => void;
  onPipelineStarted?: (runId: string) => void;
  onHumanLoopUpdated?: (stage: string) => void;
}

type RunState = 'idle' | 'submitting' | 'running' | 'polling';

const MAX_CONSECUTIVE_POLL_FAILURES = 5;
const POLL_INTERVAL_MS = 2000;
const MAX_ALL_PENDING_POLLS = 5;

const STAGE_TO_NODE_ID: Record<string, string> = {
  problem_understanding: 'problem',
  literature_mining: 'literature',
  knowledge_gap: 'gaps',
  hypothesis_generation: 'hypothesis',
  hypothesis_review: 'evaluation',
  experiment_design: 'experiment',
  small_validation: 'validation',
  report_generation: 'report',
  // 历史 run 兼容：旧数据采集阶段仍高亮同一节点
  data_acquisition: 'gaps',
};

/** 节点 → Pipeline 阶段（用于重跑/HITL）；勿用 STAGE_TO_NODE_ID 反查，避免 gaps 被 data_acquisition 覆盖 */
const NODE_ID_TO_STAGE: Record<string, string> = {
  problem: 'problem_understanding',
  literature: 'literature_mining',
  gaps: 'knowledge_gap',
  hypothesis: 'hypothesis_generation',
  evaluation: 'hypothesis_review',
  experiment: 'experiment_design',
  validation: 'small_validation',
  report: 'report_generation',
};

// ============ localStorage 工具 ============

function getActiveRunId(projectId: string): string | null {
  try {
    return localStorage.getItem(activeRunKey(projectId)) || null;
  } catch {
    return null;
  }
}

function setActiveRunId(projectId: string, runId: string): void {
  try {
    localStorage.setItem(activeRunKey(projectId), runId);
    localStorage.setItem(activeRunStatusKey(projectId), 'running');
  } catch { /* ignore */ }
}

function clearActiveRun(projectId: string): void {
  try {
    localStorage.removeItem(activeRunKey(projectId));
    localStorage.removeItem(activeRunStatusKey(projectId));
  } catch { /* ignore */ }
}

// ============ 工具函数 ============

function summarizeStageData(stageName: string, data: unknown): string {
  if (typeof data !== 'object' || data === null) {
    return JSON.stringify(data).slice(0, 200);
  }

  const d = data as Record<string, unknown>;

  if (stageName === 'literature_mining') {
    const parts: string[] = [];
    const searched = d.literature_search_count ?? d.candidate_references_count;
    const imported = d.literature_import_count ?? d.imported_documents;
    if (searched != null || imported != null) {
      parts.push(`检索 ${searched ?? '—'} 篇 / 入库 ${imported ?? '—'} 篇`);
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    if (so) {
      const sp = so.search_papers as Record<string, unknown> | undefined;
      if (sp && sp.data) {
        const spData = sp.data as Record<string, unknown>;
        if (spData.total != null) {
          parts.push(`SearchPapersSkill: ${spData.total} 篇论文`);
        }
      }
      const cg = so.citation_grounding as Record<string, unknown> | undefined;
      if (cg && cg.data) {
        const cgData = cg.data as Record<string, unknown>;
        if (cgData.references_verified != null) {
          parts.push(`CitationGrounding: ${cgData.references_verified} verified`);
        }
      }
    }
    if (d.facts && Array.isArray(d.facts)) {
      parts.push(`${d.facts.length} 个事实`);
    }
    if (d.citation_map && Array.isArray(d.citation_map)) {
      parts.push(`${d.citation_map.length} 个引用映射`);
    }
    return parts.join(' | ') || JSON.stringify(data).slice(0, 200);
  }

  if (stageName === 'hypothesis_generation') {
    const parts: string[] = [];
    if (d.research_question) {
      parts.push(`研究问题: ${String(d.research_question).slice(0, 80)}`);
    }
    if (d.hypotheses && Array.isArray(d.hypotheses)) {
      const hyps = d.hypotheses as unknown[];
      parts.push(`生成了 ${hyps.length} 条假设`);
    }
    const tree = d.hypothesis_tree as Record<string, unknown> | undefined;
    if (tree?.branches && Array.isArray(tree.branches)) {
      parts.push(`假设树保留 Top-${(tree.branches as unknown[]).length}`);
      if (tree.selected_branch_id) parts.push(`选中: ${String(tree.selected_branch_id).slice(0, 12)}`);
    }
    if (d.off_topic_count != null) {
      parts.push(`${d.off_topic_count} 条偏题`);
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    if (so) {
      const qa = so.question_alignment as Record<string, unknown> | undefined;
      if (qa && qa.data) {
        const qaData = qa.data as Record<string, unknown>;
        if (qaData.alignment_score != null) {
          parts.push(`QuestionAlignment: ${Number(qaData.alignment_score).toFixed(2)}`);
        }
        if (qaData.off_topic_count != null) {
          parts.push(`偏题: ${qaData.off_topic_count}`);
        }
      }
    }
    return parts.join(' | ') || JSON.stringify(data).slice(0, 200);
  }

  if (stageName === 'hypothesis_review') {
    const parts: string[] = [];
    if (d.reviews && Array.isArray(d.reviews)) {
      parts.push(`${(d.reviews as unknown[]).length} 条评审`);
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    const ensemble = (so?.ensemble_review || d.ensemble_review) as Record<string, unknown> | undefined;
    if (ensemble) {
      if (ensemble.overall != null) parts.push(`集成 ${Number(ensemble.overall).toFixed(1)}`);
      if (ensemble.decision) parts.push(String(ensemble.decision));
    }
    if (d.ensemble_overall != null) parts.push(`综合 ${Number(d.ensemble_overall).toFixed(1)}`);
    return parts.join(' | ') || JSON.stringify(data).slice(0, 200);
  }

  if (stageName === 'experiment_design') {
    const parts: string[] = [];
    const gate = d.executability_gate as Record<string, unknown> | undefined;
    if (gate) {
      parts.push(
        gate.passed
          ? `可执行性 ✓ ${Number(gate.score ?? 0).toFixed(0)}`
          : `可执行性 ✗ ${Number(gate.score ?? 0).toFixed(0)}`,
      );
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    if (so) {
      const dd = so.dataset_discovery as Record<string, unknown> | undefined;
      if (dd && dd.data) {
        const ddData = dd.data as Record<string, unknown>;
        if (ddData.total != null) {
          parts.push(`DatasetDiscovery: ${ddData.total} 个数据集`);
        }
      }
      const sc = so.experiment_sanity_check as Record<string, unknown> | undefined;
      if (sc && sc.data) {
        const scData = sc.data as Record<string, unknown>;
        if (Array.isArray(scData.warnings) && scData.warnings.length > 0) {
          parts.push(`SanityCheck: ${scData.warnings.length} warnings`);
        }
      }
    }
    if (d.methods && typeof d.methods === 'string') {
      parts.push(`方法: ${d.methods.slice(0, 40)}`);
    }
    return parts.join(' | ') || JSON.stringify(data).slice(0, 200);
  }

  if (stageName === 'small_validation') {
    const parts: string[] = [];
    const blockedSummary = formatValidationBlockedSummary(d);
    if (blockedSummary) {
      parts.push(blockedSummary);
      return parts.join(' | ');
    }
    if (d.validation_status === 'blocked' || d.validation_blocked === true) {
      parts.push('数据不匹配，验证已阻塞');
    }
    if (d.sandbox_execution && typeof d.sandbox_execution === 'object') {
      const sb = d.sandbox_execution as Record<string, unknown>;
      parts.push(sb.success ? '沙箱实测成功' : '沙箱执行失败');
    }
    if (d.results && typeof d.results === 'object') {
      const r = d.results as Record<string, unknown>;
      if (r.result_type_summary && typeof r.result_type_summary === 'string') {
        const typeMap: Record<string, string> = {
          has_actual_results: '有真实分析结果',
          simulated_only: '仅有模拟结果',
          expected_only: '仅有预期结果',
          none: '无结果',
        };
        parts.push(typeMap[r.result_type_summary] || r.result_type_summary);
      }
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    if (so) {
      const pa = so.preliminary_analysis as Record<string, unknown> | undefined;
      if (pa && pa.data) {
        const paData = pa.data as Record<string, unknown>;
        if (paData.summary_statistics && typeof paData.summary_statistics === 'object') {
          parts.push(`分析 ${Object.keys(paData.summary_statistics as Record<string, unknown>).length} 个数据源`);
        }
        if (Array.isArray(paData.correlations) && paData.correlations.length > 0) {
          parts.push(`${paData.correlations.length} 对相关性`);
        }
        if (paData.data_source_flag && typeof paData.data_source_flag === 'string') {
          const flagMap: Record<string, string> = { real_data: '真实数据', simulated: '模拟', no_data: '无数据' };
          parts.push(`数据来源: ${flagMap[paData.data_source_flag] || paData.data_source_flag}`);
        }
      }
    }
    return parts.join(' | ') || '可折叠查看详细输出';
  }

  if (stageName === 'report_generation') {
    const parts: string[] = [];
    if (d.plots && Array.isArray(d.plots)) {
      const plotsArr = d.plots as unknown[];
      const realCount = plotsArr.filter((p: unknown) => p && typeof p === 'object' && (p as Record<string, unknown>).is_generated_from_real_data === true).length;
      parts.push(`${plotsArr.length} 张图表 (${realCount} 张基于真实数据)`);
    }
    const so = d.skill_outputs as Record<string, unknown> | undefined;
    if (so) {
      const qc = so.report_quality_check as Record<string, unknown> | undefined;
      if (qc && qc.data) {
        const qcData = qc.data as Record<string, unknown>;
        if (qcData.score != null) {
          parts.push(`质量评分: ${qcData.score}`);
        }
      }
    }
    if (d.compliance_check && typeof d.compliance_check === 'object') {
      const cc = d.compliance_check as Record<string, unknown>;
      if (cc.completed != null && cc.total_items != null) {
        parts.push(`合规: ${cc.completed}/${cc.total_items}`);
      }
    }
    return parts.join(' | ') || '可折叠查看详细输出';
  }

  return JSON.stringify(data).slice(0, 200);
}

const BASE_AGENT_NODES: AgentNodeData[] = [
  {
    id: 'problem', name: '问题理解智能体',
    shortDesc: '解析研究问题的核心要素与上下文',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: Brain,
  },
  {
    id: 'literature', name: '文献挖掘智能体',
    shortDesc: '从 arXiv / OpenAlex 等源检索与挖掘相关文献',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: BookOpen,
  },
  {
    id: 'gaps', name: '知识缺口发现智能体',
    shortDesc: '分析现有文献，识别知识空白与研究机会',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: GitBranch,
  },
  {
    id: 'hypothesis', name: '假设生成智能体',
    shortDesc: '基于知识缺口生成可验证的科学假设',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: Lightbulb,
  },
  {
    id: 'evaluation', name: '可行性评估智能体',
    shortDesc: '评审假设的科学性与实验可行性',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: ShieldCheck,
  },
  {
    id: 'experiment', name: '实验设计智能体',
    shortDesc: '分析已上传数据并规划可验证实验方案',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: FlaskConical,
  },
  {
    id: 'validation', name: '小样验证智能体',
    shortDesc: '在受限数据集上执行快速验证实验',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: ClipboardCheck,
  },
  {
    id: 'report', name: '报告生成智能体',
    shortDesc: '汇总所有阶段结果，生成可导出报告',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: FileText,
  },
];

function createInitialNodes(): AgentNodeData[] {
  return BASE_AGENT_NODES.map((n) => ({ ...n, logs: [] }));
}

function normalizeStageName(stage?: string): string {
  if (!stage) return '';
  return stage
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/^pipelinestage\./i, '')
    .trim();
}

function normalizeStatus(status?: string): string {
  if (!status) return 'pending';
  return status
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .trim();
}

function mapStatus(status: string): AgentStatus {
  const normalized = normalizeStatus(status);
  switch (normalized) {
    case 'running':
    case 'processing':
      return 'running';
    case 'completed':
    case 'success':
    case 'done':
    case 'finished':
      return 'completed';
    case 'failed':
    case 'error':
    case 'fault':
      return 'failed';
    case 'human_review_required':
    case 'review':
    case 'needs_review':
    case 'human_review':
      return 'human_review_required';
    default:
      return 'pending';
  }
}

function mergeStageData(node: AgentNodeData, stage: PipelineStageLog): AgentNodeData {
  const mappedStatus = mapStatus(stage.status);
  const hasHumanEdit = Boolean(stage.human_modified_output);
  const hasOriginalOutput = Boolean(stage.output_data ?? node.output_data);
  const newStatus: AgentStatus =
    hasHumanEdit
    && hasOriginalOutput
    && (mappedStatus === 'human_review_required' || mappedStatus === 'human_review')
      ? 'completed'
      : mappedStatus;
  const durationMs =
    stage.duration_ms ?? (stage.duration ? Math.round(stage.duration * 1000) : null);

  const logEntry = stage.error_message
    ? `[${new Date().toLocaleTimeString()}] ${newStatus}: ${stage.error_message}`
    : newStatus !== node.status
      ? `[${new Date().toLocaleTimeString()}] 状态: ${newStatus}`
      : null;

  return {
    ...node,
    status: newStatus,
    duration: durationMs,
    logs: logEntry ? [...node.logs, logEntry] : node.logs,
    input_data: stage.input_data ?? node.input_data,
    output_data: stage.output_data ?? node.output_data,
    error_message: stage.error_message ?? node.error_message,
    prompt_used: stage.prompt_used ?? node.prompt_used,
    model_used: stage.model_used ?? node.model_used,
    model_parameters: stage.model_parameters ?? node.model_parameters,
    token_count: stage.token_count ?? node.token_count,
    human_modified_output: stage.human_modified_output ?? node.human_modified_output,
    human_reviewed: stage.human_reviewed ?? node.human_reviewed,
    human_feedback: stage.human_feedback ?? node.human_feedback,
    edited_at: stage.edited_at ?? node.edited_at,
    human_edited: hasHumanEdit || Boolean(stage.human_edited) || node.human_edited,
    revision_history: stage.revision_history ?? node.revision_history,
    chat_history: stage.chat_history ?? node.chat_history,
    model: stage.model_used || node.model,
    inputSummary: stage.input_data
      ? summarizeStageData(stage.stage ?? '', stage.input_data)
      : node.inputSummary,
    outputSummary: (stage.human_modified_output ?? stage.output_data)
      ? summarizeStageData(stage.stage ?? '', (stage.human_modified_output ?? stage.output_data) as Record<string, unknown>)
      : node.outputSummary,
  };
}

function extractRunStatusFromResponse(response: unknown): string | null {
  if (!response || typeof response !== 'object') return null;
  const r = response as Record<string, unknown>;
  const data = (r.code != null && r.data != null ? r.data : response) as Record<string, unknown>;
  if (!data || typeof data !== 'object') return null;
  const status = data.status;
  return typeof status === 'string' ? status : null;
}

const NODE_ORDER = BASE_AGENT_NODES.map((n) => n.id);

const RESUME_PHASE_TO_NODE: Record<string, string> = {
  after_hypothesis_generation: 'evaluation',
  after_hypothesis_review: 'experiment',
  after_experiment_design: 'validation',
  after_small_validation: 'report',
};

function stageKeyToNodeId(stageKey?: string | null): string | null {
  if (!stageKey) return null;
  const normalized = normalizeStageName(stageKey);
  return STAGE_TO_NODE_ID[normalized] ?? (NODE_ORDER.includes(normalized) ? normalized : null);
}

function extractExtraMetadataFromResponse(response: unknown): PipelineRunExtraMetadata | null {
  if (!response || typeof response !== 'object') return null;
  const r = response as Record<string, unknown>;
  const data = (r.code != null && r.data != null ? r.data : response) as Record<string, unknown>;
  if (!data || typeof data !== 'object') return null;
  const meta = data.extra_metadata;
  return meta && typeof meta === 'object' ? meta as PipelineRunExtraMetadata : null;
}

function extractCurrentStageFromResponse(response: unknown): string | null {
  if (!response || typeof response !== 'object') return null;
  const r = response as Record<string, unknown>;
  const data = (r.code != null && r.data != null ? r.data : response) as Record<string, unknown>;
  if (!data || typeof data !== 'object') return null;
  const cs = data.current_stage;
  return typeof cs === 'string' ? cs : null;
}

function inferRunningNodeId(
  nodes: AgentNodeData[],
  stages: PipelineStageLog[],
  currentStage?: string | null,
  extraMetadata?: PipelineRunExtraMetadata | null,
): string | null {
  const runningStage = stages.find((s) => mapStatus(s.status) === 'running');
  if (runningStage) {
    return stageKeyToNodeId(runningStage.stage) ?? null;
  }

  const fromCurrent = stageKeyToNodeId(currentStage);
  if (fromCurrent) {
    const currentNode = nodes.find((n) => n.id === fromCurrent);
    // current_stage 在 DB 中可能滞后于阶段实际完成状态（如缺口完成后、假设生成前）
    if (currentNode && currentNode.status !== 'completed') {
      return fromCurrent;
    }
  }

  const resumePhase = extraMetadata?.hitl_gate?.resume_phase;
  if (resumePhase && RESUME_PHASE_TO_NODE[resumePhase]) {
    return RESUME_PHASE_TO_NODE[resumePhase];
  }

  const cleared = extraMetadata?.hitl_gate?.cleared_stages ?? [];
  const lastCleared = cleared[cleared.length - 1];
  if (lastCleared) {
    const afterPhase = `after_${lastCleared}`;
    if (RESUME_PHASE_TO_NODE[afterPhase]) {
      return RESUME_PHASE_TO_NODE[afterPhase];
    }
  }

  let lastCompletedIdx = -1;
  nodes.forEach((node, idx) => {
    if (node.status === 'completed') lastCompletedIdx = idx;
  });
  if (lastCompletedIdx >= 0 && lastCompletedIdx < nodes.length - 1) {
    return nodes[lastCompletedIdx + 1].id;
  }

  const firstPending = nodes.findIndex((n) => n.status === 'pending');
  return firstPending >= 0 ? nodes[firstPending].id : null;
}

function applyInferredRunningStage(
  nodes: AgentNodeData[],
  overallStatus: string | null,
  stages: PipelineStageLog[] = [],
  currentStage?: string | null,
  extraMetadata?: PipelineRunExtraMetadata | null,
): AgentNodeData[] {
  if (overallStatus !== 'running') return nodes;

  const runningNodeId = inferRunningNodeId(nodes, stages, currentStage, extraMetadata);
  if (!runningNodeId) return nodes;

  // 仅一个节点为 running；已完成节点不被 current_stage 滞后拖回 running
  return nodes.map((node) => {
    if (node.id === runningNodeId) {
      return node.status === 'completed' ? node : { ...node, status: 'running' as AgentStatus };
    }
    if (node.status === 'running') {
      return { ...node, status: 'completed' as AgentStatus };
    }
    return node;
  });
}

function extractStagesFromResponse(response: unknown): PipelineStageLog[] {
  if (!response || typeof response !== 'object') return [];

  const r = response as Record<string, unknown>;

  let data: unknown = null;
  if (r.code != null && r.data != null) {
    data = r.data;
  } else {
    data = response;
  }

  if (!data || typeof data !== 'object') return [];

  const d = data as Record<string, unknown>;

  if (Array.isArray(d.stages)) return d.stages as PipelineStageLog[];
  if (Array.isArray(d.stage_executions)) return d.stage_executions as PipelineStageLog[];
  if (Array.isArray(d)) return d as PipelineStageLog[];

  return [];
}

function matchStageToNode(stage: PipelineStageLog, node: AgentNodeData): boolean {
  const ns = normalizeStageName(stage.stage);
  return ns === node.id
    || STAGE_TO_NODE_ID[ns] === node.id
    || stage.stage?.toLowerCase() === node.name?.toLowerCase();
}

// ============ 组件 ============

export function WorkflowPage({
  projectId,
  researchQuestion,
  compact: _compact = false,
  onPipelineCompleted,
  onPipelineStarted,
  onHumanLoopUpdated,
}: WorkflowPageProps) {
  const navigate = useNavigate();
  const [nodes, setNodes] = useState<AgentNodeData[]>(() => createInitialNodes());
  const [selectedId, setSelectedId] = useState<string>('');

  const [runState, setRunState] = useState<RunState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  /** 最近一次 run（含已完成），用于本阶段重跑等操作 */
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [hasExistingRuns, setHasExistingRuns] = useState<boolean | null>(null);
  const [staleWarning, setStaleWarning] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [runExtraMetadata, setRunExtraMetadata] = useState<PipelineRunExtraMetadata | null>(null);
  const [pipelineRunStatus, setPipelineRunStatus] = useState<string | null>(null);
  const [loopConfig, setLoopConfig] = useState<LoopConfigState>(DEFAULT_LOOP_CONFIG);
  const [showHitlModal, setShowHitlModal] = useState(false);
  const [hitlGateInfo, setHitlGateInfo] = useState<HitlGateInfo | null>(null);
  const [hitlGateRunId, setHitlGateRunId] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveFailuresRef = useRef(0);
  const allPendingCountRef = useRef(0);
  const currentRunIdRef = useRef<string | null>(null);
  const latestRunIdRef = useRef<string | null>(null);
  const hitlModalShownForRunRef = useRef<string | null>(null);
  const hitlGateEventKeyRef = useRef<string | null>(null);

  const rememberLatestRunId = useCallback((runId: string) => {
    latestRunIdRef.current = runId;
    setLatestRunId(runId);
  }, []);

  const resolveRunIdForActions = useCallback((): string | null => {
    return currentRunIdRef.current ?? latestRunIdRef.current;
  }, []);

  const [localResearchQuestion, setLocalResearchQuestion] = useState('');
  const finalResearchQuestion = (researchQuestion ?? '').trim() || localResearchQuestion.trim();

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;
  const selectedNodeId = selectedNode?.id ?? null;

  const experimentDesignOutput = useMemo(() => {
    return nodes.find((n) => n.id === 'experiment')?.output_data as Record<string, unknown> | undefined;
  }, [nodes]);

  const plotQualityData = useMemo((): PlotQualityData | null => {
    for (const nodeId of ['validation', 'report'] as const) {
      const out = nodes.find((n) => n.id === nodeId)?.output_data as Record<string, unknown> | undefined;
      const pq = out?.plot_quality as PlotQualityData | undefined;
      if (pq?.critique) return pq;
    }
    return null;
  }, [nodes]);

  const validationExecutionMeta = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data as Record<string, unknown> | undefined;
    if (!validationOut) return null;
    return {
      executionTier: validationOut.execution_tier as string | undefined,
      executionTierLabel: validationOut.execution_tier_label as string | undefined,
      dataAuthenticity: validationOut.data_authenticity as string | undefined,
      dataAuthenticityLabel: validationOut.data_authenticity_label as string | undefined,
    };
  }, [nodes]);

  const validationDataGuidance = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data;
    return extractValidationDataGuidance(validationOut);
  }, [nodes]);

  const validationBlockedReason = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data as Record<string, unknown> | undefined;
    return typeof validationOut?.validation_blocked_reason === 'string'
      ? validationOut.validation_blocked_reason
      : '';
  }, [nodes]);

  const verifiableValidation = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data as Record<string, unknown> | undefined;
    if (validationOut) {
      const checks = validationOut.verifiable_checks as import('@/types').VerifiableCheck[] | undefined;
      const spec = validationOut.verifiable_hypothesis as { claim?: string; primary_metric?: string } | undefined;
      if (checks?.length || spec?.claim) {
        return {
          checks,
          passed: validationOut.verifiable_passed as boolean | null | undefined,
          spec,
          isPreview: false,
        };
      }
    }
    const expSpec = experimentDesignOutput?.verifiable_hypothesis as { claim?: string; primary_metric?: string } | undefined;
    const expExpected = experimentDesignOutput?.expected_results;
    if (expSpec?.claim || expExpected) {
      return {
        checks: undefined,
        passed: null,
        spec: expSpec?.claim
          ? expSpec
          : { claim: typeof expExpected === 'string' ? expExpected.slice(0, 300) : undefined },
        isPreview: true,
      };
    }
    return null;
  }, [nodes, experimentDesignOutput]);

  const validationPendingPreview = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data;
    const experimentStatus = nodes.find((n) => n.id === 'experiment')?.status;
    if (validationOut || experimentStatus !== 'completed' || !experimentDesignOutput) return null;
    return {
      verifiable_hypothesis: experimentDesignOutput.verifiable_hypothesis,
      expected_results: experimentDesignOutput.expected_results,
      methods: experimentDesignOutput.methods,
      metrics: experimentDesignOutput.metrics,
      hypothesis: experimentDesignOutput.hypothesis,
    };
  }, [nodes, experimentDesignOutput]);

  const federatedPilot = useMemo(() => {
    const validationOut = nodes.find((n) => n.id === 'validation')?.output_data as Record<string, unknown> | undefined;
    return (validationOut?.federated_pilot as Record<string, unknown> | undefined) ?? null;
  }, [nodes]);

  const openHitlGateModal = useCallback(async (runId: string) => {
    setHitlGateRunId(runId);
    rememberLatestRunId(runId);

    let gate: HitlGateInfo = { paused: true };
    try {
      const [gateRes, detailRes] = await Promise.all([
        humanLoopService.getHitlGateStatus(runId),
        pipelineService.getRunDetail(runId),
      ]);
      if (gateRes.code === 200 && gateRes.data) {
        const { run_id: _runId, status: _status, ...rest } = gateRes.data;
        gate = { ...gate, ...rest };
      }
      if (detailRes.code === 200 && detailRes.data) {
        const runDetail = detailRes.data;
        setPipelineRunStatus((runDetail.status as string) ?? null);
        setRunExtraMetadata(runDetail.extra_metadata ?? null);
        if (runDetail.extra_metadata?.hitl_gate) {
          gate = { ...gate, ...runDetail.extra_metadata.hitl_gate };
        }
        const mergedNodes = createInitialNodes().map((node) => {
          const matchedStage = runDetail.stages?.find((s) => matchStageToNode(s as PipelineStageLog, node));
          return matchedStage ? mergeStageData(node, matchedStage as PipelineStageLog) : node;
        });
        setNodes(applyInferredRunningStage(
          mergedNodes,
          (runDetail.status as string) ?? null,
          runDetail.stages as PipelineStageLog[] ?? [],
          (runDetail as { current_stage?: string }).current_stage ?? null,
          runDetail.extra_metadata ?? null,
        ));
      }
    } catch {
      if (runExtraMetadata?.hitl_gate) {
        gate = { ...gate, ...runExtraMetadata.hitl_gate };
      }
    }

    setHitlGateInfo(gate);
    const eventKey = buildHitlGateEventKey(runId, gate);
    hitlGateEventKeyRef.current = eventKey;

    if (hasSeenHitlGateModal(eventKey)) {
      setRunState('idle');
      setStatusMessage('流程暂停中，请前往审阅后确认继续');
      return;
    }

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    hitlModalShownForRunRef.current = runId;
    setRunState('idle');
    setStaleWarning(false);
    setStatusMessage('流程已暂停，等待人工确认后继续');
    markHitlGateModalSeen(eventKey);
    setShowHitlModal(true);
  }, [rememberLatestRunId, runExtraMetadata]);

  const handleDismissHitlModal = useCallback(() => {
    if (hitlGateEventKeyRef.current) {
      markHitlGateModalSeen(hitlGateEventKeyRef.current);
    }
    setShowHitlModal(false);
    setStatusMessage('流程暂停中，请前往审阅后确认继续');
  }, []);

  const handleGoToHitlReview = useCallback((tab: string) => {
    if (!projectId) return;
    if (hitlGateEventKeyRef.current) {
      markHitlGateModalSeen(hitlGateEventKeyRef.current);
    }
    setShowHitlModal(false);
    setStatusMessage('流程暂停中，请审阅后确认继续');
    navigate(buildProjectTabUrl(projectId, tab));
  }, [projectId, navigate]);

  // ========== 生命周期：挂载时恢复 active run ==========
  useEffect(() => {
    if (!projectId) return;

    const savedRunId = getActiveRunId(projectId);
    if (savedRunId) {
      setCurrentRunId(savedRunId);
      currentRunIdRef.current = savedRunId;
      setRunState('running');
      setErrorMessage(null);
      setStaleWarning(false);

      const checkAndResume = async () => {
        try {
          const res = await pipelineService.getStatus(savedRunId);
          updateNodesFromStages(res);
          const resAny = res as unknown as Record<string, unknown>;
          const resultData = resAny.data as Record<string, unknown> | undefined;
          const status = resultData && typeof resultData === 'object'
            ? (resultData as Record<string, unknown>).status
            : null;

          if (status === 'completed' || status === 'failed') {
            setRunState('idle');
            clearActiveRun(projectId);
            currentRunIdRef.current = null;
            setCurrentRunId(null);

            if (status === 'completed') {
              setErrorMessage(null);
              setStaleWarning(false);
              setHasExistingRuns(true);
              await refreshFromRunDetail(savedRunId);
            }
            if (status === 'failed') {
              const errMsg = (resultData as Record<string, unknown>).error_message as string | undefined;
              setErrorMessage(errMsg || 'Pipeline 执行失败');
              setHasExistingRuns(true);
              rememberLatestRunId(savedRunId);
              await refreshFromRunDetail(savedRunId);
              const detailRes = await pipelineService.getRunDetail(savedRunId);
              if (detailRes.data?.extra_metadata?.hitl_gate?.paused) {
                await openHitlGateModal(savedRunId);
              }
            }
          } else if (status === 'human_review_required') {
            await openHitlGateModal(savedRunId);
          } else if (status === 'running') {
            startPolling(savedRunId);
          } else {
            setRunState('idle');
            clearActiveRun(projectId);
            currentRunIdRef.current = null;
            setCurrentRunId(null);
          }
        } catch {
          startPolling(savedRunId);
        }
      };

      checkAndResume();
    } else {
      loadLatestRun();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ========== 清理轮询 ==========
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const loadLatestRun = useCallback(async () => {
    if (!projectId) {
      setHasExistingRuns(null);
      return;
    }
    try {
      const runsRes = await pipelineService.getRuns(projectId);
      if (runsRes.code !== 200 || !runsRes.data || runsRes.data.length === 0) {
        setHasExistingRuns(false);
        return;
      }
      const latestRun = runsRes.data[0];
      rememberLatestRunId(latestRun.run_id);

      const savedRunId = getActiveRunId(projectId);
      if (savedRunId && savedRunId === latestRun.run_id) {
        return;
      }

      const detailRes = await pipelineService.getRunDetail(latestRun.run_id);
      if (detailRes.code !== 200 || !detailRes.data) {
        setHasExistingRuns(false);
        return;
      }
      const runDetail = detailRes.data;
      setHasExistingRuns(true);
      setPipelineRunStatus((runDetail.status as string) ?? null);
      setRunExtraMetadata(runDetail.extra_metadata ?? null);
      setNodes(() => {
        const base = createInitialNodes();
        return base.map((node) => {
          const matchedStage = runDetail.stages?.find((s) => matchStageToNode(s as PipelineStageLog, node));
          return matchedStage ? mergeStageData(node, matchedStage as PipelineStageLog) : node;
        });
      });

      const runStatus = (runDetail.status as string) ?? null;
      const hitlPaused = runDetail.extra_metadata?.hitl_gate?.paused;
      if (hitlPaused || runStatus === 'human_review_required') {
        const gate = runDetail.extra_metadata?.hitl_gate;
        const eventKey = buildHitlGateEventKey(latestRun.run_id, gate);
        if (!hasSeenHitlGateModal(eventKey)) {
          await openHitlGateModal(latestRun.run_id);
        }
      }
    } catch {
      setHasExistingRuns(false);
    }
  }, [projectId, rememberLatestRunId, openHitlGateModal]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  // ========== 用真实 stages 刷新节点（最终刷新） ==========
  const refreshFromRunDetail = useCallback(async (runId: string) => {
    rememberLatestRunId(runId);
    try {
      const detailRes = await pipelineService.getRunDetail(runId);
      if (detailRes.code !== 200 || !detailRes.data) return;
      const runDetail = detailRes.data;
      const runStatus = (runDetail.status as string) ?? null;
      setPipelineRunStatus(runStatus);
      setRunExtraMetadata(runDetail.extra_metadata ?? null);
      const mergedNodes = createInitialNodes().map((node) => {
        const matchedStage = runDetail.stages?.find((s) => matchStageToNode(s as PipelineStageLog, node));
        return matchedStage ? mergeStageData(node, matchedStage as PipelineStageLog) : node;
      });
      setNodes(applyInferredRunningStage(
        mergedNodes,
        runStatus,
        runDetail.stages as PipelineStageLog[] ?? [],
        (runDetail as { current_stage?: string }).current_stage ?? null,
        runDetail.extra_metadata ?? null,
      ));
    } catch {
      /* ignore */
    }
  }, [rememberLatestRunId]);

  // ========== 兼容多种响应格式更新节点 ==========
  const updateNodesFromStages = useCallback((response: unknown) => {
    const stages = extractStagesFromResponse(response);
    const overallStatus = extractRunStatusFromResponse(response);
    const currentStage = extractCurrentStageFromResponse(response);
    const extraMetadata = extractExtraMetadataFromResponse(response);

    if (overallStatus) {
      setPipelineRunStatus(overallStatus);
    }
    if (extraMetadata) {
      setRunExtraMetadata(extraMetadata);
    }

    setNodes((prev) => {
      const base = prev.length > 0 ? prev : createInitialNodes();

      const updated = base.map((node) => {
        const matchedStage = stages.find((s) => matchStageToNode(s, node));
        return matchedStage ? mergeStageData(node, matchedStage) : node;
      });

      return applyInferredRunningStage(
        updated,
        overallStatus,
        stages,
        currentStage,
        extraMetadata,
      );
    });

    if (import.meta.env.DEV && stages.length > 0) {
      stages.forEach((s) => {
        const ns = normalizeStageName(s.stage);
        const nodeId = STAGE_TO_NODE_ID[ns] ?? ns;
        if (!BASE_AGENT_NODES.some((n) => n.id === nodeId)) {
          console.warn(`[WorkflowPage] 未知阶段: "${s.stage}"，不在8个节点定义中`);
        }
      });
    }
  }, []);

  // ========== 检测是否全部 pending ==========
  const isAllPending = useCallback((response: unknown): boolean => {
    const stages = extractStagesFromResponse(response);
    if (stages.length === 0) return true;
    return stages.every((s) => normalizeStatus(s.status) === 'pending');
  }, []);

  // ========== 轮询 Pipeline 状态 ==========
  const startPolling = useCallback(
    (runId: string) => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      consecutiveFailuresRef.current = 0;
      allPendingCountRef.current = 0;
      setRunState('polling');
      setStaleWarning(false);
      setStatusMessage('正在同步阶段状态…');

      const pollOnce = async () => {
        try {
          const response = await pipelineService.getStatus(runId);

          consecutiveFailuresRef.current = 0;
          updateNodesFromStages(response);

          const resAny = response as unknown as Record<string, unknown>;
          const resultData = resAny.data as Record<string, unknown> | undefined;
          const status = resultData?.status as string | undefined;

          if (status === 'completed' || status === 'failed') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setRunState('idle');
            setStaleWarning(false);
            setStatusMessage(null);
            currentRunIdRef.current = null;
            setCurrentRunId(null);
            if (projectId) clearActiveRun(projectId);

            await refreshFromRunDetail(runId);
            setHasExistingRuns(true);

            if (status === 'completed') {
              setErrorMessage(null);
              onPipelineCompleted?.(response as unknown as PipelineRunResult);
            }

            if (status === 'failed') {
              const errMsg = (resultData?.error_message as string)
                || (resultData?.failed_stage
                  ? `执行失败在阶段: ${resultData.failed_stage}`
                  : 'Pipeline 执行失败');
              setErrorMessage(errMsg);
              const detailRes = await pipelineService.getRunDetail(runId);
              if (detailRes.data?.extra_metadata?.hitl_gate?.paused) {
                await openHitlGateModal(runId);
              }
            }
            return;
          }

          if (status === 'human_review_required') {
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            setRunState('idle');
            await openHitlGateModal(runId);
            return;
          }

          if (isAllPending(response)) {
            allPendingCountRef.current += 1;
            if (allPendingCountRef.current >= MAX_ALL_PENDING_POLLS) {
              setStaleWarning(true);
              setStatusMessage(
                'Pipeline 已创建，但后台任务尚未开始，可能是后端任务丢失。请检查后端日志或重新运行。'
              );
            } else if (allPendingCountRef.current >= 3) {
              setStatusMessage('Pipeline 已创建，但后台任务尚未开始，请检查后端日志。');
            }
          } else {
            allPendingCountRef.current = 0;
            setStaleWarning(false);
            setStatusMessage('运行中');
          }
        } catch (err: unknown) {
          consecutiveFailuresRef.current += 1;
          const msg = err instanceof Error ? err.message : String(err);
          console.error(`轮询状态失败 (${consecutiveFailuresRef.current}/${MAX_CONSECUTIVE_POLL_FAILURES}):`, msg);

          setStatusMessage(`正在重试同步状态 (${consecutiveFailuresRef.current}/${MAX_CONSECUTIVE_POLL_FAILURES})`);

          if (consecutiveFailuresRef.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setRunState('idle');
            setStatusMessage(null);
            setCurrentRunId(null);
            currentRunIdRef.current = null;
            if (projectId) clearActiveRun(projectId);
            setErrorMessage('无法获取 Pipeline 状态，请检查后端服务是否仍在运行。');
          }
        }
      };

      void pollOnce();
      pollingRef.current = setInterval(pollOnce, POLL_INTERVAL_MS);
    },
    [updateNodesFromStages, refreshFromRunDetail, onPipelineCompleted, projectId, isAllPending, openHitlGateModal],
  );

  // ========== handleRunAll ==========
  const handleRunAll = useCallback(async () => {
    if (!projectId) {
      setErrorMessage('缺少项目 ID，无法运行真实 Pipeline。');
      return;
    }

    if (!finalResearchQuestion) {
      setErrorMessage('缺少研究问题，请先在研究问题页面填写并保存，或在上方输入框中输入。');
      return;
    }

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    if (projectId) clearActiveRun(projectId);

    setRunState('submitting');
    setErrorMessage(null);
    setStaleWarning(false);
    setStatusMessage(null);
    allPendingCountRef.current = 0;
    consecutiveFailuresRef.current = 0;
    setNodes(createInitialNodes());
    setShowHitlModal(false);
    setHitlGateInfo(null);
    setHitlGateRunId(null);
    hitlModalShownForRunRef.current = null;
    hitlGateEventKeyRef.current = null;

    try {
      console.log('[Pipeline] submitting POST /pipeline/run projectId=', projectId, 'question=', finalResearchQuestion?.slice(0, 50));
      const response = await pipelineService.run(projectId, finalResearchQuestion, loopConfigToRunOptions(loopConfig));
      const result: PipelineRunResult = response.data;

      if (!result || !result.run_id) {
        console.error('[Pipeline] POST response invalid: no run_id', result);
        setErrorMessage('后端返回数据无效，请检查服务状态');
        setRunState('idle');
        return;
      }

      console.log('[Pipeline] start new run', result.run_id, 'status=', result.status);
      setActiveRunId(projectId, result.run_id);
      setCurrentRunId(result.run_id);
      currentRunIdRef.current = result.run_id;
      rememberLatestRunId(result.run_id);
      setRunState('running');
      onPipelineStarted?.(result.run_id);

      startPolling(result.run_id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      console.error('[Pipeline] POST /pipeline/run 失败:', message);
      setErrorMessage(`Pipeline 提交失败: ${message}`);
      setRunState('idle');
    }
  }, [
    projectId,
    finalResearchQuestion,
    startPolling,
    loopConfig,
    rememberLatestRunId,
  ]);

  // ========== 暂停 ==========
  const handlePause = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setRunState('idle');
  }, []);

  // ========== 重置 ==========
  const handleReset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    if (projectId) clearActiveRun(projectId);
    setRunState('idle');
    setErrorMessage(null);
    setStaleWarning(false);
    setStatusMessage(null);
    setCurrentRunId(null);
    currentRunIdRef.current = null;
    allPendingCountRef.current = 0;
    consecutiveFailuresRef.current = 0;
    setLocalResearchQuestion('');
    setNodes(createInitialNodes());
    setSelectedId('');
    setHasExistingRuns(null);
    loadLatestRun();
  }, [loadLatestRun, projectId]);

  // ========== 重新运行 ==========
  const handleRerunFullPipeline = useCallback(
    async () => {
      console.log('[Pipeline] full rerun clicked, projectId=', projectId);
      if (projectId) clearActiveRun(projectId);
      setStaleWarning(false);
      setStatusMessage(null);
      allPendingCountRef.current = 0;
      consecutiveFailuresRef.current = 0;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      await handleRunAll();
    },
    [projectId, handleRunAll],
  );

  const handleRerunCurrentStage = useCallback(
    async (nodeId: string) => {
      if (!projectId) {
        setErrorMessage('缺少项目 ID，无法重跑本阶段。');
        return;
      }
      const parentRunId = resolveRunIdForActions();
      if (!parentRunId) {
        setErrorMessage('未找到可重跑的运行记录，请先运行一次 Pipeline。');
        return;
      }
      const stage = NODE_ID_TO_STAGE[nodeId] || nodeId;
      const nodeName = nodes.find((n) => n.id === nodeId)?.name || stage;
      try {
        setErrorMessage(null);
        setStatusMessage(`正在重新运行「${nodeName}」（仅本智能体，不重启全流程）…`);
        const res = await humanLoopService.rerunFromStage({
          project_id: projectId,
          run_id: parentRunId,
          stage,
          use_human_modified_output: true,
          rerun_mode: 'single_stage',
        });
        if (res.code === 200 && res.data?.run_id) {
          const newRunId = res.data.run_id;
          const inPlace = res.data.in_place ?? (newRunId === parentRunId);
          if (!inPlace) {
            setCurrentRunId(newRunId);
            currentRunIdRef.current = newRunId;
            rememberLatestRunId(newRunId);
            setActiveRunId(projectId, newRunId);
          }
          setRunState('running');
          startPolling(inPlace ? parentRunId : newRunId);
          setStatusMessage(`正在重新运行「${nodeName}」（${inPlace ? '原地更新本阶段' : '从本阶段继续'}）…`);
        } else {
          setStatusMessage(null);
          setErrorMessage(res.message || '本阶段重跑失败');
        }
      } catch (err) {
        console.error('本阶段重跑失败', err);
        setStatusMessage(null);
        setErrorMessage(err instanceof Error ? err.message : '本阶段重跑失败');
      }
    },
    [projectId, nodes, startPolling, resolveRunIdForActions, rememberLatestRunId],
  );

  // ========== 计算状态摘要 ==========
  const effectiveRunId = currentRunId ?? latestRunId;
  const effectiveHitlRunId = hitlGateRunId ?? effectiveRunId;
  const isHitlGatePaused = Boolean(
    projectId
    && effectiveHitlRunId
    && !showHitlModal
    && (
      runExtraMetadata?.hitl_gate?.paused
      || pipelineRunStatus === 'human_review_required'
      || nodes.some((n) => n.status === 'human_review_required')
    ),
  );
  const showIterationHistory = Boolean(
    effectiveRunId
    && selectedNodeId
    && ['report', 'validation', 'hypothesis', 'evaluation'].includes(selectedNodeId),
  );
  const completedCount = nodes.filter((n) => n.status === 'completed').length;
  const failedCount = nodes.filter((n) => n.status === 'failed').length;

  const runningStageName = nodes.find((n) => n.status === 'running')?.name ?? null;
  const failedStageName = nodes.find((n) => n.status === 'failed')?.name ?? null;

  const hitlReviewTarget = useMemo(
    () => getHitlGateReviewTarget(runExtraMetadata?.hitl_gate?.stage ?? hitlGateInfo?.stage),
    [runExtraMetadata?.hitl_gate?.stage, hitlGateInfo?.stage],
  );

  // ========== JSX ==========
  return (
    <div className="max-w-7xl mx-auto">
      {/* 头部 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-bp-text mb-2">智能体工作流</h1>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-bp-muted text-sm">从文献/数据输入到可验证科学假设输出的多智能体闭环</p>
          {projectId && (
            <span className="text-xs bg-bp-cyan-tint text-bp-cyan px-2 py-0.5 rounded-bp border border-bp-cyan/20">
              API Connected
            </span>
          )}
        </div>

        {(researchQuestion || localResearchQuestion) && (
          <p className="text-sm text-bp-muted mt-1 truncate">
            研究问题：{finalResearchQuestion}
          </p>
        )}

        {effectiveRunId && (
          <p className="text-sm text-bp-muted mt-1 truncate font-mono text-xs">
            run_id: {effectiveRunId}
          </p>
        )}

        <div className="mt-4">
          <LoopConfigPanel
            value={loopConfig}
            onChange={setLoopConfig}
            disabled={runState !== 'idle'}
          />
          <p className="text-xs text-bp-muted mt-2">
            {ITERATION_MODE_HINTS[loopConfig.iterationMode]}
          </p>
          {projectId && <WorkflowAdvancedLinks projectId={projectId} />}
        </div>
      </div>

      {/* 研究问题缺失时的兜底输入 */}
      {!researchQuestion && (
        <div className="mb-5 p-4 bg-bp-panel/50 border border-bp-border rounded-bp">
          <p className="text-sm text-bp-yellow font-medium mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            缺少研究问题，请先在研究问题页面填写并保存，或在下方的输入框中直接输入
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={localResearchQuestion}
              onChange={(e) => setLocalResearchQuestion(e.target.value)}
              placeholder="请输入研究问题后运行 Pipeline"
              className="input-field flex-1 py-2 text-sm"
            />
            <Button
              icon={<Send className="w-4 h-4" />}
              variant="primary"
              size="sm"
              disabled={!localResearchQuestion.trim()}
              onClick={() => {
                if (!finalResearchQuestion) {
                  setErrorMessage('请输入研究问题后再运行 Pipeline');
                } else {
                  handleRunAll();
                }
              }}
            >
              提交运行
            </Button>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {errorMessage && (
        <div className="mb-6 p-4 bg-danger-500/10 border border-danger-500/30 rounded-lg flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-danger-500/30 flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-danger-400 text-xs font-bold">!</span>
          </div>
          <div className="flex-1">
            <p className="text-sm text-danger-300 font-medium">执行错误</p>
            <p className="text-sm text-danger-400/80 mt-0.5 whitespace-pre-wrap">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-bp-muted hover:text-bp-text shrink-0"
          >
            <span className="text-xs">✕</span>
          </button>
        </div>
      )}

      {/* 状态栏 */}
      {runState === 'submitting' && (
        <div className="mb-6 p-4 bg-bp-cyan-tint border border-bp-cyan/30 rounded-bp flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-bp-cyan border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-bp-cyan">正在提交 Pipeline 任务…</p>
        </div>
      )}

      {runState === 'running' && !pollingRef.current && (
        <div className="mb-6 p-4 bg-bp-cyan-tint border border-bp-cyan/30 rounded-bp flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-bp-cyan border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-bp-cyan">Pipeline 后台运行中…</p>
        </div>
      )}

      {(runState === 'polling' || runState === 'running') && pollingRef.current && (
        <div className={`mb-6 p-4 rounded-bp flex items-start gap-3 ${
          staleWarning
            ? 'bg-bp-yellow/10 border border-bp-yellow/30'
            : 'bg-bp-cyan-tint border border-bp-cyan/30'
        }`}>
          <div className="w-5 h-5 border-2 border-bp-cyan border-t-transparent rounded-full animate-spin shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className={`text-sm ${staleWarning ? 'text-bp-yellow' : 'text-bp-cyan'} font-medium`}>
              {staleWarning ? (
                <span className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  后台任务可能丢失
                </span>
              ) : statusMessage || '运行中'}
            </p>
            {runningStageName && !staleWarning && (
              <p className="text-xs text-bp-cyan/70 mt-1">正在运行：{runningStageName}</p>
            )}
            {completedCount > 0 && (
              <p className="text-xs text-bp-cyan/70 mt-1">已完成 {completedCount}/{nodes.length} 个阶段</p>
            )}
            {!staleWarning && allPendingCountRef.current >= 3 && !runningStageName && !completedCount && (
              <p className="text-xs text-bp-yellow/80 mt-1">
                Pipeline 已创建，等待后台任务启动...
              </p>
            )}
            {staleWarning && (
              <div className="mt-3">
                <p className="text-xs text-bp-yellow/80 mb-2">
                  {statusMessage}
                </p>
                <Button
                  size="sm"
                  variant="primary"
                  icon={<RefreshCw className="w-4 h-4" />}
                  onClick={handleRerunFullPipeline}
                >
                  重新运行全部流程
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 无运行记录提示 — 只在真正没有历史记录且没有活动运行时显示 */}
      {hasExistingRuns === false && projectId && runState === 'idle' && !currentRunId && (
        <div className="mb-6 p-4 bg-bp-panel/50 border border-bp-border rounded-bp flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-bp-surface flex items-center justify-center shrink-0">
            <span className="text-bp-muted text-sm">—</span>
          </div>
          <div>
            <p className="text-sm text-bp-text font-medium">暂无真实运行记录</p>
            <p className="text-xs text-bp-muted mt-0.5">请点击运行 Pipeline 以启动智能体工作流</p>
          </div>
        </div>
      )}

      {/* 失败时显示 failed stage 信息 */}
      {failedCount > 0 && runState === 'idle' && (
        <div className="mb-6 p-4 bg-danger-500/10 border border-danger-500/30 rounded-lg flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-danger-400 shrink-0" />
          <div>
            <p className="text-sm text-danger-300 font-medium">
              执行失败{failedStageName ? `于: ${failedStageName}` : ''}
            </p>
            {errorMessage && (
              <p className="text-xs text-danger-400/80 mt-1">{errorMessage}</p>
            )}
            <div className="mt-2">
              <Button
                size="sm"
                variant="primary"
                icon={<RefreshCw className="w-4 h-4" />}
                onClick={handleRerunFullPipeline}
              >
                重新运行全部流程
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* HITL 暂停提示条 */}
      {isHitlGatePaused && effectiveHitlRunId && projectId && (
        <div className="mb-6 p-4 bg-bp-yellow/10 border border-bp-yellow/30 rounded-bp flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-bp-yellow font-medium">{hitlReviewTarget.continueTitle}</p>
            <p className="text-xs text-bp-muted mt-1">{hitlReviewTarget.continueDescription}</p>
          </div>
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleGoToHitlReview(hitlReviewTarget.tab)}
            className="gap-1.5 shrink-0"
          >
            {hitlReviewTarget.ctaLabel}
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      )}

      {/* 操作栏 */}
      <div className="mb-6">
        <WorkflowActionBar
          nodes={nodes}
          isRunning={runState !== 'idle'}
          onRunAll={handleRunAll}
          onPause={handlePause}
          onReset={handleReset}
        />
      </div>

      {projectId && (
        <CollapsiblePanel title="运行历史" subtitle="阶段执行记录 · 模型参数 · 输入输出快照" defaultOpen={false} className="mb-6">
          <RunHistoryPanel
            projectId={projectId}
            latestRunId={effectiveRunId}
            refreshKey={completedCount + (effectiveRunId?.length ?? 0)}
          />
        </CollapsiblePanel>
      )}

      {/* 主布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：节点列表 */}
        <div className="lg:col-span-1">
          <Card
            title="Pipeline 节点"
            subtitle={`共 ${nodes.length} 个智能体` + (completedCount > 0 ? ` · 已完成 ${completedCount}/${nodes.length}` : '')}
            className="max-h-[calc(100vh-300px)] overflow-y-auto"
          >
            <div className="space-y-0">
              {nodes.map((node, idx) => (
                <AgentNode
                  key={node.id}
                  node={node}
                  isSelected={node.id === selectedId}
                  isLast={idx === nodes.length - 1}
                  stepNumber={idx + 1}
                  onClick={() => handleSelect(node.id)}
                />
              ))}
            </div>
          </Card>
        </div>

        {/* 右侧：详情 + 收拢辅助面板 */}
        <div className="lg:col-span-2 space-y-4">
          <AgentDetailPanel node={selectedNode} onRerun={handleRerunCurrentStage} />

          {selectedNodeId === 'validation' && validationPendingPreview && (
            <Card title="待验证方案" subtitle="实验设计已完成，小样验证尚未产出结果时将显示此处预览">
              <div className="p-3 rounded-bp border bg-bp-cyan/5 border-bp-cyan/20 space-y-2 text-sm text-bp-text">
                {typeof validationPendingPreview.hypothesis === 'string' && validationPendingPreview.hypothesis && (
                  <p><span className="text-bp-muted">假设：</span>{validationPendingPreview.hypothesis}</p>
                )}
                {typeof validationPendingPreview.methods === 'string' && validationPendingPreview.methods && (
                  <p><span className="text-bp-muted">方法：</span>{validationPendingPreview.methods.slice(0, 280)}{validationPendingPreview.methods.length > 280 ? '…' : ''}</p>
                )}
                {typeof validationPendingPreview.expected_results === 'string' && validationPendingPreview.expected_results && (
                  <p><span className="text-bp-muted">预期结果：</span>{validationPendingPreview.expected_results.slice(0, 280)}{validationPendingPreview.expected_results.length > 280 ? '…' : ''}</p>
                )}
              </div>
            </Card>
          )}

          {showIterationHistory && (
            <CollapsiblePanel title="迭代历史" subtitle="里程碑 · 时间线 · 版本对比" defaultOpen>
              <IterationHistoryPanel
                runId={effectiveRunId}
                extraMetadata={runExtraMetadata}
                federatedPilot={federatedPilot}
              />
            </CollapsiblePanel>
          )}

          {selectedNodeId === 'validation' && validationDataGuidance && (
            <CollapsiblePanel title="数据不匹配 · 所需数据集" defaultOpen>
              <ValidationDataGuidanceCard
                guidance={validationDataGuidance}
                blockedReason={validationBlockedReason || undefined}
              />
            </CollapsiblePanel>
          )}

          {selectedNodeId === 'validation' && validationExecutionMeta && (
            <CollapsiblePanel title="执行层级" defaultOpen={false}>
              <ExecutionTierBadge {...validationExecutionMeta} />
            </CollapsiblePanel>
          )}

          {selectedNodeId === 'validation' && verifiableValidation && (
            <CollapsiblePanel
              title={verifiableValidation.isPreview ? '可验证性检查（实验设计预览）' : '可验证性检查'}
              defaultOpen={false}
            >
              <VerifiableChecksPanel
                checks={verifiableValidation.checks}
                passed={verifiableValidation.passed ?? null}
                spec={verifiableValidation.spec}
              />
            </CollapsiblePanel>
          )}

          {plotQualityData && selectedNodeId && (selectedNodeId === 'validation' || selectedNodeId === 'report') && (
            <CollapsiblePanel title="小样验证图表质量检查" defaultOpen={false}>
              <PlotCritiquePanel plotQuality={plotQualityData} />
            </CollapsiblePanel>
          )}

          {projectId && effectiveRunId && selectedNode && (
            <CollapsiblePanel
              title="阶段人工介入"
              subtitle={selectedNode.name}
              defaultOpen={selectedNode.status === 'human_review_required' || selectedNode.status === 'human_review'}
            >
              <StageHumanLoopPanel
                projectId={projectId}
                runId={effectiveRunId}
                nodeId={selectedNode.id}
                researchQuestion={researchQuestion}
                inputData={selectedNode.input_data}
                outputData={selectedNode.output_data}
                humanModifiedOutput={selectedNode.human_modified_output}
                humanReviewed={selectedNode.human_reviewed}
                humanFeedback={selectedNode.human_feedback}
                editedAt={selectedNode.edited_at}
                revisionHistory={selectedNode.revision_history}
                chatHistory={selectedNode.chat_history as Array<Record<string, unknown>> | undefined}
                onUpdated={() => {
                  refreshFromRunDetail(effectiveRunId);
                  onHumanLoopUpdated?.(NODE_ID_TO_STAGE[selectedNode.id] || selectedNode.id);
                }}
                onRerunStarted={(runIdForPoll) => {
                  if (runIdForPoll !== currentRunIdRef.current) {
                    setCurrentRunId(runIdForPoll);
                    currentRunIdRef.current = runIdForPoll;
                    rememberLatestRunId(runIdForPoll);
                    if (projectId) setActiveRunId(projectId, runIdForPoll);
                  }
                  startPolling(runIdForPoll);
                }}
              />
            </CollapsiblePanel>
          )}
        </div>
      </div>

      <HitlGateModal
        open={showHitlModal}
        gate={hitlGateInfo}
        onDismiss={handleDismissHitlModal}
        onGoReview={handleGoToHitlReview}
      />
    </div>
  );
}