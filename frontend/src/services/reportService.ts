import api from '@/lib/api';
import type { ApiResponse, ReportData, ComplianceCheck } from '@/types';
import { extractComplianceCheck, reconcileComplianceForDisplay } from '@/lib/reportCompliance';

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
  pdf_path?: string;
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

  const rawCompliance = extractComplianceCheck(extraMeta);
  const qcFromMeta = extraMeta.report_quality_check as ComplianceCheck['report_quality_check'];
  let complianceCheck = reconcileComplianceForDisplay(rawCompliance, db.references);
  if (qcFromMeta && typeof qcFromMeta === 'object') {
    complianceCheck = {
      ...(complianceCheck ?? {
        completed: 0,
        missing: 0,
        human_review: 0,
        references_verified: 0,
        references_suspicious: 0,
        evidence_fact_count: 0,
        hypothesis_with_evidence_count: 0,
        has_actual_or_simulated_result: false,
        items: [],
      }),
      report_quality_check: qcFromMeta,
    };
  }

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

  const fileId = db.report_id || db.pdf_path;
  const exportMethod = extraMeta.export_method as string | undefined;
  const pdfSuccessMeta = extraMeta.pdf_success;
  const pdfFileExists = Boolean(db.pdf_generated);
  const pdfSuccessFlag =
    pdfSuccessMeta === true || pdfSuccessMeta === 1 || pdfSuccessMeta === '1';
  const latexPdfSuccess =
    exportMethod === 'latex' && (pdfSuccessFlag || pdfFileExists);
  const pdfDownloadable = latexPdfSuccess;

  return {
    id: db.id,
    title: db.title || db.paper_title || '科学假设与研究计划',
    generatedAt: db.created_at ? new Date(db.created_at).toLocaleString('zh-CN') : '',
    sections: complianceCheck?.items || [],
    complianceCheck,
    plots,
    pdfSuccess: latexPdfSuccess,
    exportMethod,
    texDownloadUrl: fileId ? `/api/v1/reports/download/${db.id}/tex` : undefined,
    pdfDownloadUrl: fileId && pdfDownloadable ? `/api/v1/reports/download/${db.id}/pdf` : undefined,
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

  /** POST /api/v1/reports/:reportId/regenerate-pdf */
  async regeneratePdf(reportId: string): Promise<ApiResponse<{
    success?: boolean;
    pdf_success?: boolean;
    warning?: string;
    export_method?: string;
  }>> {
    const { data } = await api.post<ApiResponse<{
      success?: boolean;
      pdf_success?: boolean;
      warning?: string;
      export_method?: string;
    }>>(`/reports/${reportId}/regenerate-pdf`);
    return data;
  },

  /** GET /api/v1/reports/download/:reportId/:fileType */
  async download(reportId: string, fileType: 'pdf' | 'tex'): Promise<Blob> {
    const response = await api.get(`/reports/download/${reportId}/${fileType}`, {
      responseType: 'blob',
    });
    const contentType = String(response.headers['content-type'] || '');
    if (fileType === 'pdf' && !contentType.includes('pdf')) {
      throw new Error('响应不是 PDF 文件');
    }
    return response.data;
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