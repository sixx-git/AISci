import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse, ReportGenerationRequest, ReportGenerationResult, ReportData } from '@/types';
import { MOCK_REPORT } from '@/data/mockData';

/** 后端 ReportDBResponse 原始格式 */
interface ReportDbRaw {
  id: string;
  project_id: string;
  title: string;
  paper_title: string;
  paper_abstract: string;
  markdown_content: string;
  problem_statement: string;
  rationale: string;
  technical_details: string;
  datasets: string;
  source: string;
  target: string;
  methods: string;
  experiments: string;
  results: string;
  references: string;
  report_id?: string;
  pdf_generated?: boolean;
  status: string;
  version: number;
  extra_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

function mapDbToReportData(db: ReportDbRaw): ReportData {
  // 从 extra_metadata 提取合规性检查
  const complianceCheck = db.extra_metadata as ReportData['complianceCheck'];

  return {
    id: db.id,
    title: db.title || db.paper_title || '科学假设与研究计划',
    generatedAt: db.created_at ? new Date(db.created_at).toLocaleString('zh-CN') : '',
    markdownContent: db.markdown_content || '',
    sections: complianceCheck?.items || [],
    complianceCheck,
    // 构建下载 URL
    mdDownloadUrl: db.report_id ? `/api/v1/reports/download/${db.report_id}/md` : undefined,
    pdfDownloadUrl: db.report_id && db.pdf_generated ? `/api/v1/reports/download/${db.report_id}/pdf` : undefined,
  };
}

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
          pdf_download_url: '/api/v1/reports/download/mock-123/pdf',
          md_download_url: '/api/v1/reports/download/mock-123/md',
          pdf_success: true,
          chapters: {},
          summary: '研究报告生成成功',
          compliance_check: MOCK_REPORT.complianceCheck,
        },
      };
    }

    const { data } = await api.post('/reports/generate', payload);
    return data;
  },

  /** GET /api/v1/reports/latest/:projectId */
  async getLatest(projectId: string): Promise<ReportData | null> {
    if (env.USE_MOCK) {
      console.log('[Mock] reportService.getLatest', projectId);
      return MOCK_REPORT;
    }

    const { data } = await api.get(`/reports/latest/${projectId}`);
    if (data?.code === 200 && data?.data) {
      return mapDbToReportData(data.data);
    }
    return null;
  },

  /** GET /api/v1/reports/:projectId 列表 */
  async getList(projectId: string): Promise<ReportData[]> {
    if (env.USE_MOCK) {
      console.log('[Mock] reportService.getList', projectId);
      return [MOCK_REPORT];
    }

    const { data } = await api.get(`/reports/${projectId}`);
    if (data?.code === 200 && Array.isArray(data?.data)) {
      return data.data.map(mapDbToReportData);
    }
    return [];
  },

  /** GET /api/v1/reports/detail/:reportId */
  async getDetail(reportId: string): Promise<ReportData | null> {
    if (env.USE_MOCK) {
      console.log('[Mock] reportService.getDetail', reportId);
      return MOCK_REPORT;
    }

    const { data } = await api.get(`/reports/detail/${reportId}`);
    if (data?.code === 200 && data?.data) {
      return mapDbToReportData(data.data);
    }
    return null;
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