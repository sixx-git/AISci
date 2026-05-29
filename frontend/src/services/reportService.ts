import api from '@/lib/api';
import type { ApiResponse, ReportData } from '@/types';

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
  const extraMeta = (db.extra_metadata || {}) as Record<string, unknown>;
  const complianceCheckRaw =
    extraMeta.compliance_check || extraMeta.complianceCheck || undefined;
  const complianceCheck = complianceCheckRaw
    ? (complianceCheckRaw as unknown as ReportData['complianceCheck'])
    : undefined;
  const plots = (extraMeta.plots as ReportData['plots']) || [];

  return {
    id: db.id,
    title: db.title || db.paper_title || '科学假设与研究计划',
    generatedAt: db.created_at ? new Date(db.created_at).toLocaleString('zh-CN') : '',
    markdownContent: db.markdown_content || '',
    sections: complianceCheck?.items || [],
    complianceCheck,
    plots,
    mdDownloadUrl: db.report_id ? `/api/v1/reports/download/${db.report_id}/md` : undefined,
    pdfDownloadUrl: db.report_id && db.pdf_generated ? `/api/v1/reports/download/${db.report_id}/pdf` : undefined,
  };
}

export const reportService = {
  /** POST /api/v1/reports/generate */
  async generate(payload: Record<string, unknown>): Promise<ApiResponse<Record<string, unknown>>> {
    const { data } = await api.post<ApiResponse<Record<string, unknown>>>('/reports/generate', payload);
    return data;
  },

  /** GET /api/v1/reports/latest/:projectId */
  async getLatest(projectId: string): Promise<ReportData | null> {
    const { data } = await api.get<ApiResponse<ReportDbRaw | null>>(`/reports/latest/${projectId}`);
    if (data?.code === 200 && data?.data) {
      return mapDbToReportData(data.data);
    }
    return null;
  },

  /** GET /api/v1/reports/:projectId 列表 */
  async getList(projectId: string): Promise<ReportData[]> {
    const { data } = await api.get<ApiResponse<ReportDbRaw[]>>(`/reports/${projectId}`);
    if (data?.code === 200 && Array.isArray(data?.data)) {
      return data.data.map(mapDbToReportData);
    }
    return [];
  },

  /** GET /api/v1/reports/detail/:reportId */
  async getDetail(reportId: string): Promise<ReportData | null> {
    const { data } = await api.get<ApiResponse<ReportDbRaw | null>>(`/reports/detail/${reportId}`);
    if (data?.code === 200 && data?.data) {
      return mapDbToReportData(data.data);
    }
    return null;
  },

  /** GET /api/v1/reports/download/:reportId/:fileType */
  async download(reportId: string, fileType: 'pdf' | 'md'): Promise<Blob> {
    const { data } = await api.get(`/reports/download/${reportId}/${fileType}`, {
      responseType: 'blob',
    });
    return data;
  },
};