/**
 * 迭代实验 API 客户端；失败时降级到 localStorage mock，保证前端可联调。
 */
import api from '@/lib/api';
import type { ApiResponse } from '@/types';
import type {
  DataConfig,
  IterativeExperiment,
  IterationRecordMock,
  RunMode,
} from '@/types/iterativeExperiment';
import { iterativeExperimentMock } from '@/services/iterativeExperimentMock';

function unwrap<T>(res: ApiResponse<T>, fallbackMsg = '请求失败'): T {
  if (res.code !== 200 || res.data === undefined || res.data === null) {
    throw new Error(res.message || fallbackMsg);
  }
  return res.data;
}

async function withMockFallback<T>(
  apiCall: () => Promise<T>,
  mockCall: () => T | Promise<T>,
): Promise<T> {
  try {
    return await apiCall();
  } catch (err) {
    if (import.meta.env.DEV) {
      console.warn('[iterativeExperiment] API 失败，降级 mock:', err);
    }
    return mockCall();
  }
}

export const iterativeExperimentService = {
  async list(projectId: string): Promise<{
    experiments: IterativeExperiment[];
    reportExperimentIds: string[];
  }> {
    return withMockFallback(
      async () => {
        const { data } = await api.get<
          ApiResponse<{ items: IterativeExperiment[]; report_experiment_ids: string[] }>
        >(`/projects/${projectId}/iterative-experiments`);
        const payload = unwrap(data);
        return {
          experiments: Array.isArray(payload.items) ? payload.items : [],
          reportExperimentIds: Array.isArray(payload.report_experiment_ids)
            ? payload.report_experiment_ids
            : [],
        };
      },
      () => ({
        experiments: iterativeExperimentMock.list(projectId),
        reportExperimentIds: iterativeExperimentMock.getReportExperimentIds(projectId),
      }),
    );
  },

  async get(projectId: string, experimentId: string): Promise<IterativeExperiment | null> {
    return withMockFallback(
      async () => {
        const { data } = await api.get<ApiResponse<IterativeExperiment>>(
          `/iterative-experiments/${experimentId}`,
          { params: { project_id: projectId } },
        );
        if (data.code === 404) return null;
        return unwrap(data);
      },
      () => iterativeExperimentMock.get(projectId, experimentId),
    );
  },

  async create(
    projectId: string,
    input: {
      hypothesis: string;
      research_goal?: string;
      constraints?: string[];
      executor_type: 'sandbox' | 'simulation';
      max_iterations: number;
    },
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments`,
          input,
        );
        return unwrap(data, '创建实验失败');
      },
      () => iterativeExperimentMock.create(projectId, input),
    );
  },

  async delete(projectId: string, experimentId: string): Promise<void> {
    return withMockFallback(
      async () => {
        const { data } = await api.delete<ApiResponse<{ deleted: boolean }>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}`,
        );
        unwrap(data);
      },
      () => iterativeExperimentMock.delete(projectId, experimentId),
    );
  },

  async toggleReport(projectId: string, experimentId: string): Promise<string[]> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<{ report_experiment_ids: string[] }>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/toggle-report`,
        );
        return unwrap(data).report_experiment_ids || [];
      },
      () => iterativeExperimentMock.toggleReportExperiment(projectId, experimentId),
    );
  },

  async recommendDatasets(
    projectId: string,
    experimentId: string,
    feedback?: string,
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/recommend-datasets`,
          { feedback: feedback || '' },
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.recommendDatasets(projectId, experimentId, feedback),
    );
  },

  async designScript(
    projectId: string,
    experimentId: string,
    dataConfig?: DataConfig,
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/design-script`,
          { data_config: dataConfig },
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.designScript(projectId, experimentId, dataConfig),
    );
  },

  async setRunMode(
    projectId: string,
    experimentId: string,
    runMode: RunMode,
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/run-mode`,
          { run_mode: runMode },
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.setRunMode(projectId, experimentId, runMode),
    );
  },

  async runIteration(
    projectId: string,
    experimentId: string,
  ): Promise<{ record: IterationRecordMock; experiment: IterativeExperiment | null }> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<
          ApiResponse<{ record: IterationRecordMock; experiment: IterativeExperiment }>
        >(`/projects/${projectId}/iterative-experiments/${experimentId}/run-iteration`);
        const payload = unwrap(data);
        return { record: payload.record, experiment: payload.experiment ?? null };
      },
      () => {
        const record = iterativeExperimentMock.runIteration(projectId, experimentId);
        return {
          record,
          experiment: iterativeExperimentMock.get(projectId, experimentId),
        };
      },
    );
  },

  async runToCompletion(projectId: string, experimentId: string): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/run-to-completion`,
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.runToCompletion(projectId, experimentId),
    );
  },

  async submitFeedback(
    projectId: string,
    experimentId: string,
    feedback: string,
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/feedback`,
          { feedback },
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.submitFeedback(projectId, experimentId, feedback),
    );
  },

  async redesignFromFeedback(
    projectId: string,
    experimentId: string,
    feedback: string,
  ): Promise<IterativeExperiment> {
    return withMockFallback(
      async () => {
        const { data } = await api.post<ApiResponse<IterativeExperiment>>(
          `/projects/${projectId}/iterative-experiments/${experimentId}/redesign`,
          { feedback },
        );
        return unwrap(data);
      },
      () => iterativeExperimentMock.redesignFromFeedback(projectId, experimentId, feedback),
    );
  },
};

export default iterativeExperimentService;
