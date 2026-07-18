/**
 * 迭代实验 API 客户端（真实 shaxiang 后端；失败直接抛错，无 localStorage mock）
 */
import api from '@/lib/api';
import type { ApiResponse } from '@/types';
import type {
  DataConfig,
  IterativeExperiment,
  IterationRecordMock,
  RunMode,
} from '@/types/iterativeExperiment';

/** 设计脚本 / smoke 修复 / 多轮迭代：最长 60 分钟 */
const LONG_OP_TIMEOUT_MS = 60 * 60 * 1000;

function unwrap<T>(res: ApiResponse<T>, fallbackMsg = '请求失败'): T {
  if (res.code !== 200 || res.data === undefined || res.data === null) {
    throw new Error(res.message || fallbackMsg);
  }
  return res.data;
}

export const iterativeExperimentService = {
  async list(projectId: string): Promise<{
    experiments: IterativeExperiment[];
    reportExperimentIds: string[];
  }> {
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

  async get(projectId: string, experimentId: string): Promise<IterativeExperiment | null> {
    const { data } = await api.get<ApiResponse<IterativeExperiment>>(
      `/iterative-experiments/${experimentId}`,
      { params: { project_id: projectId } },
    );
    if (data.code === 404) return null;
    return unwrap(data);
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
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments`,
      input,
      { timeout: 300000 },
    );
    return unwrap(data, '创建实验失败');
  },

  async delete(projectId: string, experimentId: string): Promise<void> {
    const { data } = await api.delete<ApiResponse<{ deleted: boolean }>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}`,
    );
    unwrap(data);
  },

  async toggleReport(projectId: string, experimentId: string): Promise<string[]> {
    const { data } = await api.post<ApiResponse<{ report_experiment_ids: string[] }>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/toggle-report`,
    );
    return unwrap(data).report_experiment_ids || [];
  },

  async recommendDatasets(
    projectId: string,
    experimentId: string,
    feedback?: string,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/recommend-datasets`,
      { feedback: feedback || '' },
      { timeout: 300000 },
    );
    return unwrap(data, '推荐数据集失败');
  },

  async uploadDataset(
    projectId: string,
    experimentId: string,
    file: File,
  ): Promise<{
    data_config: DataConfig;
    preview: Record<string, unknown>;
    experiment: IterativeExperiment;
  }> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<
      ApiResponse<{
        data_config: DataConfig;
        preview: Record<string, unknown>;
        experiment: IterativeExperiment;
      }>
    >(`/projects/${projectId}/iterative-experiments/${experimentId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return unwrap(data, '上传失败');
  },

  async verifyData(
    projectId: string,
    experimentId: string,
    dataConfig: DataConfig,
  ): Promise<{ ok: boolean; preview: Record<string, unknown> }> {
    const { data } = await api.post<ApiResponse<{ ok: boolean; preview: Record<string, unknown> }>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/verify-data`,
      { data_config: dataConfig },
    );
    return unwrap(data, '数据校验失败');
  },

  async autoDetectProfile(
    projectId: string,
    experimentId: string,
    directoryPath: string,
  ): Promise<{
    profile: Record<string, unknown>;
    preview: Record<string, unknown>;
    data_config: DataConfig;
  }> {
    const { data } = await api.post<
      ApiResponse<{
        profile: Record<string, unknown>;
        preview: Record<string, unknown>;
        data_config: DataConfig;
      }>
    >(`/projects/${projectId}/iterative-experiments/${experimentId}/auto-detect-profile`, {
      directory_path: directoryPath,
    }, { timeout: 300000 });
    return unwrap(data, '自动识别失败');
  },

  async designScript(
    projectId: string,
    experimentId: string,
    dataConfig?: DataConfig,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/design-script`,
      { data_config: dataConfig },
      { timeout: LONG_OP_TIMEOUT_MS },
    );
    return unwrap(data, '设计脚本失败');
  },

  async setRunMode(
    projectId: string,
    experimentId: string,
    runMode: RunMode,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/run-mode`,
      { run_mode: runMode },
    );
    return unwrap(data);
  },

  async runIteration(
    projectId: string,
    experimentId: string,
  ): Promise<{ record: IterationRecordMock; experiment: IterativeExperiment | null }> {
    const { data } = await api.post<
      ApiResponse<{ record: IterationRecordMock; experiment: IterativeExperiment }>
    >(`/projects/${projectId}/iterative-experiments/${experimentId}/run-iteration`, null, {
      timeout: LONG_OP_TIMEOUT_MS,
    });
    const payload = unwrap(data, '执行迭代失败');
    return { record: payload.record, experiment: payload.experiment ?? null };
  },

  async runToCompletion(projectId: string, experimentId: string): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/run-to-completion`,
      null,
      { timeout: LONG_OP_TIMEOUT_MS },
    );
    return unwrap(data, '自动运行失败');
  },

  async submitFeedback(
    projectId: string,
    experimentId: string,
    feedback: string,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/feedback`,
      { feedback },
    );
    return unwrap(data);
  },

  async redesignFromFeedback(
    projectId: string,
    experimentId: string,
    feedback: string,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/redesign`,
      { feedback },
      { timeout: LONG_OP_TIMEOUT_MS },
    );
    return unwrap(data, '重设计脚本失败');
  },
};

export default iterativeExperimentService;
