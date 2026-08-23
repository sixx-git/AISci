import { mapStageExecutionStatus, normalizePipelineStageKey } from '@/lib/pipelineProgressNodes';
import type {
  ClosedLoopDecision,
  ClosedLoopEvent,
  PipelineRunDetail,
  PipelineStageExecutionSummary,
  ProjectOverview,
  QualityTrendEntry,
} from '@/types';

export interface SnapshotItem {
  id?: string;
  title: string;
  detail?: string;
  source?: string;
  /** 白名单分层：核心可引用 / 辅助材料 */
  tier?: 'core' | 'auxiliary';
}

export interface QwenUsageRow {
  label: string;
  value: string;
}

export interface LiteratureInventory {
  facts: number;
  core_facts: number;
  auxiliary_facts: number;
  evidence_quotes: number;
  source_papers: number;
  citation_map: number;
  search_candidates: number;
  imported: number;
  selected: number;
  uncertain_points: number;
  warning?: string;
}

export interface ContextSnapshot {
  project_id: string;
  run_id: string | null;
  generated_at: string;
  research_question: string;
  literature: LiteratureInventory;
  whitelist_core: SnapshotItem[];
  whitelist_auxiliary: SnapshotItem[];
  channels: {
    question: SnapshotItem[];
    existing_evidence: SnapshotItem[];
    opposing_evidence: SnapshotItem[];
    constraints: SnapshotItem[];
    history: SnapshotItem[];
    feedback: SnapshotItem[];
  };
  qwen: QwenUsageRow[];
}

export interface StageOutputSnapshot {
  key: string;
  label: string;
  status: string;
  model?: string;
  token_count?: number | null;
  duration_ms?: number | null;
  highlights: SnapshotItem[];
  output: Record<string, unknown>;
}

export const EXPERIMENT_STAGE_KEYS = [
  'iterative_experiment',
  'experiment_design',
  'small_validation',
] as const;

export function isExperimentStageKey(key: string): boolean {
  return (EXPERIMENT_STAGE_KEYS as readonly string[]).includes(key);
}

export const STAGE_DISPLAY_ORDER = [
  'problem_understanding',
  'literature_mining',
  'data_acquisition',
  'knowledge_gap',
  'hypothesis_generation',
  'hypothesis_review',
  'iterative_experiment',
  'experiment_design',
  'small_validation',
  'report_generation',
] as const;

export interface FeedbackLoopItem {
  id: string;
  label: string;
  fromLabel: string;
  toLabel: string;
  fired: boolean;
  evidence?: string;
}

export interface FailureRow {
  situation: string;
  detected: string;
  handling: string;
  occurred: boolean;
  evidence?: string;
}

export interface RunFeedbackSnapshot {
  project_id: string;
  run_id: string | null;
  generated_at: string;
  run_status: string;
  auto_feedback: SnapshotItem[];
  human_feedback: SnapshotItem[];
  loops: FeedbackLoopItem[];
  failures: FailureRow[];
  events: ClosedLoopEvent[];
}

const STAGE_CN: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  data_acquisition: '数据采集',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '假设评估',
  iterative_experiment: '迭代实验',
  experiment_design: '迭代实验',
  small_validation: '迭代实验',
  report_generation: '报告生成',
};

const HUMAN_EVENT_TYPES = new Set([
  'hitl_gate_pause',
  'hitl_gate',
  'human_feedback',
]);

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function stageKey(stage: PipelineStageExecutionSummary | { stage?: string }): string {
  return normalizePipelineStageKey(stage.stage);
}

function findStage(
  stages: PipelineStageExecutionSummary[] | undefined,
  key: string,
): PipelineStageExecutionSummary | undefined {
  return (stages || []).find((s) => stageKey(s) === key);
}

function stageOutput(stage?: PipelineStageExecutionSummary): Record<string, unknown> {
  return asRecord(stage?.output_data) || {};
}

function textFromFact(item: unknown): SnapshotItem | null {
  const rec = asRecord(item);
  if (!rec) {
    const raw = asString(item);
    return raw ? { title: raw } : null;
  }
  const title =
    asString(rec.content)
    || asString(rec.fact_text)
    || asString(rec.claim)
    || asString(rec.text)
    || asString(rec.quote_text);
  if (!title) return null;
  const id = asString(rec.fact_id) || asString(rec.evidence_id) || undefined;
  const source =
    asString(rec.source_paper_title)
    || asString(rec.source_title)
    || asString(rec.source_chunk_id)
    || undefined;
  const detail = [
    id ? `fact_id=${id}` : '',
    asString(rec.source_chunk_id) ? `chunk=${asString(rec.source_chunk_id)}` : '',
  ].filter(Boolean).join(' · ') || undefined;
  const srcKind = asString(rec.source).toLowerCase();
  const explicitTier = asString(rec.tier).toLowerCase();
  let tier: SnapshotItem['tier'] = 'core';
  if (explicitTier === 'auxiliary' || explicitTier === 'core') {
    tier = explicitTier;
  } else if (rec.no_pdf === true) {
    tier = 'auxiliary';
  } else if (
    srcKind === 'vector_chunk'
    || srcKind === 'chunk'
    || srcKind === 'abstract_fallback'
    || srcKind === 'retrieved_paper'
    || srcKind === 'source_paper'
    || srcKind === 'project_library'
    || srcKind === 'rcs_rejected_chunk'
    || srcKind.includes('abstract')
  ) {
    tier = 'auxiliary';
  }
  return { id, title, detail, source, tier };
}

function textFromCounter(item: unknown): SnapshotItem | null {
  const rec = asRecord(item);
  if (!rec) {
    const raw = asString(item);
    return raw ? { title: raw } : null;
  }
  const title =
    asString(rec.claim)
    || asString(rec.quote_or_summary)
    || asString(rec.fact_text)
    || asString(rec.text)
    || asString(rec.weakness);
  if (!title) return null;
  return {
    id: asString(rec.evidence_id) || undefined,
    title,
    detail: asString(rec.stance_reason) || asString(rec.stance) || undefined,
    source: asString(rec.source_title) || undefined,
  };
}

function collectWhitelistFacts(stages: PipelineStageExecutionSummary[]): {
  core: SnapshotItem[];
  auxiliary: SnapshotItem[];
} {
  const lit = stageOutput(findStage(stages, 'literature_mining'));
  const core: SnapshotItem[] = [];
  const auxiliary: SnapshotItem[] = [];

  for (const fact of asArray(lit.facts)) {
    const item = textFromFact(fact);
    if (!item) continue;
    if (item.tier === 'auxiliary') auxiliary.push(item);
    else core.push({ ...item, tier: 'core' });
  }

  for (const ev of asArray(lit.evidence)) {
    const rec = asRecord(ev);
    const title = rec
      ? (asString(rec.quote_text) || asString(rec.content) || asString(rec.text) || asString(rec.snippet))
      : asString(ev);
    if (!title) continue;
    auxiliary.push({
      title,
      source: rec
        ? (asString(rec.source_paper_title) || asString(rec.source_title) || '证据原文')
        : '证据原文',
      detail: rec && asString(rec.source_chunk_id)
        ? `chunk=${asString(rec.source_chunk_id)}`
        : '原文摘句',
      id: rec ? (asString(rec.evidence_id) || asString(rec.source_chunk_id) || undefined) : undefined,
      tier: 'auxiliary',
    });
  }

  for (const paper of [...asArray(lit.source_papers), ...asArray(lit.retrieved_papers)]) {
    const rec = asRecord(paper);
    const title = rec
      ? (asString(rec.title) || asString(rec.paper_title) || asString(rec.source_title))
      : asString(paper);
    if (!title) continue;
    const year = rec ? asString(rec.year) : '';
    const authors = rec ? asString(rec.authors) : '';
    auxiliary.push({
      title,
      source: rec ? (asString(rec.venue) || '来源论文') : '来源论文',
      detail: [authors, year].filter(Boolean).join(' · ') || '论文元数据',
      id: rec ? (asString(rec.document_id) || asString(rec.paper_id) || undefined) : undefined,
      tier: 'auxiliary',
    });
  }

  const cmap = asRecord(lit.citation_map) || {};
  for (const [cid, raw] of Object.entries(cmap)) {
    const rec = asRecord(raw);
    const title = rec
      ? (asString(rec.title) || asString(rec.paper_title) || cid)
      : asString(raw) || cid;
    const chunks = rec ? asArray(rec.chunk_ids).map((x) => asString(x)).filter(Boolean) : [];
    auxiliary.push({
      title,
      source: '引用映射',
      detail: chunks.length > 0 ? `chunk_ids=${chunks.slice(0, 6).join(',')}` : `citation_id=${cid}`,
      id: rec ? (asString(rec.document_id) || cid) : cid,
      tier: 'auxiliary',
    });
  }

  return {
    core: dedupeItems(core),
    auxiliary: dedupeItems(auxiliary),
  };
}

/** 从 citation_map / 论文元数据抽出可拉取 chunk 的文档 ID */
export function collectLiteratureDocumentIds(run: PipelineRunDetail | null): string[] {
  const lit = stageOutput(findStage(run?.stages, 'literature_mining'));
  const ids = new Set<string>();
  const cmap = asRecord(lit.citation_map) || {};
  for (const raw of Object.values(cmap)) {
    const rec = asRecord(raw);
    const id = rec ? asString(rec.document_id) : '';
    if (id) ids.add(id);
  }
  for (const paper of [...asArray(lit.source_papers), ...asArray(lit.retrieved_papers)]) {
    const rec = asRecord(paper);
    const id = rec ? (asString(rec.document_id) || asString(rec.id)) : '';
    if (id) ids.add(id);
  }
  return [...ids];
}

export function appendAuxiliaryWhitelist(
  snapshot: ContextSnapshot,
  extras: SnapshotItem[],
): ContextSnapshot {
  if (extras.length === 0) return snapshot;
  const auxiliary = dedupeItems([...snapshot.whitelist_auxiliary, ...extras]);
  return {
    ...snapshot,
    whitelist_auxiliary: auxiliary,
    literature: {
      ...snapshot.literature,
      auxiliary_facts: auxiliary.length,
    },
    channels: {
      ...snapshot.channels,
      existing_evidence: [...snapshot.whitelist_core, ...auxiliary],
    },
  };
}

function numField(rec: Record<string, unknown>, ...keys: string[]): number {
  for (const key of keys) {
    const val = rec[key];
    if (typeof val === 'number' && Number.isFinite(val)) return val;
    if (Array.isArray(val)) return val.length;
  }
  return 0;
}

function collectLiteratureInventory(stages: PipelineStageExecutionSummary[]): LiteratureInventory {
  const lit = stageOutput(findStage(stages, 'literature_mining'));
  const warning = asString(lit.warning) || undefined;
  const whitelist = collectWhitelistFacts(stages);
  const coreRaw = lit.core_facts_count;
  const auxRaw = lit.auxiliary_facts_count;
  return {
    facts: numField(lit, 'evidence_facts', 'facts_count', 'facts'),
    core_facts: typeof coreRaw === 'number' && Number.isFinite(coreRaw) ? coreRaw : whitelist.core.length,
    auxiliary_facts: typeof auxRaw === 'number' && Number.isFinite(auxRaw) ? auxRaw : whitelist.auxiliary.length,
    evidence_quotes: numField(lit, 'evidence_count', 'evidence'),
    source_papers: numField(lit, 'source_papers_count', 'source_papers', 'retrieved_papers'),
    citation_map: numField(lit, 'citation_map_count', 'verified_references_count', 'citation_map'),
    search_candidates: numField(lit, 'literature_search_count', 'candidate_references_count'),
    imported: numField(lit, 'literature_import_count', 'imported_documents'),
    selected: numField(lit, 'literature_selected_count'),
    uncertain_points: numField(lit, 'uncertain_points_count', 'uncertain_points'),
    warning,
  };
}

function collectOpposing(stages: PipelineStageExecutionSummary[]): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  const lit = stageOutput(findStage(stages, 'literature_mining'));
  for (const point of asArray(lit.uncertain_points)) {
    const title = asString(point);
    if (title) items.push({ title, source: '文献不确定点' });
  }
  const gap = stageOutput(findStage(stages, 'knowledge_gap'));
  for (const c of asArray(gap.contradictions)) {
    const rec = asRecord(c);
    const title = rec
      ? (asString(rec.description) || asString(rec.contradiction) || asString(rec.text) || asString(rec.title))
      : asString(c);
    if (title) items.push({ title, source: '知识缺口矛盾' });
  }

  const hypoOut = stageOutput(findStage(stages, 'hypothesis_generation'));
  for (const h of asArray(hypoOut.hypotheses)) {
    const rec = asRecord(h);
    if (!rec) continue;
    const chain = asRecord(rec.evidence_chain);
    for (const c of asArray(chain?.counter_evidence || rec.counter_evidence)) {
      const item = textFromCounter(c);
      if (item) items.push(item);
    }
  }

  const review = stageOutput(findStage(stages, 'hypothesis_review'));
  for (const r of asArray(review.reviews)) {
    const rec = asRecord(r);
    if (!rec) continue;
    for (const w of asArray(rec.weaknesses)) {
      const title = asString(w);
      if (title) items.push({ title, source: '评审弱点' });
    }
  }
  return dedupeItems(items);
}

function collectConstraints(
  project: ProjectOverview,
  stages: PipelineStageExecutionSummary[],
): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  if (project.constraints) {
    items.push({ title: project.constraints, source: '项目约束' });
  }
  const problem = stageOutput(findStage(stages, 'problem_understanding'));
  const problemConstraints =
    asString(problem.constraints)
    || asString(problem.boundary)
    || asString(asRecord(problem.structured_problem)?.constraints);
  if (problemConstraints) {
    items.push({ title: problemConstraints, source: '问题理解' });
  }
  const gap = stageOutput(findStage(stages, 'knowledge_gap'));
  for (const g of asArray(gap.knowledge_gaps)) {
    const rec = asRecord(g);
    const title = rec
      ? (asString(rec.description) || asString(rec.gap) || asString(rec.title))
      : asString(g);
    if (title) items.push({ title, source: '知识缺口' });
  }
  return dedupeItems(items);
}

function collectHistory(
  stages: PipelineStageExecutionSummary[],
  extra: Record<string, unknown> | null,
): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  const trend = asArray(extra?.quality_trend) as QualityTrendEntry[];
  for (const entry of trend.slice(-8)) {
    const rec = asRecord(entry) || {};
    const stage = asString(rec.stage) || asString(entry.stage);
    const label = STAGE_CN[normalizePipelineStageKey(stage)] || stage || '门禁';
    const passed = rec.passed === true || entry.passed === true;
    const score = rec.score ?? entry.score;
    items.push({
      title: `${label} · ${passed ? '通过' : '未通过'}`,
      detail: score != null ? `评分 ${String(score)}` : asString(rec.gate_label || entry.gate_label) || undefined,
      source: '质量趋势',
    });
  }
  for (const stage of stages) {
    if (!stage.completed_at && !stage.duration_ms) continue;
    const key = stageKey(stage);
    const label = STAGE_CN[key] || stage.stage;
    items.push({
      title: `${label} · ${stage.status}`,
      detail: [
        stage.duration_ms != null ? `${Math.round(stage.duration_ms / 1000)}s` : '',
        stage.token_count != null ? `${stage.token_count} tokens` : '',
        stage.model_used || '',
      ].filter(Boolean).join(' · ') || undefined,
      source: '阶段执行',
    });
  }
  return items;
}

function collectHumanFeedback(
  stages: PipelineStageExecutionSummary[],
  extra: Record<string, unknown> | null,
): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  for (const stage of stages) {
    const meta = asRecord(stage.extra_metadata);
    const feedback = asString(stage.human_feedback) || asString(meta?.human_feedback);
    if (feedback) {
      items.push({
        title: feedback,
        source: STAGE_CN[stageKey(stage)] || stage.stage,
        detail: stage.human_reviewed ? '已人工审核' : undefined,
      });
    }
    const chats = asArray(stage.chat_history).length > 0
      ? asArray(stage.chat_history)
      : asArray(meta?.chat_history);
    for (const chat of chats) {
      const rec = asRecord(chat);
      const msg = rec ? (asString(rec.user_message) || asString(rec.message)) : asString(chat);
      if (msg) {
        items.push({
          title: msg,
          source: `${STAGE_CN[stageKey(stage)] || stage.stage} · 对话`,
        });
      }
    }
  }
  const gate = asRecord(extra?.hitl_gate);
  if (gate) {
    const title = [
      asString(gate.stage_label) || asString(gate.stage),
      asString(gate.last_action),
    ].filter(Boolean).join(' · ');
    if (title) {
      items.push({
        title: gate.paused ? `HITL 暂停：${title}` : `HITL：${title}`,
        source: '人工在回路',
        detail: asString(gate.paused_at) || undefined,
      });
    }
  }
  return dedupeItems(items);
}

function collectAutoFeedback(
  extra: Record<string, unknown> | null,
  stages: PipelineStageExecutionSummary[],
): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  const events = asArray(extra?.closed_loop_events) as ClosedLoopEvent[];
  for (const evt of events) {
    if (HUMAN_EVENT_TYPES.has(evt.type)) continue;
    items.push({
      title: asString(evt.summary) || evt.type,
      source: evt.type,
      detail: [evt.decision, evt.at].filter(Boolean).map(String).join(' · ') || undefined,
    });
  }
  const decisions = asArray(extra?.closed_loop_decisions) as ClosedLoopDecision[];
  for (const d of decisions) {
    const actor = asString(d.actor).toLowerCase();
    if (actor === 'human' || actor === 'user' || actor === 'researcher') continue;
    items.push({
      title: asString(d.reason) || asString(d.action) || asString(d.trigger) || '自动决策',
      source: asString(d.trigger) || '闭环决策',
      detail: asString(d.action) || undefined,
    });
  }
  for (const stage of stages) {
    if (stage.error_message) {
      items.push({
        title: stage.error_message,
        source: `${STAGE_CN[stageKey(stage)] || stage.stage} · 失败`,
      });
    }
  }
  return dedupeItems(items);
}

function dedupeItems(items: SnapshotItem[]): SnapshotItem[] {
  const seen = new Set<string>();
  const out: SnapshotItem[] = [];
  for (const item of items) {
    const key = `${item.title}|${item.source || ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function buildQwenRows(stages: PipelineStageExecutionSummary[]): QwenUsageRow[] {
  const models = [...new Set(
    stages.map((s) => asString(s.model_used)).filter(Boolean),
  )];
  const tasks = stages
    .filter((s) => s.model_used || s.prompt_used)
    .map((s) => STAGE_CN[stageKey(s)] || s.stage);
  const uniqueTasks = [...new Set(tasks)];
  const whitelist = collectWhitelistFacts(stages);
  const factCount = whitelist.core.length;
  const auxCount = whitelist.auxiliary.length;
  return [
    {
      label: '使用的 Qwen 模型与调用方式',
      value: models.length > 0
        ? `${models.join('、')}，经阿里云百炼 DashScope 调用`
        : 'Qwen 系列，经阿里云百炼 DashScope 调用',
    },
    {
      label: 'Qwen 承担的具体任务',
      value: uniqueTasks.length > 0
        ? uniqueTasks.join('、')
        : '各阶段智能体的生成、评审与结构化抽取',
    },
    {
      label: '一次生成时提供给模型的上下文',
      value: `阶段提示词 + 强置信核心白名单（${factCount} 条）+ 辅助性非核心白名单（${auxCount} 条）+ 全局约束 + 当前阶段输入 + 历史审计摘要`,
    },
    {
      label: '结构化输出或格式约束',
      value: 'Pydantic JSON Schema 强制输出结构；引用须绑定 fact_id / source_chunk_id',
    },
    {
      label: '与检索、代码或其他工具的协作方式',
      value: '向量检索 / arXiv / PDF 解析 / 沙箱实验以 Skill 被智能体调用；Qwen 负责推理，工具负责执行',
    },
  ];
}

export function buildContextSnapshot(
  project: ProjectOverview,
  run: PipelineRunDetail | null,
  researchQuestion: string,
): ContextSnapshot {
  const stages = run?.stages || [];
  const extra = asRecord(run?.extra_metadata);
  const whitelist = collectWhitelistFacts(stages);
  return {
    project_id: project.id,
    run_id: run?.run_id || null,
    generated_at: new Date().toISOString(),
    research_question: researchQuestion || run?.research_question || project.research_question || '',
    literature: collectLiteratureInventory(stages),
    whitelist_core: whitelist.core,
    whitelist_auxiliary: whitelist.auxiliary,
    channels: {
      question: [{
        title: researchQuestion || run?.research_question || project.research_question || '（尚未填写研究问题）',
        source: '科学问题',
      }],
      existing_evidence: [...whitelist.core, ...whitelist.auxiliary],
      opposing_evidence: collectOpposing(stages),
      constraints: collectConstraints(project, stages),
      history: collectHistory(stages, extra),
      feedback: collectHumanFeedback(stages, extra),
    },
    qwen: buildQwenRows(stages),
  };
}

function eventFired(events: ClosedLoopEvent[], types: string[]): { fired: boolean; evidence?: string } {
  const hit = events.find((e) => types.includes(e.type));
  if (!hit) return { fired: false };
  return {
    fired: true,
    evidence: asString(hit.summary) || hit.type,
  };
}

export function buildRunFeedbackSnapshot(
  project: ProjectOverview,
  run: PipelineRunDetail | null,
): RunFeedbackSnapshot {
  const stages = run?.stages || [];
  const extra = asRecord(run?.extra_metadata);
  const events = asArray(extra?.closed_loop_events) as ClosedLoopEvent[];
  const evidence = eventFired(events, [
    'evidence_reasoning_loop',
    'discovery_literature_refresh',
    'data_gap_loop',
  ]);
  const reviewFail = (() => {
    const hit = events.find((e) => {
      if (e.type === 'quality_acceptance') {
        const decision = asString(e.decision).toLowerCase();
        return Boolean(decision) && decision !== 'accept';
      }
      return e.type === 'teaching_auto_refinement' || e.type === 'discovery_refine';
    });
    if (!hit) return { fired: false as const, evidence: undefined as string | undefined };
    return { fired: true as const, evidence: asString(hit.summary) || hit.type };
  })();
  const sandbox = events.find((e) => e.type === 'sandbox_validation' && e.success === false);
  const expStage = findStage(stages, 'iterative_experiment')
    || findStage(stages, 'experiment_design')
    || findStage(stages, 'small_validation');
  const scriptFailed = Boolean(sandbox)
    || mapStageExecutionStatus(expStage?.status) === 'error'
    || Boolean(expStage?.error_message);

  return {
    project_id: project.id,
    run_id: run?.run_id || null,
    generated_at: new Date().toISOString(),
    run_status: run?.status || 'idle',
    auto_feedback: collectAutoFeedback(extra, stages),
    human_feedback: collectHumanFeedback(stages, extra),
    loops: [
      {
        id: 'evidence-refresh',
        label: '证据弱 → 补文献重跑',
        fromLabel: '假设评估',
        toLabel: '文献挖掘',
        fired: evidence.fired,
        evidence: evidence.evidence,
      },
      {
        id: 'review-revise',
        label: '评审不通过 → 修订假设',
        fromLabel: '假设评估',
        toLabel: '假设生成',
        fired: reviewFail.fired,
        evidence: reviewFail.evidence,
      },
      {
        id: 'script-redesign',
        label: '脚本失败 → 重设计再运行',
        fromLabel: '迭代实验',
        toLabel: '迭代实验',
        fired: scriptFailed,
        evidence: sandbox
          ? asString(sandbox.summary) || '沙箱执行失败'
          : expStage?.error_message || undefined,
      },
      {
        id: 'hitl-constraint',
        label: '人工反馈 → 全局约束池',
        fromLabel: '任意阶段',
        toLabel: '后续轮次',
        fired: collectHumanFeedback(stages, extra).length > 0,
      },
    ],
    failures: [
      {
        situation: '证据不足（证据弱）',
        detected: '假设缺乏足够证据支撑',
        handling: '自动补文献检索 → 重建证据链 → 重跑假设树',
        occurred: evidence.fired,
        evidence: evidence.evidence,
      },
      {
        situation: '评审不通过',
        detected: '候选假设未达集成门禁阈值',
        handling: '科学自迭代修订，或降级淘汰',
        occurred: reviewFail.fired,
        evidence: reviewFail.evidence,
      },
      {
        situation: '实验脚本不可执行 / 外部失败',
        detected: '数据列不匹配、脚本报错，或接口超时',
        handling: '可执行性门禁驳回 → 脚本重设计；外部失败自动重试',
        occurred: scriptFailed,
        evidence: sandbox
          ? asString(sandbox.summary) || '沙箱执行失败'
          : expStage?.error_message || undefined,
      },
    ],
    events,
  };
}

function pushHighlight(items: SnapshotItem[], title: string, source?: string, detail?: string) {
  const t = title.trim();
  if (!t) return;
  items.push({ title: t, source, detail });
}

function highlightsForStage(key: string, output: Record<string, unknown>): SnapshotItem[] {
  const items: SnapshotItem[] = [];
  if (key === 'problem_understanding') {
    pushHighlight(items, asString(output.problem_statement), '问题陈述');
    pushHighlight(items, asString(output.main_contradiction), '主要矛盾');
    const kws = asArray(output.keywords).map((v) => asString(v)).filter(Boolean);
    if (kws.length) pushHighlight(items, kws.join('、'), '关键词');
    const ro = asRecord(output.research_object);
    if (ro) {
      pushHighlight(items, [
        asString(ro.internal) && `内部 ${asString(ro.internal)}`,
        asString(ro.external) && `外部 ${asString(ro.external)}`,
        asString(ro.boundary) && `边界 ${asString(ro.boundary)}`,
      ].filter(Boolean).join('；'), '研究对象');
    }
    for (const c of asArray(output.constraints)) {
      pushHighlight(items, asString(c), '约束');
    }
  } else if (key === 'literature_mining') {
    const facts = asArray(output.facts);
    pushHighlight(items, `事实白名单 ${facts.length} 条`, 'facts');
    pushHighlight(
      items,
      `检索候选 ${numField(output, 'literature_search_count')} · 入库 ${numField(output, 'literature_import_count', 'imported_documents')} · 引用映射 ${numField(output, 'citation_map_count', 'citation_map')}`,
      '检索/入库',
    );
    for (const f of facts.slice(0, 6)) {
      const item = textFromFact(f);
      if (item) items.push({ ...item, source: item.source || 'fact' });
    }
      for (const paper of asArray(output.source_papers).slice(0, 6)) {
      const rec = asRecord(paper);
      const title = rec
        ? (asString(rec.paper_title) || asString(rec.title))
        : asString(paper);
      pushHighlight(items, title, '来源论文');
    }
    for (const ev of asArray(output.evidence).slice(0, 4)) {
      const rec = asRecord(ev);
      pushHighlight(items, rec ? (asString(rec.text) || asString(rec.quote_text)) : asString(ev), '证据原文');
    }
  } else if (key === 'knowledge_gap') {
    for (const g of asArray(output.knowledge_gaps).slice(0, 8)) {
      const rec = asRecord(g);
      pushHighlight(items, rec ? (asString(rec.description) || asString(rec.gap) || asString(rec.title)) : asString(g), '知识缺口');
    }
    for (const c of asArray(output.contradictions).slice(0, 4)) {
      const rec = asRecord(c);
      pushHighlight(items, rec ? (asString(rec.description) || asString(rec.contradiction)) : asString(c), '矛盾');
    }
    for (const o of asArray(output.research_opportunities).slice(0, 4)) {
      const rec = asRecord(o);
      pushHighlight(items, rec ? (asString(rec.description) || asString(rec.title)) : asString(o), '研究机会');
    }
  } else if (key === 'hypothesis_generation') {
    for (const h of asArray(output.hypotheses).slice(0, 8)) {
      const rec = asRecord(h);
      if (!rec) continue;
      const ids = asArray(rec.supporting_fact_ids).map((v) => asString(v)).filter(Boolean);
      pushHighlight(
        items,
        asString(rec.hypothesis) || asString(rec.core_claim) || asString(rec.statement),
        rec.off_topic ? '偏题假设' : '候选假设',
        ids.length ? `supporting_fact_ids: ${ids.join(', ')}` : asString(rec.evidence_level) || undefined,
      );
      const chain = asRecord(rec.evidence_chain);
      if (chain) {
        const support = asArray(chain.supporting_evidence).length;
        const counter = asArray(chain.counter_evidence).length;
        pushHighlight(items, `证据链 支持 ${support} / 反对 ${counter}`, 'evidence_chain');
      }
    }
    pushHighlight(items, asString(output.summary), '生成摘要');
  } else if (key === 'hypothesis_review') {
    for (const r of asArray(output.reviews).slice(0, 8)) {
      const rec = asRecord(r);
      if (!rec) continue;
      const scores = asRecord(rec.scores) || rec;
      const overall = rec.overall_score ?? asRecord(scores)?.overall_score;
      pushHighlight(
        items,
        asString(rec.recommendation) || asString(rec.summary) || `假设 #${asString(rec.hypothesis_index)}`,
        '评审',
        overall != null ? `综合 ${String(overall)}` : undefined,
      );
    }
    if (output.primary_index != null) {
      pushHighlight(items, `主假设索引 ${String(output.primary_index)}`, '入选');
    }
  } else if (key === 'iterative_experiment' || key === 'experiment_design' || key === 'small_validation') {
    const spec = asRecord(output.experiment_spec) || asRecord(output.plan) || {};
    pushHighlight(items, asString(spec.objective) || asString(output.summary) || asString(output.status), '实验');
    const sandbox = asRecord(output.sandbox_result) || asRecord(output.pilot_result);
    if (sandbox) {
      pushHighlight(items, asString(sandbox.summary) || (sandbox.success === false ? '沙箱失败' : '沙箱完成'), '沙箱');
    }
    if (output.warning) pushHighlight(items, asString(output.warning), '警告');
  } else if (key === 'report_generation') {
    pushHighlight(items, asString(output.paper_title) || asString(output.title), '报告标题');
    const chapters = asRecord(output.chapters);
    if (chapters) {
      pushHighlight(items, Object.keys(chapters).join('、'), '章节');
    }
    if (output.pdf_success === true) pushHighlight(items, 'PDF 已生成', '导出');
    if (output.pdf_success === false) pushHighlight(items, 'PDF 未生成或失败', '导出');
  } else if (key === 'data_acquisition') {
    pushHighlight(items, asString(output.summary), '数据采集');
    const search = asRecord(output.search_summary);
    if (search) {
      pushHighlight(items, `外部候选 ${numField(search, 'external_candidates_count')}`, '数据检索');
    }
  }
  return items;
}

export function buildStageOutputSnapshots(
  run: PipelineRunDetail | null,
): StageOutputSnapshot[] {
  const stages = run?.stages || [];
  const byKey = new Map<string, PipelineStageExecutionSummary>();
  for (const stage of stages) {
    const key = stageKey(stage);
    if (key) byKey.set(key, stage);
  }
  const ordered: PipelineStageExecutionSummary[] = [];
  const seen = new Set<string>();
  for (const key of STAGE_DISPLAY_ORDER) {
    const stage = byKey.get(key);
    if (stage) {
      ordered.push(stage);
      seen.add(key);
    }
  }
  for (const stage of stages) {
    const key = stageKey(stage);
    if (key && !seen.has(key)) ordered.push(stage);
  }
  return ordered.map((stage) => {
    const key = stageKey(stage);
    const output = stageOutput(stage);
    return {
      key,
      label: STAGE_CN[key] || stage.stage,
      status: stage.status,
      model: stage.model_used || undefined,
      token_count: stage.token_count,
      duration_ms: stage.duration_ms,
      highlights: highlightsForStage(key, output),
      output,
    };
  });
}
