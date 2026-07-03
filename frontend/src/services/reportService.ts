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
  const plots = (extraMeta.plots as ReportData['plots']) || [];

  const complianceCheck = Object.keys(extraMeta).length > 0
    ? (extraMeta as unknown as ReportData['complianceCheck'])
    : undefined;

  const reportContent: Record<string, string> = {
    title: db.title || '',
    paper_title: db.paper_title || '',
    paper_abstract: db.paper_abstract || '',
    problem_statement: db.problem_statement || '',
    rationale: db.rationale || '',
    technical_details: db.technical_details || '',
    datasets: db.datasets || '',
    source: db.source || '',
    target: db.target || '',
    methods: db.methods || '',
    experiments: db.experiments || '',
    results: db.results || '',
    references: db.references || '',
    markdown_content: db.markdown_content || '',
  };

  return {
    id: db.id,
    title: db.title || db.paper_title || '科学假设与研究计划',
    generatedAt: db.created_at ? new Date(db.created_at).toLocaleString('zh-CN') : '',
    markdownContent: db.markdown_content || '',
    sections: complianceCheck?.items || [],
    complianceCheck,
    plots,
    mdDownloadUrl: db.report_id ? `/api/v1/reports/download/${db.report_id}/md` : undefined,
    texDownloadUrl: db.report_id ? `/api/v1/reports/download/${db.report_id}/tex` : undefined,
    pdfDownloadUrl: db.report_id && db.pdf_generated ? `/api/v1/reports/download/${db.report_id}/pdf` : undefined,
    extraMetadata: extraMeta,
    reportContent,
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
  async download(reportId: string, fileType: 'pdf' | 'md' | 'tex'): Promise<Blob> {
    const { data } = await api.get(`/reports/download/${reportId}/${fileType}`, {
      responseType: 'blob',
    });
    return data;
  },

  /** GET /api/v1/reports/browse — 报告中心分页列表 */
  async browse(params: {
    page?: number;
    page_size?: number;
    project_mode?: string;
    date_from?: string;
    date_to?: string;
    keyword?: string;
  }): Promise<ApiResponse<ReportBrowsePage>> {
    const { data } = await api.get<ApiResponse<ReportBrowsePage>>('/reports/browse', { params });
    return data;
  },
};

export interface ReportBrowseItem {
  id: string;
  project_id: string;
  project_name: string;
  project_mode: 'general' | 'federated_learning' | string;
  research_question?: string | null;
  title: string;
  paper_title: string;
  status: string;
  version: number;
  created_at: string;
  updated_at?: string | null;
}

export interface ReportBrowsePage {
  list: ReportBrowseItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}