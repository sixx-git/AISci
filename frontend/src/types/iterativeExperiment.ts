/** 迭代实验（对齐 shaxiang-main Experiment / phase / 迭代记录） */

export type IterativeExperimentPhase =
  | 'created'
  | 'data_recommended'
  | 'data_uploaded'
  | 'script_designed'
  | 'running'
  | 'completed'
  | 'failed';

export type IterativeExperimentStatus =
  | 'created'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed';

export type ExecutorType = 'sandbox' | 'simulation';

export type RunMode = 'smoke_only' | 'full';

export type DataSourceType = 'uploaded' | 'directory' | 'local_csv' | 'local_json' | 'huggingface';

export interface DatasetRecommendation {
  name: string;
  description?: string;
  reason?: string;
  download_url?: string;
  expected_columns?: string[];
  size_hint?: string;
  file_format?: string;
  is_required?: boolean;
}

export interface DataConfig {
  source_type: DataSourceType;
  source_path: string;
  profile_name?: string;
  sample_size?: number;
  preprocessing_steps?: string[];
  /** mock：上传文件名 */
  file_name?: string;
  row_count?: number;
  columns?: string[];
}

export interface ExperimentPlanMock {
  title: string;
  description: string;
  methodology: string;
  analysis_script: string;
  script_params: Record<string, unknown>;
  success_criteria: string[];
}

export interface IterationRecordMock {
  iteration_number: number;
  status: 'success' | 'failed' | 'partial';
  plan: { title: string; methodology?: string };
  result: {
    metrics?: Record<string, number | string>;
    charts?: Array<{ name: string; note?: string }>;
    summary?: string;
  };
  analysis: { summary?: string; strengths?: string[]; weaknesses?: string[] };
  decision: { continue: boolean; reason?: string };
  metrics: Record<string, number | string>;
  duration_seconds: number;
  error_message?: string;
  created_at: string;
}

export interface IterativeExperiment {
  id: string;
  project_id: string;
  title: string;
  research_goal: string;
  hypothesis: string;
  constraints: string[];
  executor_type: ExecutorType;
  max_iterations: number;
  current_iteration: number;
  phase: IterativeExperimentPhase;
  status: IterativeExperimentStatus;
  run_mode: RunMode;
  dataset_recommendations: DatasetRecommendation[] | null;
  data_config: DataConfig | null;
  initial_plan: ExperimentPlanMock | null;
  human_feedback: string | null;
  feedback_status: 'none' | 'pending' | 'submitted' | 'applied';
  iterations: IterationRecordMock[];
  created_at: string;
  updated_at: string;
}

export interface IterativeExperimentStore {
  experiments: IterativeExperiment[];
  /** 手动指定用于报告的实验 ID（可多选） */
  reportExperimentIds: string[];
}
