import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface VectorIndexStats {
  project_id: string;
  exists: boolean;
  chunk_count: number;
  db_chunk_count?: number;
  in_sync?: boolean;
  dimension?: number;
  embedding_model?: string;
}

export const vectorService = {
  /** POST /api/v1/vector-search/build */
  async buildIndex(
    projectId: string,
    rebuild = false,
  ): Promise<ApiResponse<{ added_count: number; total_count: number }>> {
    const { data } = await api.post('/vector-search/build', null, {
      params: { project_id: projectId, rebuild },
    });
    return data;
  },

  /** GET /api/v1/vector-search/index/{projectId}/stats */
  async getIndexStats(projectId: string): Promise<ApiResponse<VectorIndexStats>> {
    const { data } = await api.get(`/vector-search/index/${projectId}/stats`);
    return data;
  },
};
