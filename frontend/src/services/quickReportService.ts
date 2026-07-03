import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface QuickReportStartResult {
  project_id: string;
  run_id: string;
  research_question: string;
  status: string;
}

export interface QuickReportPendingCandidate {
  candidate_id?: string;
  dataset_name?: string;
  source_platform?: string;
  availability?: string;
  url?: string;
  user_upload_status?: string;
}

export interface QuickReportStatus {
  run_id: string;
  project_id: string;
  status: string;
  awaiting_data_upload: boolean;
  pending_upload_count: number;
  uploaded_count: number;
  can_resume: boolean;
  pending_candidates: QuickReportPendingCandidate[];
  final_report_id?: string | null;
}

export const quickReportService = {
  async start(questionName: string, fileDescription: string): Promise<ApiResponse<QuickReportStartResult>> {
    const { data } = await api.post<ApiResponse<QuickReportStartResult>>(
      '/pipeline/quick-report',
      {
        question_name: questionName,
        file_description: fileDescription,
      },
      { timeout: 30000 },
    );
    return data;
  },

  async getStatus(runId: string): Promise<ApiResponse<QuickReportStatus>> {
    const { data } = await api.get<ApiResponse<QuickReportStatus>>(`/pipeline/quick-report/status/${runId}`);
    return data;
  },

  async resume(runId: string, force = false): Promise<ApiResponse<Record<string, unknown>>> {
    const { data } = await api.post<ApiResponse<Record<string, unknown>>>('/pipeline/quick-report/resume', {
      run_id: runId,
      force,
    });
    return data;
  },
};
