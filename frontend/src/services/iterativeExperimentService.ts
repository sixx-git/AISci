/**
 * 迭代实验 API 客户端（真实 shaxiang 后端；失败直接抛错，无 localStorage mock）
 */
import api from '@/lib/api';
import type { ApiResponse } from '@/types';
import type {
  DataConfig,
  IterativeExperiment,
  IterationRecordMock,
  QualityMode,
  RunMode,
} from '@/types/iterativeExperiment';

/** 设计脚本 / smoke 修复 / 多轮迭代：最长 60 分钟 */
const LONG_OP_TIMEOUT_MS = 60 * 60 * 1000;
const JOB_POLL_INTERVAL_MS = 2000;
/** 启动后台任务本身应很快返回 */
const JOB_START_TIMEOUT_MS = 60_000;

export type IterativeExperimentJob = {
  job_id: string;
  project_id: string;
  experiment_id: string;
  kind: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | string;
  created_at?: string;
  updated_at?: string;
  error?: string | null;
  message?: string;
  result?: IterativeExperiment | null;
};

function unwrap<T>(res: ApiResponse<T>, fallbackMsg = '请求失败'): T {
  if (res.code !== 200 || res.data === undefined || res.data === null) {
    throw new Error(res.message || fallbackMsg);
  }
  return res.data;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function pollJobUntilDone(
  projectId: string,
  jobId: string,
  fallbackMsg: string,
): Promise<IterativeExperiment> {
  const deadline = Date.now() + LONG_OP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(JOB_POLL_INTERVAL_MS);
    const { data } = await api.get<ApiResponse<IterativeExperimentJob>>(
      `/projects/${projectId}/iterative-experiments/jobs/${jobId}`,
      { timeout: 30_000 },
    );
    const job = unwrap(data, '查询任务状态失败');
    if (job.status === 'succeeded') {
      if (!job.result || typeof job.result !== 'object') {
        throw new Error(`${fallbackMsg}：任务完成但未返回实验数据`);
      }
      return job.result;
    }
    if (job.status === 'failed') {
      throw new Error(job.error || fallbackMsg);
    }
  }
  throw new Error(`${fallbackMsg}：等待超时`);
}

export const iterativeExperimentService = {
  /** 轮询已启动的后台任务直至完成（页面恢复 active-job 时使用）。 */
  async pollJob(projectId: string, jobId: string): Promise<IterativeExperiment> {
    return pollJobUntilDone(projectId, jobId, '后台任务失败');
  },

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
      skip_dataset_recommend?: boolean;
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

  async getJob(projectId: string, jobId: string): Promise<IterativeExperimentJob> {
    const { data } = await api.get<ApiResponse<IterativeExperimentJob>>(
      `/projects/${projectId}/iterative-experiments/jobs/${jobId}`,
    );
    return unwrap(data, '查询任务失败');
  },

  async getActiveJob(
    projectId: string,
    experimentId: string,
  ): Promise<IterativeExperimentJob | null> {
    const { data } = await api.get<ApiResponse<{ job: IterativeExperimentJob | null }>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/active-job`,
    );
    return unwrap(data).job ?? null;
  },

  async designScript(
    projectId: string,
    experimentId: string,
    dataConfig?: DataConfig,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperimentJob | IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/design-script`,
      { data_config: dataConfig },
      { timeout: JOB_START_TIMEOUT_MS },
    );
    const payload = unwrap(data, '设计脚本失败');
    // 新协议：立即返回 job；兼容旧后端直接返回实验
    if (payload && typeof payload === 'object' && 'job_id' in payload && (payload as IterativeExperimentJob).job_id) {
      return pollJobUntilDone(projectId, (payload as IterativeExperimentJob).job_id, '设计脚本失败');
    }
    return payload as IterativeExperiment;
  },

  async listFlScriptTemplates(projectId: string): Promise<Array<{
    id: string;
    path?: string;
    recommended_when?: string;
    setting?: string;
    preview?: string;
    content?: string;
    exists?: boolean;
  }>> {
    const { data } = await api.get<
      ApiResponse<{ items: Array<Record<string, unknown>>; count: number }>
    >(`/projects/${projectId}/fl-pack/scripts`);
    const payload = unwrap(data);
    return Array.isArray(payload.items)
      ? (payload.items as Array<{
          id: string;
          path?: string;
          recommended_when?: string;
          setting?: string;
          preview?: string;
          content?: string;
          exists?: boolean;
        }>)
      : [];
  },

  async applyFlScript(
    projectId: string,
    experimentId: string,
    scriptId: string,
  ): Promise<IterativeExperiment> {
    /** 以 FL 模板为反馈，后台设计/重设计脚本（与 designScript 同协议）。 */
    const { data } = await api.post<ApiResponse<IterativeExperimentJob | IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/apply-fl-script`,
      { script_id: scriptId },
      { timeout: JOB_START_TIMEOUT_MS },
    );
    const payload = unwrap(data, '基于 FL 模板设计脚本失败');
    if (payload && typeof payload === 'object' && 'job_id' in payload && (payload as IterativeExperimentJob).job_id) {
      return pollJobUntilDone(
        projectId,
        (payload as IterativeExperimentJob).job_id,
        '基于 FL 模板设计脚本失败',
      );
    }
    return payload as IterativeExperiment;
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

  async setQualityMode(
    projectId: string,
    experimentId: string,
    qualityMode: QualityMode,
  ): Promise<IterativeExperiment> {
    const { data } = await api.post<ApiResponse<IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/quality-mode`,
      { quality_mode: qualityMode },
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
    const { data } = await api.post<ApiResponse<IterativeExperimentJob | IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/run-to-completion`,
      null,
      { timeout: JOB_START_TIMEOUT_MS },
    );
    const payload = unwrap(data, '自动运行失败');
    if (payload && typeof payload === 'object' && 'job_id' in payload && (payload as IterativeExperimentJob).job_id) {
      return pollJobUntilDone(projectId, (payload as IterativeExperimentJob).job_id, '自动运行失败');
    }
    return payload as IterativeExperiment;
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
    const { data } = await api.post<ApiResponse<IterativeExperimentJob | IterativeExperiment>>(
      `/projects/${projectId}/iterative-experiments/${experimentId}/redesign`,
      { feedback },
      { timeout: JOB_START_TIMEOUT_MS },
    );
    const payload = unwrap(data, '重设计脚本失败');
    if (payload && typeof payload === 'object' && 'job_id' in payload && (payload as IterativeExperimentJob).job_id) {
      return pollJobUntilDone(
        projectId,
        (payload as IterativeExperimentJob).job_id,
        '重设计脚本失败',
      );
    }
    return payload as IterativeExperiment;
  },
};

export default iterativeExperimentService;
