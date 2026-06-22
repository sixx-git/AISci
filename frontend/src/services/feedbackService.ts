import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface FeedbackEntry {
  id?: string;
  source?: string;
  message?: string;
  target?: string;
  constraints?: string[];
  trigger_rerun?: boolean;
  applied?: boolean;
  created_at?: string;
}

export interface FeedbackSubmitResult {
  entry?: FeedbackEntry;
  global_constraints?: string[];
  suggested_rerun_stages?: string[];
  side_effects?: Record<string, unknown>;
}

const feedbackService = {
  async submit(payload: {
    project_id: string;
    source?: string;
    message: string;
    target?: string;
    payload?: Record<string, unknown>;
    trigger_rerun?: boolean;
  }): Promise<ApiResponse<FeedbackSubmitResult>> {
    const { data } = await api.post('/feedback/submit', payload);
    return data;
  },

  async getConstraints(projectId: string): Promise<ApiResponse<{
    global_constraints?: string[];
    recent_entries?: FeedbackEntry[];
  }>> {
    const { data } = await api.get('/feedback/constraints', { params: { project_id: projectId } });
    return data;
  },
};

export default feedbackService;
