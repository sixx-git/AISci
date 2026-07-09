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

export type ProjectMode = 'general' | 'federated_learning';

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  status?: string;
  project_mode?: ProjectMode;
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
  project_mode?: ProjectMode;
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
  research_domain?: string;
  research_goal?: string;
  research_background?: string;
  data_source?: string;
  constraints?: string;
  expected_output?: string;
  project_mode?: ProjectMode;
  config?: {
    data_spec_hints?: Record<string, unknown>;
    data_acquisition?: Record<string, unknown>;
  };
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
  stance?: 'support' | 'refute' | 'neutral';
  stance_reason?: string;
  reliability_score?: number;
}

export interface EvidenceChainItem {
  evidence_id: string;
  claim: string;
  stance: 'support' | 'refute' | 'neutral';
  source_title: string;
  source_type?: string;
  year?: number | null;
  doi?: string;
  arxiv_id?: string;
  paper_id?: string;
  quote_or_summary?: string;
  relevance_score?: number;
  reliability_score?: number;
  used_in_revision?: boolean;
  stance_reason?: string;
}

export interface HypothesisRevisionRecord {
  original_hypothesis?: string;
  revision_reason?: string;
  revised_hypothesis?: string;
  what_changed?: string[];
  remaining_risks?: string[];
  round?: number;
}

export interface EvidenceChain {
  hypothesis?: string;
  supporting_evidence: EvidenceChainItem[];
  counter_evidence: EvidenceChainItem[];
  evidence_balance_score?: number;
  revision_history?: HypothesisRevisionRecord[];
  final_version?: string;
  chain_completeness?: number;
  citation_reliability?: number;
  support_count?: number;
  counter_count?: number;
  counter_evidence_empty_reason?: string;
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
  human_modified_output?: Record<string, unknown> | null;
  human_reviewed?: boolean;
  human_feedback?: string | null;
  edited_at?: string | null;
  human_edited?: boolean;
  revision_history?: Array<Record<string, unknown>>;
  chat_history?: Array<Record<string, unknown>>;
}

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
  human_modified_output?: Record<string, unknown> | null;
  human_reviewed?: boolean;
  human_feedback?: string | null;
  edited_at?: string | null;
  revision_history?: Array<Record<string, unknown>>;
  chat_history?: Array<Record<string, unknown>>;
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
  extra_metadata?: PipelineRunExtraMetadata;
}

export interface QualityTrendEntry {
  stage?: string;
  score?: number;
  cqs?: number;
  raw_score?: number;
  breakdown?: Record<string, number>;
  round?: number;
  branch_id?: string;
  label?: string;
}

export interface ClosedLoopEvent {
  type: string;
  at?: string;
  round?: number;
  overall?: number;
  decision?: string;
  summary?: string;
  success?: boolean;
  experiment_id?: string;
  composite_score?: number;
  selected_branch?: string;
  [key: string]: unknown;
}

export interface HitlGateInfo {
  paused?: boolean;
  stage?: string;
  stage_label?: string;
  resume_phase?: string;
  paused_at?: string;
  cleared_stages?: string[];
  last_action?: string;
}

export interface PipelineRunExtraMetadata {
  closed_loop_events?: ClosedLoopEvent[];
  closed_loop_decisions?: ClosedLoopDecision[];
  quality_trend?: QualityTrendEntry[];
  quality_acceptance?: QualityAcceptance;
  version_snapshots?: IterationSnapshot[];
  science_iteration?: ScienceIterationSession;
  auxiliary_results?: Record<string, unknown>;
  parent_run_id?: string;
  rerun_from?: string;
  run_options?: PipelineRunOptions;
  hitl_gate?: HitlGateInfo;
}

export interface ClosedLoopDecision {
  trigger?: string;
  action?: string;
  reason?: string;
  actor?: string;
  next_stage?: string;
  round?: number;
  at?: string;
  metadata?: Record<string, unknown>;
}

export interface ExecutabilityGate {
  passed?: boolean;
  score?: number;
  blockers?: string[];
  warnings?: string[];
  missing_columns?: string[];
  matched_columns?: string[];
  available_columns_sample?: string[];
}

export interface QualityAcceptance {
  verdict?: 'pass' | 'needs_review' | 'stagnant';
  accepted?: boolean;
  ensemble_decision?: string;
  ensemble_overall?: number;
  score_improved?: boolean;
  score_delta?: number;
  first_score?: number;
  last_score?: number;
  weak_stages?: string[];
  sandbox_success?: boolean | null;
  discovery_rounds?: number;
  literature_refresh_count?: number;
  refining_rounds?: number;
  federated_discovery_accept?: boolean;
  cqs_first?: number;
  cqs_last?: number;
  cqs_delta?: number;
  cqs_improved?: boolean;
  summary?: string;
}

export interface IterationSnapshot {
  round?: number;
  label?: string;
  hypothesis?: string;
  rationale_preview?: string;
  experimental_steps_preview?: string;
  methods_preview?: string;
  ensemble_overall?: number;
  ensemble_decision?: string;
  sandbox_success?: boolean;
  sandbox_metrics?: Record<string, unknown>;
  federated_best_method?: string;
  federated_execution_mode?: string;
  federated_gate_passed?: boolean;
  replan_action_count?: number;
  supporting_fact_count?: number;
  supporting_fact_ids_sample?: string[];
  evidence_level?: string;
  verifiable_spec_summary?: string;
  verifiable_primary_metric?: string;
  hypothesis_full?: string;
  data_evidence_count?: number;
  dataset_field_count?: number;
}

// ==================== 科学自迭代 ====================

export interface ScienceIterationConfig {
  enabled?: boolean;
  max_rounds?: number;
  auto_triggers?: string[];
  min_ensemble_score?: number;
  min_evidence_facts?: number;
  stagnation_delta?: number;
  require_human_on_stagnation?: boolean;
  show_iteration_in_report?: boolean;
  auto_literature_on_weak_evidence?: boolean;
  auto_literature_max?: number;
}

export interface HypothesisOriginBlock {
  main_contradiction?: string;
  phenomenon_contradiction?: string;
  problem_statement?: string;
  research_significance?: string;
  reasoning_chain?: string[];
}

export interface LiteratureGroundingItem {
  fact_id?: string;
  content?: string;
  quote_text?: string;
  source_title?: string;
  document_id?: string;
  relevance_score?: number | null;
}

export interface DataGroundingItem {
  table_id?: string;
  source_title?: string;
  source_type?: string;
  csv_path?: string;
  row_count?: number | null;
  extraction_method?: string;
}

export interface HypothesisGroundingBlock {
  literature?: LiteratureGroundingItem[];
  data?: DataGroundingItem[];
  multimodal?: Record<string, unknown>[];
  counter_evidence?: Record<string, unknown>[];
  knowledge_gaps?: string[];
}

export interface HypothesisVerificationBlock {
  verifiable_spec?: Record<string, unknown>;
  validation_target?: string;
  expected_measurable_effect?: string;
  verification_checks?: Record<string, unknown>[];
  sandbox_success?: boolean | null;
}

export interface HypothesisProvenance {
  hypothesis_id: string;
  hypothesis_text?: string;
  origin?: HypothesisOriginBlock;
  grounding?: HypothesisGroundingBlock;
  verification?: HypothesisVerificationBlock;
  evidence_sufficiency?: string;
  evidence_level?: string;
  scores?: Record<string, unknown>;
}

export interface MaterialSupplementAction {
  action_type?: string;
  description?: string;
  priority?: string;
  target?: string;
}

export interface MaterialSupplementPlan {
  triggers?: string[];
  actions?: MaterialSupplementAction[];
  suggested_queries?: string[];
}

export interface IterationRoundScores {
  hypothesis_tree?: number | null;
  ensemble_overall?: number | null;
  evidence_balance?: number | null;
  logic_score?: number | null;
  cqs?: number | null;
}

export interface IterationRoundRecord {
  round?: number;
  trigger?: string;
  label?: string;
  hypothesis_preview?: string;
  actions_taken?: string[];
  scores?: IterationRoundScores;
  delta_from_prev?: Record<string, unknown>;
  material_plan?: MaterialSupplementPlan | null;
  snapshot_label?: string;
}

export interface ScienceIterationSession {
  session_id?: string;
  project_id?: string;
  run_id?: string;
  config?: ScienceIterationConfig;
  rounds?: IterationRoundRecord[];
  current_best?: Record<string, unknown>;
  version_snapshots?: IterationSnapshot[];
  material_supplement_plan?: MaterialSupplementPlan | null;
  human_checkpoints?: Record<string, unknown>[];
}

export interface ReplanAction {
  action_id?: string;
  action_type?: string;
  parameter?: string;
  to_value?: string | number;
  expected_check?: string;
  priority?: string;
  rationale?: string;
  verifiable?: boolean;
}

export interface DiscoveryFederatedAcceptance {
  accepted?: boolean;
  ensemble_ok?: boolean;
  federated_ok?: boolean;
  blockers?: string[];
  summary?: string;
}

export interface DiscoveryLoopHistoryEntry {
  round?: number;
  status?: string;
  decision?: string;
  overall?: number;
  refinement_notes?: string[];
  rollback?: Record<string, unknown>;
  snapshot_before?: IterationSnapshot;
  snapshot_after?: IterationSnapshot;
  federated_acceptance?: DiscoveryFederatedAcceptance;
  federated_campaign?: FederatedCampaignRefinementData;
  data_changes?: string[];
  plan_changes?: string[];
  driven_by?: string;
  summary?: string;
  stagnation?: Record<string, unknown>;
}

export interface DiscoveryLoopData {
  pipeline_mode?: string;
  max_rounds?: number;
  rounds_executed?: number;
  history?: DiscoveryLoopHistoryEntry[];
  final_report_id?: string;
  version_snapshots?: IterationSnapshot[];
}

export interface TeachingAutoRefinementData {
  round?: number;
  reasons?: string[];
  reran?: boolean;
  snapshot_before?: IterationSnapshot;
  snapshot_after?: IterationSnapshot;
  version_snapshots?: IterationSnapshot[];
}

export interface FederatedCampaignRefinementData {
  round?: number;
  reasons?: string[];
  reran?: boolean;
  improved?: boolean;
  improvement?: {
    improved?: boolean;
    summary?: string;
    accuracy_delta?: number;
    mode_before?: string;
    mode_after?: string;
  };
  pilot_before_mode?: string;
  pilot_after_mode?: string;
  version_snapshots?: IterationSnapshot[];
}

export interface HypothesisTreeBranch {
  branch_id: string;
  index: number;
  label: string;
  hypothesis?: string;
  composite_score: number;
  scores?: Record<string, number>;
  supporting_fact_count?: number;
  alignment_score?: number;
  evidence_level?: string;
  status?: string;
  pilot_score?: number;
  pilot_success?: boolean;
  pilot_status?: string;
  pilot_metrics?: Record<string, unknown>;
}

export interface HypothesisTreeData {
  tree_id?: string;
  branches: HypothesisTreeBranch[];
  pruned_branches?: Array<{ branch_id: string; index: number; composite_score: number }>;
  selected_branch_id?: string;
  selected_hypothesis_index?: number;
  iteration_summary?: string;
  quality_trend?: QualityTrendEntry[];
  evidence_coverage?: Record<string, unknown>;
}

export interface EnsembleReviewData {
  overall?: number;
  decision?: string;
  weaknesses?: string[];
  revision_suggestions?: string[];
  ensemble_reviews?: Array<Record<string, unknown>>;
  aggregated?: {
    overall_score?: number;
    decision?: string;
    needs_human_review?: boolean;
    disagreement_flags?: string[];
  };
  target_hypothesis_index?: number;
  pro_con_adversarial?: boolean;
}

export type AdversarialMode = 'single_group' | 'multi_group' | 'off';

export interface ProConChallenge {
  target_aspect?: string;
  attack_type?: string;
  severity?: string;
  statement?: string;
  counter_evidence_fact_ids?: string[];
  suggested_fix?: string;
}

export interface CounterfactualScenario {
  scenario_id?: string;
  intervention?: string;
  question?: string;
  predicted_outcome?: string;
  failure_risk?: 'low' | 'medium' | 'high' | string;
  confidence?: 'low' | 'medium' | 'high' | string;
  evidence_fact_ids?: string[];
  cheap_test?: string;
  decision_impact?: string;
  falsifiable?: boolean;
}

export interface CounterfactualPreviewData {
  prediction_tier?: string;
  scenarios?: CounterfactualScenario[];
  failure_predictions?: string[];
  recommended_pivots?: string[];
  proceed_to_experiment_design?: boolean;
  summary?: string;
  skipped?: boolean;
  reason?: string;
}

export interface ProConAdversarialData {
  mode?: AdversarialMode;
  pro_side?: {
    role?: string;
    agents?: string[];
    research_groups?: Array<{
      group_index: number;
      hypothesis?: string;
      rationale?: string;
      evidence_level?: string;
      literature_anchors?: Array<{ fact_id?: string; summary?: string }>;
      validation_target?: string;
    }>;
  };
  con_side?: {
    type?: string;
    target_hypothesis_index?: number;
    rounds?: Array<{
      round?: number;
      round_summary?: string;
      overall_threat_level?: string;
      challenges?: ProConChallenge[];
    }>;
  };
  cross_group_attacks?: Array<{
    defender_index?: number;
    attacker_index?: number;
    attacker_label?: string;
    challenges?: ProConChallenge[];
  }>;
  group_survival_scores?: number[];
  evolution?: {
    status?: string;
    evolved_rationale?: string;
    revision_points?: string[];
    hypothesis_patch?: string;
    remaining_risks?: string[];
  };
  primary_index_override?: { from?: number; to?: number; reason?: string };
}

export interface IdeationNoveltyData {
  research_question?: string;
  novelty_score?: number;
  novelty_risk?: string;
  external_papers_count?: number;
  num_ideas_requested?: number;
  suggested_angles?: string[];
  avoid_topics?: string[];
  top_similar_works?: Array<{
    title?: string;
    year?: number;
    overlap_ratio?: number;
    source?: string;
  }>;
  assessment?: string;
  sources_used?: string[];
}

export interface PlotQualityData {
  critique?: {
    average_score?: number;
    critiques?: Array<Record<string, unknown>>;
    needs_human_review?: boolean;
    needs_redraw?: boolean;
    review_mode?: string;
    degradation_reason?: string;
  };
  redraw_count?: number;
  needs_human_review?: boolean;
}

export type PipelineRunMode = 'teaching' | 'discovery';

export interface PipelineRunOptions {
  pipeline_mode?: PipelineRunMode;
  num_ideas?: number;
  literature_max_papers?: number;
  discovery_max_rounds?: number;
  force_sandbox?: boolean;
  enable_plot_vlm_critique?: boolean;
  enable_teaching_auto_refinement?: boolean;
  enable_federated_campaign_loop?: boolean;
  federated_campaign_max?: number;
  sandbox_use_docker?: boolean;
  enable_pro_con_adversarial?: boolean;
  adversarial_mode?: AdversarialMode;
  con_challenge_max_rounds?: number;
  enable_hypothesis_evolution?: boolean;
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
  human_modified_output?: Record<string, unknown> | null;
  human_reviewed?: boolean;
  human_feedback?: string | null;
  edited_at?: string | null;
  revision_history?: Array<Record<string, unknown>>;
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
  extra_metadata?: PipelineRunExtraMetadata;
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

export interface VerifiableSpec {
  claim?: string;
  primary_metric?: string;
  success_criteria?: string[];
  falsification_criteria?: string;
  stop_criteria?: string[];
  mode?: string;
  supporting_fact_ids?: string[];
  evidence_level?: string;
}

export interface VerifiableCheck {
  check_id?: string;
  description?: string;
  expected?: string;
  actual?: string;
  passed?: boolean;
  source?: string;
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
  evidenceChain?: EvidenceChain | null;
  chainCompleteness?: number;
  supportEvidenceCount?: number;
  counterEvidenceCount?: number;
  citationReliability?: number;
  supporting_fact_ids?: string[];
  verifiable_spec?: VerifiableSpec | null;
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
  /** ── 报告质量检查（ReportQualityCheckSkill 输出）── */
  report_quality_check?: {
    success: boolean;
    data?: {
      score?: number;
      passed?: boolean;
      references_verified?: number;
      has_real_data_plots?: boolean;
      has_actual_or_simulated_results?: boolean;
      missing_fields?: string[];
      warnings?: string[];
      critical_issues?: string[];
      recommendations?: string[];
    };
    warnings?: string[];
    errors?: string[];
    error?: string;
  };
}

export interface ReportData {
  id: string;
  title: string;
  generatedAt: string;
  /** 同一份报告的 PDF 再生成次数（非 Pipeline 多次运行的版本号） */
  version?: number;
  sections: ReportSection[];
  /** 合规性检查结果 */
  complianceCheck?: ComplianceCheck;
  /** 下载链接 */
  texDownloadUrl?: string;
  pdfDownloadUrl?: string;
  /** PDF 导出是否成功（LaTeX 编译） */
  pdfSuccess?: boolean;
  /** PDF 导出方式：latex */
  exportMethod?: string;
  /** 图表数据 */
  plots?: ReportPlot[];
  extraMetadata?: Record<string, unknown>;
  /** 12 章节原始字段，供导师评审 / 局部修订 */
  reportContent?: Record<string, string>;
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
  type: 'line' | 'bar' | 'scatter' | 'heatmap' | 'histogram' | 'box' | 'grouped_bar' | 'sandbox_plot';
  title: string;
  description: string;
  /** 完整论文图注：实验条件、指标、对比结论 */
  caption?: string;
  experiment_condition?: string;
  metric?: string;
  metric_direction?: 'higher_is_better' | 'lower_is_better' | 'context_dependent';
  baseline_comparison?: string;
  x_label?: string;
  y_label?: string;
  has_legend?: boolean;
  chart_kind?: 'experiment_result' | 'descriptive_stat';
  base64?: string;
  url?: string;
  file_path?: string;
  markdown_embed?: string;
  source?: string;
  source_dataset_id?: string;
  has_image?: boolean;
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