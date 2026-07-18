import api from '@/lib/api';
import type { ApiResponse, EvidenceChain } from '@/types';

export interface BackendReviewScores {
  novelty?: number;
  testability?: number;
  data_availability?: number;
  scientific_value?: number;
  cost_risk?: number;
  overall_score?: number;
}

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
  domain_conflict_keywords?: string[];
  is_primary?: boolean;
  review_scores?: BackendReviewScores;
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
  extra_metadata?: string;
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

  async getEvidenceChain(hypothesisId: string): Promise<ApiResponse<EvidenceChain | null>> {
    const { data } = await api.get<ApiResponse<EvidenceChain | null>>(
      `/agents/hypotheses/${hypothesisId}/evidence-chain`,
    );
    return data;
  },

  async iterateEvidenceChain(hypothesisId: string): Promise<ApiResponse<{ evidence_chain: EvidenceChain; hypothesis: Record<string, unknown> }>> {
    const { data } = await api.post(
      `/agents/hypotheses/${hypothesisId}/evidence-chain/iterate`,
      null,
      { timeout: 300000 },
    );
    return data;
  },

  async getProvenanceTimeline(hypothesisId: string): Promise<ApiResponse<ProvenanceTimelineResponse>> {
    const { data } = await api.get<ApiResponse<ProvenanceTimelineResponse>>(
      `/agents/hypotheses/${hypothesisId}/provenance-timeline`,
    );
    return data;
  },
};

export interface ProvenanceTimelineStep {
  step: string;
  label: string;
  count?: number;
  items?: Array<Record<string, unknown>>;
}

export interface ProvenanceTimelineResponse {
  hypothesis_id: string;
  timeline: ProvenanceTimelineStep[];
}

export default hypothesisService;