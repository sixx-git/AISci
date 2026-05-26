import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export const vectorService = {
  /** POST /api/v1/vector-search/build */
  async buildIndex(projectId: string): Promise<ApiResponse<{ added_count: number; total_count: number }>> {
    const { data } = await api.post('/vector-search/build', null, {
      params: { project_id: projectId },
    });
    return data;
  },

  /** POST /api/v1/vector-search/search */
  async search(
    projectId: string,
    query: string,
    topK = 5,
  ): Promise<ApiResponse<{ results: unknown[]; total: number }>> {
    const { data } = await api.post('/vector-search/search', { query, top_k: topK }, {
      params: { project_id: projectId },
    });
    return data;
  },
};