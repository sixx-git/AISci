import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse, Document } from '@/types';
import { MOCK_LITERATURE } from '@/data/mockData';

// Mock 数据转换
const mockDocumentsList: Document[] = MOCK_LITERATURE.map((l) => ({
  id: l.id,
  filename: l.title,
  file_path: `/storage/documents/${l.id}.pdf`,
  file_type: l.type,
  status: l.parseStatus,
  created_at: l.uploadDate,
}));

export const documentService = {
  /** POST /api/v1/documents/upload */
  async uploadDocument(projectId: string, file: File): Promise<ApiResponse<Document>> {
    if (env.USE_MOCK) {
      console.log('[Mock] documentService.uploadDocument', projectId, file.name);
      const newDoc: Document = {
        id: Date.now().toString(),
        filename: file.name,
        file_path: `/storage/documents/${Date.now()}.pdf`,
        file_type: file.type,
        status: 'processed',
        created_at: new Date().toISOString(),
      };
      return {
        code: 200,
        message: '文档上传成功 (Mock)',
        data: newDoc,
      };
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    const { data } = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  /** GET /api/v1/documents?project_id=xxx */
  async getDocuments(projectId: string): Promise<ApiResponse<Document[]>> {
    if (env.USE_MOCK) {
      console.log('[Mock] documentService.getDocuments', projectId);
      return {
        code: 200,
        message: '获取文档列表成功 (Mock)',
        data: mockDocumentsList,
      };
    }

    const { data } = await api.get('/documents', { params: { project_id: projectId } });
    return data;
  },

  /** GET /api/v1/documents/:docId */
  async getDocument(docId: string): Promise<ApiResponse<Document>> {
    if (env.USE_MOCK) {
      console.log('[Mock] documentService.getDocument', docId);
      const doc = mockDocumentsList.find((d) => d.id === docId) || mockDocumentsList[0];
      return {
        code: 200,
        message: '获取文档详情成功 (Mock)',
        data: doc,
      };
    }

    const { data } = await api.get(`/documents/${docId}`);
    return data;
  },

  /** DELETE /api/v1/documents/:docId */
  async deleteDocument(docId: string): Promise<ApiResponse<boolean>> {
    if (env.USE_MOCK) {
      console.log('[Mock] documentService.deleteDocument', docId);
      return {
        code: 200,
        message: '删除文档成功 (Mock)',
        data: true,
      };
    }

    const { data } = await api.delete(`/documents/${docId}`);
    return data;
  },
};