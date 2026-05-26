import api from '@/lib/api';
import env from '@/config/env';
import type {
  ApiResponse,
  PipelineRunSummary,
  PipelineRunDetail,
} from '@/types';
import { MOCK_RUN_LOGS } from '@/data/mockData';

// Mock 数据转换
const mockPipelineRuns: PipelineRunSummary[] = MOCK_RUN_LOGS.map((log) => ({
  id: log.id,
  run_id: log.id,
  project_id: '1',
  research_question: '基于自适应特征选择的小样本泛化能力提升研究',
  status: log.status === 'success' ? 'completed' : log.status === 'failed' ? 'failed' : 'running',
  created_at: log.timestampStart,
}));

export const pipelineService = {
  /** POST /api/v1/pipeline/run */
  async run(projectId: string, researchQuestion: string): Promise<ApiResponse<unknown>> {
    if (env.USE_MOCK) {
      console.log('[Mock] pipelineService.run', projectId, researchQuestion);
      return {
        code: 200,
        message: 'Pipeline 启动成功 (Mock)',
        data: { pipeline_id: Date.now().toString(), status: 'running' },
      };
    }

    const { data } = await api.post('/pipeline/run', {
      project_id: projectId,
      research_question: researchQuestion,
    });
    return data;
  },

  /** GET /api/v1/pipeline/runs/:projectId */
  async getRuns(projectId: string): Promise<ApiResponse<PipelineRunSummary[]>> {
    if (env.USE_MOCK) {
      console.log('[Mock] pipelineService.getRuns', projectId);
      return {
        code: 200,
        message: '获取 Pipeline 运行历史成功 (Mock)',
        data: mockPipelineRuns,
      };
    }

    const { data } = await api.get(`/pipeline/runs/${projectId}`);
    return data;
  },

  /** GET /api/v1/pipeline/run/:runId */
  async getRunDetail(runId: string): Promise<ApiResponse<PipelineRunDetail>> {
    if (env.USE_MOCK) {
      console.log('[Mock] pipelineService.getRunDetail', runId);
      const run = mockPipelineRuns[0];
      return {
        code: 200,
        message: '获取 Pipeline 运行详情成功 (Mock)',
        data: {
          ...run,
          stages: [],
        },
      };
    }

    const { data } = await api.get(`/pipeline/run/${runId}`);
    return data;
  },
};