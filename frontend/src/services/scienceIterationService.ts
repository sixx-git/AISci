import api from '@/lib/api';
import type {
  ApiResponse,
  HypothesisProvenance,
  ScienceIterationConfig,
  ScienceIterationSession,
} from '@/types';

const scienceIterationService = {
  async getHypothesisProvenance(
    projectId: string,
    hypothesisId: string,
    runId?: string | null,
  ): Promise<ApiResponse<HypothesisProvenance>> {
    const params = runId ? { run_id: runId } : undefined;
    const { data } = await api.get<ApiResponse<HypothesisProvenance>>(
      `/science-iteration/projects/${projectId}/hypotheses/${hypothesisId}/provenance`,
      { params },
    );
    return data;
  },

  async getIterationSession(runId: string): Promise<ApiResponse<ScienceIterationSession>> {
    const { data } = await api.get<ApiResponse<ScienceIterationSession>>(
      `/science-iteration/runs/${runId}/session`,
    );
    return data;
  },

  async getIterationConfig(projectId: string): Promise<ApiResponse<ScienceIterationConfig>> {
    const { data } = await api.get<ApiResponse<ScienceIterationConfig>>(
      `/science-iteration/projects/${projectId}/config`,
    );
    return data;
  },
};

export default scienceIterationService;
