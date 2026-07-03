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
};