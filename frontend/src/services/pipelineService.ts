import api from '@/lib/api';
import env from '@/config/env';
import type {
  ApiResponse,
  PipelineRunSummary,
  PipelineRunDetail,
  PipelineRunResult,
} from '@/types';
import { MOCK_RUN_LOGS } from '@/data/mockData';

// Mock 数据转换
const mockPipelineRuns: PipelineRunSummary[] = MOCK_RUN_LOGS.map((log) => ({
  id: log.id,
  run_id: log.id,
  project_id: '1',
  research_question: '基于自适应特征选择的小样本泛化能力提升研究',
  status: log.status === 'success' ? 'completed' : log.status === 'failed' ? 'failed' : 'running',
  created_at: log.timestampStart || new Date().toISOString(),
}));

// 阶段名称映射：后端 → 前端节点 ID
const STAGE_TO_NODE_MAP: Record<string, string> = {
  problem_understanding: 'problem',
  literature_mining: 'literature',
  knowledge_gap: 'gaps',
  hypothesis_generation: 'hypothesis',
  hypothesis_review: 'evaluation',
  experiment_design: 'experiment',
  small_validation: 'validation',
  report_generation: 'report',
};

export const pipelineService = {
  /** 阶段名称 → 前端节点 ID */
  STAGE_TO_NODE_MAP,

  /** POST /api/v1/pipeline/run */
  async run(
    projectId: string,
    researchQuestion: string,
    options?: Record<string, unknown>
  ): Promise<ApiResponse<PipelineRunResult>> {
    if (env.USE_MOCK) {
      console.log('[Mock] pipelineService.run', projectId, researchQuestion);
      // 模拟 PipelineRunResult
      const mockResult: PipelineRunResult = {
        pipeline_id: Date.now().toString(),
        run_id: Date.now().toString(),
        project_id: projectId,
        research_question: researchQuestion,
        status: 'completed',
        stages: [
          { stage: 'problem_understanding', status: 'completed', duration: 0.5 },
          { stage: 'literature_mining', status: 'completed', duration: 1.2 },
          { stage: 'knowledge_gap', status: 'completed', duration: 0.8 },
          { stage: 'hypothesis_generation', status: 'completed', duration: 1.0 },
          { stage: 'hypothesis_review', status: 'completed', duration: 0.9 },
          { stage: 'experiment_design', status: 'completed', duration: 0.7 },
          { stage: 'small_validation', status: 'completed', duration: 0.6 },
          { stage: 'report_generation', status: 'completed', duration: 1.5 },
        ],
        total_duration: 7.2,
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      };
      return {
        code: 200,
        message: 'Pipeline 执行成功 (Mock)',
        data: mockResult,
      };
    }

    const { data } = await api.post('/pipeline/run', {
      project_id: projectId,
      research_question: researchQuestion,
      options: options || {},
    });
    return data;
  },

  /** GET /api/v1/pipeline/status/:runId — 轮询运行状态 */
  async getStatus(runId: string): Promise<ApiResponse<PipelineRunResult>> {
    if (env.USE_MOCK) {
      console.log('[Mock] pipelineService.getStatus', runId);
      return {
        code: 200,
        message: '获取状态成功 (Mock)',
        data: {
          pipeline_id: runId,
          run_id: runId,
          project_id: '1',
          research_question: '',
          status: 'completed',
          stages: [],
          created_at: new Date().toISOString(),
        },
      };
    }

    const { data } = await api.get(`/pipeline/status/${runId}`);
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