import api from '@/lib/api';
import type { ApiResponse } from '@/types';

// ==================== 类型定义 ====================

/** 可用的文献来源 */
export interface LiteratureSource {
  id: string;
  name: string;
  description: string;
  features: string[];
  supports_pdf: boolean;
}

/** arXiv 搜索结果中的单篇论文 */
export interface ArxivPaper {
  title: string;
  authors: string;
  abstract: string;
  published_at: string | null;
  categories: string;
  external_id: string;
  source_url: string;
  pdf_url: string;
  source_type: string;
  doi?: string | null;
  journal_ref?: string | null;
  comment?: string | null;
}

/** 已入库的文献记录 */
export interface ImportedDocument {
  id: string;
  title: string;
  authors: string;
  abstract?: string;
  doi?: string;
  external_id?: string;
  source_type?: 'upload' | 'arxiv' | 'bibtex' | 'google_scholar_import' | 'manual';
  source_url?: string;
  pdf_url?: string;
  library_scope?: 'base' | 'project' | 'personal';
  import_status?: 'discovered' | 'imported' | 'pdf_downloaded' | 'parsed' | 'indexed' | 'failed';
  is_personal?: boolean;
  created_at?: string;
}

/** 搜索响应 */
export interface SearchArxivData {
  query: string;
  total: number;
  results: ArxivPaper[];
  fallback?: boolean;
  warning?: string;
}

/** 导入响应 */
export interface ImportArxivResult {
  total: number;
  imported: number;
  duplicates: number;
  failed: number;
  results: Array<{
    external_id: string;
    document_id: string | null;
    title: string;
    duplicate: boolean;
    error?: string;
  }>;
}

/** 项目文献列表 */
export interface ProjectLiteratureData {
  total: number;
  page: number;
  page_size: number;
  items: ImportedDocument[];
}

/** BibTeX 导入响应 */
export interface ImportBibtexResult {
  total: number;
  imported: number;
  duplicates: number;
  failed: number;
  results: Array<{
    cite_key: string;
    title: string;
    document_id: string | null;
    duplicate: boolean;
    error?: string;
  }>;
}

/** PDF 下载响应 */
export interface DownloadPdfResult {
  document_id: string;
  pdf_url: string;
  file_path: string;
  file_size: number;
  status: string;
}

/** PDF 解析 + 索引响应 */
export interface ParseIndexResult {
  document_id: string;
  title: string;
  chunk_count: number;
  status: string;
  index_added?: number;
}

/** 从研究问题推荐 arXiv 文献的响应 */
export interface ArxivRecommendData {
  query_mode: 'keyword' | 'raw_question';
  keywords: string[];
  original_question: string;
  search_query: string;
  total: number;
  results: ArxivPaper[];
  fallback?: boolean;
  warning?: string;
}

// ==================== Service ====================

export const literatureService = {
  /**
   * GET /api/v1/literature/sources
   */
  async getSources(): Promise<ApiResponse<{ sources: LiteratureSource[] }>> {
    const { data } = await api.get<ApiResponse<{ sources: LiteratureSource[] }>>('/literature/sources');
    return data;
  },

  /**
   * POST /api/v1/literature/search/arxiv
   */
  async searchArxiv(
    query: string,
    maxResults: number = 10,
    start: number = 0,
    sortBy: string = 'relevance',
  ): Promise<ApiResponse<SearchArxivData>> {
    const { data } = await api.post<ApiResponse<SearchArxivData>>('/literature/search/arxiv', {
      query,
      max_results: maxResults,
      start,
      sort_by: sortBy,
    });
    return data;
  },

  /**
   * POST /api/v1/literature/import/arxiv
   */
  async importArxiv(
    projectId: string,
    papers: ArxivPaper[],
    fallback: boolean = false,
  ): Promise<ApiResponse<ImportArxivResult>> {
    const { data } = await api.post<ApiResponse<ImportArxivResult>>('/literature/import/arxiv', {
      project_id: projectId,
      papers,
      fallback,
    });
    return data;
  },

  /**
   * POST /api/v1/literature/recommend/arxiv
   * 从研究问题自动提取关键词并搜索 arXiv
   */
  async recommendArxiv(
    projectId: string,
    researchQuestion: string,
    maxResults: number = 10,
  ): Promise<ApiResponse<ArxivRecommendData>> {
    const { data } = await api.post<ApiResponse<ArxivRecommendData>>('/literature/recommend/arxiv', {
      project_id: projectId,
      research_question: researchQuestion,
      max_results: maxResults,
    });
    return data;
  },

  /**
   * GET /api/v1/literature/project/{projectId}
   */
  async getProjectLiterature(
    projectId: string,
    sourceType?: string,
    page: number = 1,
    pageSize: number = 50,
  ): Promise<ApiResponse<ProjectLiteratureData>> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (sourceType) params.source_type = sourceType;

    const { data } = await api.get<ApiResponse<ProjectLiteratureData>>(
      `/literature/project/${projectId}`,
      { params },
    );
    return data;
  },

  /**
   * POST /api/v1/literature/import/bibtex
   */
  async importBibtex(
    projectId: string,
    bibtexText: string,
    sourceType: string = 'google_scholar_import',
  ): Promise<ApiResponse<ImportBibtexResult>> {
    const { data } = await api.post<ApiResponse<ImportBibtexResult>>('/literature/import/bibtex', {
      project_id: projectId,
      bibtex_text: bibtexText,
      source_type: sourceType,
    });
    return data;
  },

  /**
   * POST /api/v1/literature/download-pdf
   */
  async downloadPdf(projectId: string, documentId: string): Promise<ApiResponse<DownloadPdfResult>> {
    const { data } = await api.post<ApiResponse<DownloadPdfResult>>('/literature/download-pdf', {
      project_id: projectId,
      document_id: documentId,
    });
    return data;
  },

  /**
   * POST /api/v1/literature/parse-and-index
   */
  async parseAndIndex(
    projectId: string,
    documentId: string,
    autoIndex: boolean = true,
  ): Promise<ApiResponse<ParseIndexResult>> {
    const { data } = await api.post<ApiResponse<ParseIndexResult>>('/literature/parse-and-index', {
      project_id: projectId,
      document_id: documentId,
      auto_index: autoIndex,
    });
    return data;
  },

  /**
   * GET /api/v1/documents/{doc_id}/chunks
   */
  async getDocumentChunks(
    docId: string,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<ApiResponse<{ items: unknown[]; total: number; page: number; page_size: number }>> {
    const { data } = await api.get(`/documents/${docId}/chunks`, {
      params: { page, page_size: pageSize },
    });
    return data as ApiResponse<{ items: unknown[]; total: number; page: number; page_size: number }>;
  },
};