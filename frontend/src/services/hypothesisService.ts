import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface BackendHypothesis {
  id: string;
  project_id: string;
  research_question: string;
  hypothesis: string;
  rationale: string;
  novelty: string;
  testability: string;
  required_data: string;
  possible_method: string;
  risk: string;
  supporting_fact_ids: string[];
  evidence_level: string;
  status: string;
  priority: number;
  confidence: number;
  created_at: string;
  updated_at?: string;
  alignment_score?: number;
  off_topic?: boolean;
  off_topic_reason?: string;
  matched_keywords?: string[];
  missing_keywords?: string[];
  question_alignment?: string;
  dataset_field_refs?: string[];
  data_evidence_ids?: string[];
  validation_target?: string;
  expected_measurable_effect?: string;
}

export interface BackendEvidence {
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
  created_at: string;
}

const hypothesisService = {
  async getProjectHypotheses(projectId: string): Promise<ApiResponse<BackendHypothesis[]>> {
    const { data } = await api.get<ApiResponse<BackendHypothesis[]>>(
      `/projects/${projectId}/hypotheses`,
    );
    return data;
  },

  async getHypothesisEvidence(hypothesisId: string): Promise<ApiResponse<BackendEvidence[]>> {
    const { data } = await api.get<ApiResponse<BackendEvidence[]>>(
      `/agents/hypotheses/${hypothesisId}/evidence`,
    );
    return data;
  },

  async setPrimaryHypothesis(projectId: string, hypothesisId: string): Promise<ApiResponse<BackendHypothesis>> {
    const { data } = await api.post<ApiResponse<BackendHypothesis>>(
      `/projects/${projectId}/hypotheses/${hypothesisId}/set-primary`,
    );
    return data;
  },
};

export default hypothesisService;