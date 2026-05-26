import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse } from '@/types';

export const vectorService = {
  /** POST /api/v1/vector-search/build */
  async buildIndex(projectId: string): Promise<ApiResponse<{ added_count: number }>> {
    if (env.USE_MOCK) {
      console.log('[Mock] vectorService.buildIndex', projectId);
      return {
        code: 200,
        message: '构建向量索引成功 (Mock)',
        data: { added_count: 23 },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] vectorService.search', projectId, query);
      return {
        code: 200,
        message: '向量搜索成功 (Mock)',
        data: {
          results: [
            { id: 's1', content: '特征选择对小样本学习有正向影响' },
            { id: 's2', content: '元学习框架适合跨任务泛化' },
          ],
          total: 2,
        },
      };
    }

    const { data } = await api.post('/vector-search/search', { query, top_k: topK }, {
      params: { project_id: projectId },
    });
    return data;
  },
};