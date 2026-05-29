// ============================================================
// 统一类型定义 —— 前端所有组件均从此文件导入类型
// ============================================================

import type { LucideIcon } from 'lucide-react';

// ==================== API 通用 ====================

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  timestamp?: string;
}

// ==================== 项目 ====================

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  status?: string;
  // 研究问题字段
  research_question?: string;
  research_domain?: string;
  research_goal?: string;
  research_background?: string;
  data_source?: string;
  constraints?: string;
  expected_output?: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  // 研究问题字段（可选）
  research_question?: string;
  research_domain?: string;
  research_goal?: string;
  research_background?: string;
  data_source?: string;
  constraints?: string;
  expected_output?: string;
}

export interface ProjectOverview {
  id: string;
  name: string;
  research_field: string;
  description: string;
  current_stage: string;
  research_question?: string;
  created_at: string;
  updated_at: string;
  status: string;
}

// ==================== 文档 / 文献 ====================

export interface Document {
  id: string;
  filename: string;
  file_path: string;
  file_type: string;
  content?: string;
  status: string;
  created_at: string;
}

export interface LiteratureItem {
  id: string;
  title: string;
  authors: string;
  year: number;
  type: '论文' | '综述' | '会议' | '预印本';
  parseStatus: 'pending' | 'parsing' | 'completed' | 'error';
  snippetCount: number;
  factCount: number;
  fileSize: string;
  uploadDate: string;
}

export interface LiteratureStats {
  uploaded: number;
  parsed: number;
  snippets: number;
  facts: number;
}

export interface LiteratureEvidence {
  id: string;
  title: string;
  author: string;
  year: string;
  content: string;
  source_type: 'citation' | 'quote' | 'concept';
  relevance: number;
}

// ==================== 证据链 ====================

export interface EvidenceItem {
  id: string;
  project_id: string;
  hypothesis_id: string;
  document_id?: string;
  chunk_id?: string;
  fact_text: string;
  quote_text?: string;
  page_number?: number;
  relevance_score: number;
  source_title?: string;
  created_at?: string;
}

// ==================== 研究问题 ====================

export interface ResearchQuestion {
  researchDomain: string;
  researchQuestion: string;
  researchGoal: string;
  constraints: string;
  evaluationCriteria: string;
  keywords: string;
}

// ==================== 智能体工作流 ====================

export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'human_review_required' | 'human_review';

export interface AgentNodeData {
  id: string;
  name: string;
  shortDesc: string;
  status: AgentStatus;
  duration: number | null;
  inputSummary: string;
  outputSummary: string;
  logs: string[];
  model: string;
  promptVersion: string;
  icon: LucideIcon;
  /** 从真实 API 获取的完整数据 */
  input_data?: Record<string, unknown> | null;
  output_data?: Record<string, unknown> | null;
  error_message?: string | null;
  prompt_used?: string | null;
  model_used?: string | null;
  model_parameters?: Record<string, unknown> | null;
  token_count?: number | null;
}

// ==================== Pipeline 统计 ====================

export interface PipelineNodeData {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  icon: LucideIcon;
}

export interface PipelineStage {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  result?: unknown;
  error?: string;
}

export interface PipelineStageExecutionSummary {
  id: string;
  pipeline_run_id: string;
  stage: string;
  stage_order: number;
  status: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  input_data?: unknown;
  output_data?: unknown;
  error_message?: string;
  token_count?: number;
  model_used?: string;
  prompt_used?: string;
  model_parameters?: Record<string, unknown>;
}

export interface PipelineRunSummary {
  id: string;
  run_id: string;
  project_id: string;
  research_question: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  total_duration_ms?: number;
  final_report_id?: string;
  failed_stage?: string;
  error_message?: string;
  created_at: string;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  input_data?: unknown;
  output_data?: unknown;
  stages: PipelineStageExecutionSummary[];
}

export interface PipelineStageLog {
  stage: string;
  stage_order?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string | null;
  completed_at?: string | null;
  start_time?: string;
  end_time?: string;
  duration?: number;
  duration_ms?: number | null;
  input_data?: Record<string, unknown> | null;
  output_data?: Record<string, unknown> | null;
  error_message?: string | null;
  prompt_used?: string | null;
  model_used?: string | null;
  model_parameters?: Record<string, unknown> | null;
  token_count?: number | null;
}

export interface PipelineRunResult {
  pipeline_id: string;
  run_id: string;
  project_id: string;
  research_question: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  stages: PipelineStageLog[];
  total_duration?: number;
  problem_understanding?: Record<string, unknown>;
  literature_mining?: Record<string, unknown>;
  knowledge_gap?: Record<string, unknown>;
  hypothesis_generation?: Record<string, unknown>;
  hypothesis_review?: Record<string, unknown>;
  experiment_design?: Record<string, unknown>;
  small_validation?: Record<string, unknown>;
  report_generation?: Record<string, unknown>;
  final_report?: Record<string, unknown>;
  final_report_id?: string;
  failed_stage?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

// ==================== 统计卡片 ====================

export interface StatItem {
  id: string;
  label: string;
  value: number;
  icon: LucideIcon;
  color: string;
}

// ==================== 假设 ====================

export interface HypothesisScores {
  novelty: number;
  feasibility: number;
  scientific_value: number;
  clarity: number;
  testability: number;
}

export interface Hypothesis {
  id: string;
  title: string;
  description: string;
  score: number;
  scores: HypothesisScores;
}

export interface DetailedHypothesis {
  id: string;
  title: string;
  content: string;
  reasoning: string;
  evidenceCount: number;
  novelty: number;
  verifiability: number;
  dataAvailability: number;
  overallScore: number;
  riskWarning: string;
  isPrimary: boolean;
  status: 'draft' | 'evaluated' | 'confirmed';
  alignment_score?: number;
  off_topic?: boolean;
  off_topic_reason?: string;
  matched_keywords?: string[];
  missing_keywords?: string[];
  domain_conflict_keywords?: string[];
  evidenceLevel?: string;
  question_alignment?: string;
  dataset_field_refs?: string[];
  data_evidence_ids?: string[];
  validation_target?: string;
  expected_measurable_effect?: string;
}

/** 后端返回的数据集记录 */
export interface BackendDataset {
  id: string;
  project_id: string;
  filename: string;
  file_path: string;
  file_size?: number;
  data_type: 'tabular' | 'image' | 'time_series' | 'json' | 'pdf' | 'unknown';
  source_type: 'upload' | 'history' | 'public';
  n_rows?: number;
  n_columns?: number;
  columns_json?: string;
  dtypes_json?: string;
  missing_count?: number;
  missing_rate?: number;
  statistics_json?: string;
  preview_json?: string;
  preprocessing_status: 'pending' | 'processing' | 'completed' | 'failed';
  use_for_hypothesis: boolean;
  extra_metadata?: string;
  created_at: string;
  updated_at?: string;
}

/** 前端展示用的数据集摘要 */
export interface DatasetSummary {
  id: string;
  filename: string;
  dataType: string;
  nRows?: number;
  nColumns?: number;
  columns?: string[];
  dtypes?: Record<string, string>;
  missingCount?: number;
  missingRate?: number;
  statistics?: Record<string, unknown>;
  preview?: Record<string, unknown>[];
  preprocessingStatus: string;
  useForHypothesis: boolean;
  fileSize?: number;
  createdAt: string;
}

// ==================== 实验设计 ====================

export interface ExperimentDesign {
  id: string;
  step: number;
  name: string;
  description: string;
  expected_result: string;
  success_criteria: string;
}

export interface ExperimentStep {
  step: number;
  title: string;
  description: string;
  expected: string;
}

export interface ExperimentBaseline {
  name: string;
  description: string;
  category: 'traditional' | 'deep' | 'sota';
}

export interface ExperimentMetric {
  name: string;
  description: string;
  target: string;
}

export interface DetailedExperimentDesign {
  id: string;
  hypothesisTitle: string;
  objective: string;
  methods: string;
  sourceDataset: string;
  sourceDescription: string;
  targetDataset: string;
  targetDescription: string;
  baselines: ExperimentBaseline[];
  metrics: ExperimentMetric[];
  steps: ExperimentStep[];
  expectedResults: string;
  limitations: string[];
}

// ==================== 研究报告 ====================

export type ReportSectionStatus = 'completed' | 'missing' | 'human_review';

export interface ReportSection {
  key: string;
  label: string;
  status: ReportSectionStatus;
  note?: string;
}

/** 合规性检查结果（挑战杯 XH-202619 12 项字段） */
export interface ComplianceCheck {
  total_items?: number;
  completed: number;
  missing: number;
  human_review: number;
  references_verified: number;
  references_suspicious: number;
  references_replaced?: boolean;
  /** ── 赛题专属指标 ── */
  evidence_fact_count: number;
  hypothesis_with_evidence_count: number;
  has_actual_or_simulated_result: boolean;
  result_type?: string;
  /** ── 12 字段合规标记 ── */
  has_problem_statement?: boolean;
  has_rationale?: boolean;
  has_technical_details?: boolean;
  has_datasets?: boolean;
  has_source?: boolean;
  has_target?: boolean;
  has_paper_title?: boolean;
  has_paper_abstract?: boolean;
  has_methods?: boolean;
  has_experiments?: boolean;
  has_results?: boolean;
  has_references?: boolean;
  /** ── Skill 适配层指标 ── */
  novelty_score?: number;
  experiment_sanity_check?: {
    executable: boolean;
    missing_items: string[];
    weak_points: string[];
    recommendations: string[];
  };
  /** ── 警告与严重问题 ── */
  warnings?: string[];
  critical_issues?: string[];
  items: ReportSection[];
}

export interface ReportData {
  id: string;
  title: string;
  generatedAt: string;
  markdownContent: string;
  sections: ReportSection[];
  /** 合规性检查结果 */
  complianceCheck?: ComplianceCheck;
  /** 下载链接 */
  mdDownloadUrl?: string;
  pdfDownloadUrl?: string;
  /** PDF 导出是否成功（后端返回） */
  pdfSuccess?: boolean;
  /** 图表数据 */
  plots?: ReportPlot[];
}

export interface ReportGenerationResult {
  title: string;
  paper_title: string;
  paper_abstract: string;
  markdown_content: string;
  report_id?: string;
  pdf_url?: string;
  pdf_download_url?: string;
  md_download_url?: string;
  pdf_success?: boolean;
  summary?: string;
  chapters: unknown;
  /** 合规性检查结果 */
  compliance_check?: ComplianceCheck;
  /** 图表数据 */
  plots?: ReportPlot[];
  chart_skill_outputs?: Record<string, unknown>;
}

export interface ReportPlot {
  plot_id: string;
  type: 'line' | 'bar' | 'scatter' | 'heatmap' | 'histogram' | 'box';
  title: string;
  description: string;
  base64: string;
  url: string;
  file_path: string;
  markdown_embed: string;
  source_dataset_id?: string;
  is_generated_from_real_data: boolean;
}

export interface ReportGenerationRequest {
  project_id: string;
  project_info: unknown;
  problem_understanding: unknown;
  literature_facts: unknown[];
  citation_map: unknown[];
  knowledge_gaps: unknown;
  final_hypothesis: unknown;
  experiment_design: unknown;
  small_validation?: unknown;
}

// ==================== 运行日志 ====================

export type RunLogStatus = 'success' | 'running' | 'failed' | 'pending';
export type RunLogStage = '问题理解' | '文献挖掘' | '知识缺口' | '假设生成' | '假设评估' | '实验设计' | '小样验证' | '实验执行' | '报告生成';

export interface RunLog {
  id: string;
  projectName: string;
  runTime: string;
  stage: RunLogStage;
  model: string;
  promptVersion: string;
  duration: string;
  status: RunLogStatus;
  inputSummary: string;
  outputSnapshot: string;
  errorMessage?: string;
  modelParams?: Record<string, string>;
  timestampStart?: string;
  timestampEnd?: string;
  temperature?: string;
  tokenCount?: number;
  runId?: string;
}

// ==================== 研究结果（聚合） ====================

export interface ResearchResult {
  hypotheses: Hypothesis[];
  literature_evidence: LiteratureEvidence[];
  experiment_design: ExperimentDesign[];
  final_report?: string;
}