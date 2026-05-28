import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface BackendExperimentDesign {
  id: string;
  project_id: string;
  hypothesis_id: string;
  hypothesis: string;
  methods: string;
  datasets: string;
  source_data: string;
  target_data: string;
  baselines: string;
  metrics: string;
  experimental_steps: string;
  expected_results: string;
  limitations: string;
  status: string;
  priority: number;
  created_at: string;
  updated_at?: string;
}

const experimentService = {
  async getProjectExperimentDesigns(
    projectId: string,
  ): Promise<ApiResponse<BackendExperimentDesign[]>> {
    const { data } = await api.get<ApiResponse<BackendExperimentDesign[]>>(
      `/projects/${projectId}/experiment-designs`,
    );
    return data;
  },
};

export default experimentService;