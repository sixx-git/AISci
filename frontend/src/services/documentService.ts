import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse } from '@/types';

/** 后端返回的文档信息 */
export interface DocumentInfo {
  id: string;
  project_id?: string;
  filename: string;
  file_type: string;
  file_size: number;
  title?: string;
  authors?: string;
  abstract?: string;
  summary?: string;
  status: 'uploaded' | 'processing' | 'processed' | 'failed';
  error_message?: string;
  chunk_count?: number;
  created_at: string;
  updated_at?: string;
}

/** upload 接口返回的 data 结构 */
export interface UploadResult {
  document: DocumentInfo;
  chunks_count?: number;
}

/** list 接口返回的 data 结构 */
export interface DocumentListResult {
  items: DocumentInfo[];
  total: number;
  page: number;
  page_size: number;
}

export const documentService = {
  /**
   * POST /api/v1/documents/upload
   * 上传 PDF 并自动解析
   */
  async uploadDocument(
    projectId: string,
    file: File,
  ): Promise<ApiResponse<UploadResult>> {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await api.post<ApiResponse<UploadResult>>(
      `/documents/upload?project_id=${projectId}&auto_parse=true`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return data;
  },

  /**
   * GET /api/v1/documents?project_id=xxx
   * 获取某项目的文档列表
   */
  async getDocuments(
    projectId: string,
    page = 1,
    pageSize = 100,
  ): Promise<ApiResponse<DocumentListResult>> {
    if (env.USE_MOCK) {
      console.log('[Mock] documentService.getDocuments', projectId);
      return {
        code: 200,
        message: 'Mock data',
        data: { items: [], total: 0, page: 1, page_size: 20 },
      };
    }

    const { data } = await api.get<ApiResponse<DocumentListResult>>(
      '/documents',
      { params: { project_id: projectId, page, page_size: pageSize } },
    );
    return data;
  },

  /**
   * DELETE /api/v1/documents/:docId
   */
  async deleteDocument(docId: string): Promise<ApiResponse<null>> {
    const { data } = await api.delete<ApiResponse<null>>(`/documents/${docId}`);
    return data;
  },
};