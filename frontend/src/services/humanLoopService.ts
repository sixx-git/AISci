import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface StageHumanDetail {
  run_id: string;
  project_id: string;
  stage: string;
  status: string;
  input_data?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  human_modified_output?: Record<string, unknown>;
  human_reviewed?: boolean;
  human_feedback?: string;
  edited_at?: string;
  revision_history?: Array<Record<string, unknown>>;
  prompt_used?: string;
  model_used?: string;
}

export interface MentorReview {
  strengths: string[];
  weaknesses: string[];
  revision_suggestions: string[];
  risk_points: string[];
  required_additional_evidence: string[];
  overall_assessment?: string;
  readiness_score?: number;
}

export const humanLoopService = {
  async getStageDetail(runId: string, stage: string): Promise<ApiResponse<StageHumanDetail>> {
    const { data } = await api.get<ApiResponse<StageHumanDetail>>(`/human-loop/stage/${runId}/${stage}`);
    return data;
  },

  async saveStageOutput(payload: {
    project_id: string;
    run_id: string;
    stage: string;
    output_data: Record<string, unknown>;
    human_feedback?: string;
    mark_reviewed?: boolean;
  }): Promise<ApiResponse<unknown>> {
    const { data } = await api.post<ApiResponse<unknown>>('/human-loop/stage-output/save', payload);
    return data;
  },

  async rerunFromStage(payload: {
    project_id: string;
    run_id: string;
    stage: string;
    use_human_modified_output?: boolean;
  }): Promise<ApiResponse<{ run_id: string; parent_run_id: string; rerun_from_stage: string; status: string }>> {
    const { data } = await api.post('/pipeline/rerun-from-stage', payload);
    return data;
  },

  async stageChat(payload: {
    project_id: string;
    run_id: string;
    stage: string;
    message: string;
    apply_change?: boolean;
  }): Promise<ApiResponse<{
    revised_output: Record<string, unknown>;
    explanation: string;
    changes_summary: string[];
  }>> {
    const { data } = await api.post('/human-loop/stage-chat', payload);
    return data;
  },

  async mentorReview(payload: {
    project_id: string;
    run_id?: string;
    stage?: string;
    target_type: 'hypothesis' | 'experiment_design' | 'report';
    content?: Record<string, unknown>;
    research_question?: string;
    user_notes?: string;
  }): Promise<ApiResponse<{ target_type: string; review: MentorReview }>> {
    const { data } = await api.post('/human-loop/mentor-review', payload);
    return data;
  },

  async reviseReport(payload: {
    project_id: string;
    report_id: string;
    message: string;
  }): Promise<ApiResponse<{ revision_history?: Array<Record<string, unknown>> }>> {
    const { data } = await api.post('/reports/revise', payload);
    return data;
  },
};

export default humanLoopService;
