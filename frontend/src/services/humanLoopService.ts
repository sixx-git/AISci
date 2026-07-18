import api from '@/lib/api';
import type { ApiResponse, HitlGateInfo } from '@/types';

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
  chat_history?: Array<Record<string, unknown>>;
  prompt_used?: string;
  model_used?: string;
  global_constraints?: string[];
  recent_feedback_entries?: Array<{
    id?: string;
    source?: string;
    message?: string;
    target?: string;
    created_at?: string;
  }>;
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

export type StageChatMode = 'advisory' | 'revise';
export type RerunMode = 'single_stage' | 'from_stage_onward';
export type HitlInteractionMode = StageChatMode | 'rerun_agent';

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
    rerun_mode?: RerunMode;
    human_feedback?: string;
  }): Promise<ApiResponse<{ run_id: string; parent_run_id: string; rerun_from_stage: string; rerun_mode?: string; status: string; in_place?: boolean }>> {
    const { data } = await api.post('/human-loop/rerun-from-stage', payload);
    return data;
  },

  async stageChat(payload: {
    project_id: string;
    run_id: string;
    stage: string;
    message: string;
    apply_change?: boolean;
    mode?: StageChatMode;
  }): Promise<ApiResponse<{
    revised_output: Record<string, unknown>;
    explanation: string;
    changes_summary: string[];
    applied?: boolean;
    chat_history?: Array<Record<string, unknown>>;
    revision_mode?: string;
    mode?: string;
  }>> {
    const { data } = await api.post('/human-loop/stage-chat', payload, {
      // 轻量修订可能触发完整 JSON 再生成
      timeout: 1_200_000,
    });
    return data;
  },

  async getHitlGateStatus(runId: string): Promise<ApiResponse<HitlGateInfo & { run_id: string; status: string }>> {
    const { data } = await api.get(`/human-loop/gate/${runId}`);
    return data;
  },

  async resumeHitlGate(payload: {
    project_id: string;
    run_id: string;
    action: 'continue' | 'rerun' | 'abort';
    human_feedback?: string;
    inject_feedback?: boolean;
  }): Promise<ApiResponse<{ action: string; status: string; run_id: string; rerun_from_stage?: string }>> {
    const { data } = await api.post('/human-loop/gate/resume', payload);
    return data;
  },

  async mentorReview(payload: {
    project_id: string;
    run_id?: string;
    report_id?: string;
    stage?: string;
    target_type: 'hypothesis' | 'iterative_experiment' | 'experiment_design' | 'report';
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
    section_keys?: string[];
    apply_change?: boolean;
  }): Promise<ApiResponse<{
    explanation?: string;
    changes_summary?: string[];
    revision_history?: Array<Record<string, unknown>>;
    chat_history?: Array<Record<string, unknown>>;
    applied?: boolean;
  }>> {
    const { data } = await api.post('/reports/revise', payload);
    return data;
  },
};

export default humanLoopService;
