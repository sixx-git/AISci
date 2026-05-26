import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse, ReportGenerationRequest, ReportGenerationResult } from '@/types';
import { MOCK_REPORT } from '@/data/mockData';

export const reportService = {
  /** POST /api/v1/reports/generate */
  async generate(payload: ReportGenerationRequest): Promise<ApiResponse<ReportGenerationResult>> {
    if (env.USE_MOCK) {
      console.log('[Mock] reportService.generate', payload);
      return {
        code: 200,
        message: '生成报告成功 (Mock)',
        data: {
          title: MOCK_REPORT.title,
          paper_title: '科学假设与研究计划',
          paper_abstract: '研究自适应特征选择在小样本泛化能力中的应用',
          markdown_content: MOCK_REPORT.markdownContent,
          report_id: 'mock-123',
          chapters: {},
          summary: '研究报告生成成功',
        },
      };
    }

    const { data } = await api.post('/reports/generate', payload);
    return data;
  },

  /** GET /api/v1/reports/download/:reportId/:fileType */
  async download(reportId: string, fileType: 'pdf' | 'md'): Promise<Blob> {
    if (env.USE_MOCK) {
      console.log('[Mock] reportService.download', reportId, fileType);
      const content = fileType === 'md' ? MOCK_REPORT.markdownContent : '%PDF-1.4... (Mock)';
      return new Blob([content], {
        type: fileType === 'pdf' ? 'application/pdf' : 'text/markdown',
      });
    }

    const { data } = await api.get(`/reports/download/${reportId}/${fileType}`, {
      responseType: 'blob',
    });
    return data;
  },
};