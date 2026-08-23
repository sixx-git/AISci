import api from '@/lib/api';
import type {
  ApiResponse,
  PipelineRunSummary,
  PipelineRunDetail,
  PipelineRunResult,
} from '@/types';

export const pipelineService = {
  /** POST /api/v1/pipeline/run */
  async run(
    projectId: string,
    researchQuestion: string,
    options?: Record<string, unknown>
  ): Promise<ApiResponse<PipelineRunResult>> {
    const { data } = await api.post<ApiResponse<PipelineRunResult>>('/pipeline/run', {
      project_id: projectId,
      research_question: researchQuestion,
      options: options || {},
    });
    return data;
  },

  /** GET /api/v1/pipeline/status/:runId — 轮询运行状态 */
  async getStatus(runId: string): Promise<ApiResponse<PipelineRunResult>> {
    const { data } = await api.get<ApiResponse<PipelineRunResult>>(`/pipeline/status/${runId}`);
    return data;
  },

  /** GET /api/v1/pipeline/runs/:projectId */
  async getRuns(projectId: string): Promise<ApiResponse<PipelineRunSummary[]>> {
    const { data } = await api.get<ApiResponse<PipelineRunSummary[]>>(`/pipeline/runs/${projectId}`);
    return data;
  },

  /** GET /api/v1/pipeline/run/:runId */
  async getRunDetail(runId: string): Promise<ApiResponse<PipelineRunDetail>> {
    const { data } = await api.get<ApiResponse<PipelineRunDetail>>(`/pipeline/run/${runId}`);
    return data;
  },

  /** POST /api/v1/pipeline/runs/:runId/pause — 协作式暂停（当前阶段结束后生效） */
  async pause(runId: string): Promise<ApiResponse<{
    run_id: string;
    accepted: boolean;
    already_requested?: boolean;
    status: string;
    message: string;
  }>> {
    const { data } = await api.post<ApiResponse<{
      run_id: string;
      accepted: boolean;
      already_requested?: boolean;
      status: string;
      message: string;
    }>>(`/pipeline/runs/${runId}/pause`);
    return data;
  },

  /** POST /api/v1/pipeline/runs/:runId/resume — 从用户暂停检查点续跑 */
  async resume(runId: string): Promise<ApiResponse<{
    run_id: string;
    status: string;
    resume_phase?: string;
    message: string;
  }>> {
    const { data } = await api.post<ApiResponse<{
      run_id: string;
      status: string;
      resume_phase?: string;
      message: string;
    }>>(`/pipeline/runs/${runId}/resume`);
    return data;
  },

  /** GET /api/v1/pipeline/audit-export/:runId */
  async exportAuditChain(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    const { data } = await api.get<ApiResponse<Record<string, unknown>>>(`/pipeline/audit-export/${runId}`);
    return data;
  },
  /** POST /api/v1/pipeline/loop-dry-run */
  async loopDryRun(body: {
    run_options?: Record<string, unknown>;
    quality_trend?: Array<Record<string, unknown>>;
    round_num?: number;
    hypothesis_review?: Record<string, unknown>;
    small_validation?: Record<string, unknown>;
    project_mode?: string;
  }): Promise<ApiResponse<{ summary?: string; [key: string]: unknown }>> {
    const { data } = await api.post<ApiResponse<Record<string, unknown>>>('/pipeline/loop-dry-run', body);
    return data;
  },

  /** GET /api/v1/pipeline/coordinator-hints/:runId — 获取大家长提示 */
  async getCoordinatorHints(runId: string): Promise<ApiResponse<{
    run_id: string;
    hints: Array<Record<string, unknown>>;
    coordinator_decisions: Array<Record<string, unknown>>;
    hint_count: number;
  }>> {
    const { data } = await api.get<ApiResponse<{
      run_id: string;
      hints: Array<Record<string, unknown>>;
      coordinator_decisions: Array<Record<string, unknown>>;
      hint_count: number;
    }>>(`/pipeline/coordinator-hints/${runId}`);
    return data;
  },

  /** POST /api/v1/pipeline/coordinator-hints/:runId/evidence-iteration-decision */
  async respondEvidenceIterationDecision(payload: {
    run_id: string;
    project_id: string;
    hint_id: string;
    decision: 'approve' | 'reject';
  }): Promise<ApiResponse<{
    run_id: string;
    parent_run_id?: string;
    decision: string;
    status: string;
    rerun_from_stage?: string;
    rerun_mode?: string;
  }>> {
    const { data } = await api.post(
      `/pipeline/coordinator-hints/${payload.run_id}/evidence-iteration-decision`,
      {
        project_id: payload.project_id,
        hint_id: payload.hint_id,
        decision: payload.decision,
      },
    );
    return data;
  },

  // ── 主动协调 ──

  /** GET /api/v1/pipeline/coordinator/advice/:projectId — 获取主动协调建议 */
  async getCoordinatorAdvice(projectId: string, status?: string, adviceType?: string): Promise<ApiResponse<{
    project_id: string;
    advice_list: Array<Record<string, unknown>>;
    count: number;
  }>> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (adviceType) params.set('advice_type', adviceType);
    const qs = params.toString();
    const { data } = await api.get(`/pipeline/coordinator/advice/${projectId}${qs ? '?' + qs : ''}`);
    return data;
  },

  /** POST /api/v1/pipeline/coordinator/advice/:adviceId/ack — 确认建议 */
  async acknowledgeAdvice(adviceId: string): Promise<ApiResponse<{ id: string }>> {
    const { data } = await api.post(`/pipeline/coordinator/advice/${adviceId}/ack`);
    return data;
  },

  /** POST /api/v1/pipeline/coordinator/advice/:adviceId/dismiss — 忽略建议 */
  async dismissAdvice(adviceId: string): Promise<ApiResponse<{ id: string }>> {
    const { data } = await api.post(`/pipeline/coordinator/advice/${adviceId}/dismiss`);
    return data;
  },

  /** GET /api/v1/pipeline/coordinator/readiness/:projectId — 获取项目就绪状态 */
  async getProjectReadiness(projectId: string): Promise<ApiResponse<{
    is_ready: boolean;
    issues: Array<Record<string, unknown>>;
    warnings: Array<Record<string, unknown>>;
    summary: string;
    check_time: string;
  }>> {
    const { data } = await api.get(`/pipeline/coordinator/readiness/${projectId}`);
    return data;
  },
};