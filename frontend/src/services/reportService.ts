import api from '@/lib/api';
import type { ApiResponse, ReportGenerationRequest, ReportGenerationResult } from '@/types';

export const reportService = {
  /** POST /api/v1/reports/generate */
  async generate(payload: ReportGenerationRequest): Promise<ApiResponse<ReportGenerationResult>> {
    const { data } = await api.post('/reports/generate', payload);
    return data;
  },

  /** GET /api/v1/reports/download/:reportId/:fileType */
  async download(reportId: string, fileType: 'pdf' | 'md'): Promise<Blob> {
    const { data } = await api.get(`/reports/download/${reportId}/${fileType}`, {
      responseType: 'blob',
    });
    return data;
  },
};