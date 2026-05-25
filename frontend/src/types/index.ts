export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
  timestamp?: string;
}

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

export interface Document {
  id: string;
  filename: string;
  file_path: string;
  file_type: string;
  content?: string;
  status: string;
  created_at: string;
}

export interface PipelineStage {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  result?: any;
  error?: string;
}

export interface PipelineResult {
  stages: PipelineStage[];
  finalReport?: any;
}

export interface ReportGenerationResult {
  title: string;
  paper_title: string;
  paper_abstract: string;
  markdown_content: string;
  report_id?: string;
  pdf_download_url?: string;
  md_download_url?: string;
  pdf_success?: boolean;
  chapters: any;
}

export interface ReportGenerationRequest {
  project_id: string;
  project_info: any;
  problem_understanding: any;
  literature_facts: any[];
  citation_map: any[];
  knowledge_gaps: any;
  final_hypothesis: any;
  experiment_design: any;
  small_validation?: any;
}

// ============ 结果展示相关类型 ============

export interface Hypothesis {
  id: string;
  title: string;
  description: string;
  score: number;
  scores: {
    novelty: number;
    feasibility: number;
    scientific_value: number;
    clarity: number;
    testability: number;
  };
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

export interface ExperimentDesign {
  id: string;
  step: number;
  name: string;
  description: string;
  expected_result: string;
  success_criteria: string;
}

export interface ResearchResult {
  hypotheses: Hypothesis[];
  literature_evidence: LiteratureEvidence[];
  experiment_design: ExperimentDesign[];
  final_report?: string;
}
