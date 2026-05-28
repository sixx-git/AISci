import api from '@/lib/api';
import env from '@/config/env';
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

// ==================== Mock 数据 ====================

const MOCK_ARXIV_RESULTS: ArxivPaper[] = [
  {
    title: 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models',
    authors: 'Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou',
    abstract: 'We explore how generating a chain of thought—a series of intermediate reasoning steps—significantly improves the ability of large language models to perform complex reasoning. We demonstrate that chain-of-thought reasoning can be elicited in sufficiently large language models via prompting, and that it improves performance on arithmetic, commonsense, and symbolic reasoning tasks.',
    published_at: '2023-01-10T00:00:00+00:00',
    categories: 'cs.CL, cs.AI',
    external_id: '2201.11903',
    source_url: 'https://arxiv.org/abs/2201.11903',
    pdf_url: 'https://arxiv.org/pdf/2201.11903',
    source_type: 'arxiv',
    doi: null,
    journal_ref: 'NeurIPS 2022',
  },
  {
    title: 'Tree of Thoughts: Deliberate Problem Solving with Large Language Models',
    authors: 'Shunyu Yao, Dian Yu, Jeffrey Zhao, Izhak Shafran, Thomas L. Griffiths, Yuan Cao, Karthik Narasimhan',
    abstract: 'We introduce a framework for deliberate problem solving with large language models called Tree of Thoughts (ToT). ToT generalizes chain-of-thought prompting by allowing LLMs to explore multiple reasoning paths and self-evaluate choices.',
    published_at: '2023-12-03T00:00:00+00:00',
    categories: 'cs.CL, cs.AI',
    external_id: '2305.10601',
    source_url: 'https://arxiv.org/abs/2305.10601',
    pdf_url: 'https://arxiv.org/pdf/2305.10601',
    source_type: 'arxiv',
    doi: null,
    journal_ref: 'NeurIPS 2023',
  },
  {
    title: 'Large Language Models as Optimizers',
    authors: 'Chengrun Yang, Xuezhi Wang, Yifeng Lu, Hanxiao Liu, Quoc V. Le, Denny Zhou, Xinyun Chen',
    abstract: 'We propose Optimization by PROmpting (OPRO), a simple and effective approach to leverage large language models as optimizers. Instead of formally defining the optimization problem and deriving the update step with a programmed solver, we describe the optimization problem in natural language and instruct the LLM to iteratively generate new solutions.',
    published_at: '2024-09-07T00:00:00+00:00',
    categories: 'cs.LG, cs.AI, cs.CL',
    external_id: '2309.03409',
    source_url: 'https://arxiv.org/abs/2309.03409',
    pdf_url: 'https://arxiv.org/pdf/2309.03409',
    source_type: 'arxiv',
    doi: null,
    journal_ref: null,
  },
];

const MOCK_IMPORTED_DOCS: ImportedDocument[] = [
  {
    id: 'mock-imported-1',
    title: 'Attention Is All You Need',
    authors: 'Ashish Vaswani, Noam Shazeer, Niki Parmar, et al.',
    abstract: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...',
    doi: '10.48550/arXiv.1706.03762',
    external_id: '1706.03762',
    source_type: 'arxiv',
    source_url: 'https://arxiv.org/abs/1706.03762',
    pdf_url: 'https://arxiv.org/pdf/1706.03762',
    library_scope: 'base',
    import_status: 'imported',
    is_personal: false,
    created_at: '2025-01-15T10:00:00',
  },
];

// ==================== Service ====================

export const literatureService = {
  /**
   * GET /api/v1/literature/sources
   */
  async getSources(): Promise<ApiResponse<{ sources: LiteratureSource[] }>> {
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.getSources');
      return {
        code: 200,
        message: 'Mock data',
        data: {
          sources: [
            { id: 'arxiv', name: 'arXiv', description: 'arXiv 预印本论文库', features: ['search', 'import_metadata'], supports_pdf: false },
            { id: 'bibtex', name: 'BibTeX', description: 'BibTeX 文献导入', features: ['import_metadata'], supports_pdf: false },
            { id: 'google_scholar_import', name: 'Google Scholar', description: 'Google Scholar BibTeX 导入（手动粘贴）', features: ['import_metadata'], supports_pdf: false },
            { id: 'upload', name: '本地上传', description: '用户手动上传 PDF 文献', features: ['upload', 'parse_pdf'], supports_pdf: true },
          ],
        },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.searchArxiv', { query, maxResults });
      // 模拟延迟
      await new Promise((r) => setTimeout(r, 600));
      return {
        code: 200,
        message: 'Mock data',
        data: {
          query,
          total: MOCK_ARXIV_RESULTS.length,
          results: MOCK_ARXIV_RESULTS,
          fallback: false,
          warning: '',
        },
      };
    }

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
  ): Promise<ApiResponse<ImportArxivResult>> {
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.importArxiv', { projectId, count: papers.length });
      await new Promise((r) => setTimeout(r, 400));
      return {
        code: 200,
        message: 'Mock import success',
        data: {
          total: papers.length,
          imported: papers.length,
          duplicates: 0,
          failed: 0,
          results: papers.map((p) => ({
            external_id: p.external_id,
            document_id: `mock-doc-${p.external_id}`,
            title: p.title,
            duplicate: false,
          })),
        },
      };
    }

    const { data } = await api.post<ApiResponse<ImportArxivResult>>('/literature/import/arxiv', {
      project_id: projectId,
      papers,
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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.recommendArxiv', { projectId, researchQuestion, maxResults });
      await new Promise((r) => setTimeout(r, 800));
      return {
        code: 200,
        message: 'Mock data',
        data: {
          query_mode: 'keyword',
          keywords: ['chain-of-thought', 'reasoning', 'large language models'],
          original_question: researchQuestion,
          search_query: 'all:chain-of-thought AND all:reasoning AND all:large language models',
          total: MOCK_ARXIV_RESULTS.length,
          results: MOCK_ARXIV_RESULTS,
          fallback: false,
          warning: '',
        },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.getProjectLiterature', projectId);
      return {
        code: 200,
        message: 'Mock data',
        data: {
          total: MOCK_IMPORTED_DOCS.length,
          page: 1,
          page_size: 50,
          items: MOCK_IMPORTED_DOCS,
        },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.importBibtex', { projectId, textLen: bibtexText.length });
      await new Promise((r) => setTimeout(r, 500));

      // 模拟解析：统计 @ 符号数量
      const entryCount = (bibtexText.match(/@\w+\{/g) || []).length || 1;
      const titles = bibtexText.match(/title\s*=\s*[{""](.+?)[}""]/gi) || [];
      const results = titles.map((t, i) => ({
        cite_key: `mock-key-${i}`,
        title: t.replace(/title\s*=\s*[{""]/gi, '').replace(/[}""]$/g, '').trim().slice(0, 80),
        document_id: `mock-bib-doc-${i}`,
        duplicate: false,
      }));

      return {
        code: 200,
        message: `Mock: 导入完成`,
        data: {
          total: entryCount,
          imported: entryCount,
          duplicates: 0,
          failed: 0,
          results: results.length > 0 ? results : [{
            cite_key: 'mock-key',
            title: 'Mock BibTeX Entry',
            document_id: 'mock-bib-doc',
            duplicate: false,
          }],
        },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.downloadPdf', { projectId, documentId });
      await new Promise((r) => setTimeout(r, 800));
      return {
        code: 200,
        message: 'Mock: PDF 下载完成',
        data: {
          document_id: documentId,
          pdf_url: 'https://arxiv.org/pdf/mock.pdf',
          file_path: `storage/uploads/${projectId}/external/arxiv/${documentId}.pdf`,
          file_size: 2048000,
          status: 'pdf_downloaded',
        },
      };
    }

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
    if (env.USE_MOCK) {
      console.log('[Mock] literatureService.parseAndIndex', { projectId, documentId, autoIndex });
      await new Promise((r) => setTimeout(r, 1500));
      return {
        code: 200,
        message: 'Mock: 解析完成',
        data: {
          document_id: documentId,
          title: 'Mock Paper Title',
          chunk_count: 12,
          status: autoIndex ? 'indexed' : 'parsed',
          index_added: autoIndex ? 12 : undefined,
        },
      };
    }

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
  ): Promise<ApiResponse<{ items: any[]; total: number; page: number; page_size: number }>> {
    if (env.USE_MOCK) {
      await new Promise((r) => setTimeout(r, 200));
      return {
        code: 200,
        message: 'Mock chunks',
        data: {
          items: Array.from({ length: 3 }, (_, i) => ({
            id: `chunk-${i}`,
            chunk_index: i,
            content: `[Mock chunk ${i}] Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.`,
            content_preview: `[Mock chunk ${i}] Lorem ipsum dolor sit amet...`,
            page_number: i + 1,
            status: 'ready',
          })),
          total: 3,
          page,
          page_size: pageSize,
        },
      };
    }

    const { data } = await api.get(`/documents/${docId}/chunks`, {
      params: { page, page_size: pageSize },
    });
    return data as any;
  },
};