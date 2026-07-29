/**
 * pingfenbiao API 客户端。
 * 经 AISci 后端代理：/api/v1/pingfenbiao/* → http://127.0.0.1:8765/*
 *（走 Vite 已有的 /api → :8000，不依赖 /pingfenbiao 专用反代）
 */

const BASE = '/api/v1/pingfenbiao';

export type PredictTaskType =
  | 'claim_verification'
  | 'data_analysis'
  | 'literature_review';

export type PredictJobMode = 'generate' | 'score' | 'impact';

export interface PredictJobStatus {
  job_id?: string;
  job_mode?: PredictJobMode;
  status?: 'queued' | 'running' | 'completed' | 'failed' | string;
  progress?: number;
  message?: string;
  error?: string;
  logs?: string[];
  task_type?: string;
  rating?: Record<string, unknown>;
  total_score?: number;
  updated_at?: string;
  saved_path?: string | null;
  saved_paths?: Record<string, string> | null;
  [key: string]: unknown;
}

export interface ImpactHistoryItem {
  job_id: string;
  title?: string;
  venue?: string;
  year?: number | string | null;
  rating?: string;
  total_score?: number | null;
  citations?: number | null;
  completed_at?: string;
}

export type ImpactReport = Record<string, unknown>;

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(text || `请求失败 (${res.status})`);
  }
  if (!res.ok) {
    const detail =
      typeof data === 'object' && data && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : text || `请求失败 (${res.status})`;
    throw new Error(detail);
  }
  return data as T;
}

export const predictService = {
  async generate(form: FormData): Promise<{ job_id: string; job_mode?: string }> {
    const res = await fetch(`${BASE}/api/generate`, { method: 'POST', body: form });
    return parseJson(res);
  },

  async score(form: FormData): Promise<{ job_id: string; job_mode?: string }> {
    const res = await fetch(`${BASE}/api/score`, { method: 'POST', body: form });
    return parseJson(res);
  },

  async impact(form: FormData): Promise<{ job_id: string; job_mode?: string }> {
    const res = await fetch(`${BASE}/api/impact`, { method: 'POST', body: form });
    return parseJson(res);
  },

  async getStatus(jobId: string): Promise<PredictJobStatus> {
    const res = await fetch(`${BASE}/api/status/${jobId}`);
    return parseJson(res);
  },

  async getHistory(): Promise<ImpactHistoryItem[]> {
    const res = await fetch(`${BASE}/api/impact/history`);
    const data = await parseJson<ImpactHistoryItem[]>(res);
    return Array.isArray(data) ? data : [];
  },

  async getDetail(jobId: string): Promise<ImpactReport> {
    const res = await fetch(`${BASE}/api/impact/detail/${jobId}`);
    return parseJson(res);
  },

  async deleteImpact(jobId: string): Promise<void> {
    const res = await fetch(`${BASE}/api/impact/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
    });
    // 200/204 都视为成功；其余走 parseJson 抛错
    if (res.ok || res.status === 204) {
      return;
    }
    await parseJson(res);
  },

  downloadUrl(jobId: string, kind: 'task' | 'scores' | 'impact'): string {
    if (kind === 'task') return `${BASE}/api/download/${jobId}`;
    if (kind === 'scores') return `${BASE}/api/download/${jobId}/scores`;
    return `${BASE}/api/download/${jobId}/impact`;
  },
};
