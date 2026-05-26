import api from '@/lib/api';
import type {
  ApiResponse,
  PipelineRunSummary,
  PipelineRunDetail,
} from '@/types';

export const pipelineService = {
  /** POST /api/v1/pipeline/run */
  async run(projectId: string, researchQuestion: string): Promise<ApiResponse<unknown>> {
    const { data } = await api.post('/pipeline/run', {
      project_id: projectId,
      research_question: researchQuestion,
    });
    return data;
  },

  /** GET /api/v1/pipeline/runs/:projectId */
  async getRuns(projectId: string): Promise<ApiResponse<PipelineRunSummary[]>> {
    const { data } = await api.get(`/pipeline/runs/${projectId}`);
    return data;
  },

  /** GET /api/v1/pipeline/run/:runId */
  async getRunDetail(runId: string): Promise<ApiResponse<PipelineRunDetail>> {
    const { data } = await api.get(`/pipeline/run/${runId}`);
    return data;
  },
};