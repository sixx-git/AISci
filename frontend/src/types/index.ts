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
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectOverview {
  id: string;
  name: string;
  research_field: string;
  description: string;
  current_stage: string;
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

// ==================== 智能体 / 工作流节点 ====================

export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'human_review';

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
  created_at: string;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  input_data?: unknown;
  output_data?: unknown;
  stages: PipelineStageExecutionSummary[];
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

export interface ReportData {
  id: string;
  title: string;
  generatedAt: string;
  markdownContent: string;
  sections: ReportSection[];
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
export type RunLogStage = '问题理解' | '文献挖掘' | '假设生成' | '实验设计' | '实验执行' | '报告生成';

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
  modelParams: Record<string, string>;
  timestampStart: string;
  timestampEnd?: string;
}

// ==================== 研究结果（聚合） ====================

export interface ResearchResult {
  hypotheses: Hypothesis[];
  literature_evidence: LiteratureEvidence[];
  experiment_design: ExperimentDesign[];
  final_report?: string;
}