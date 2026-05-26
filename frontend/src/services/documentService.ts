import api from '@/lib/api';
import type { ApiResponse, Document } from '@/types';

export const documentService = {
  /** POST /api/v1/documents/upload */
  async uploadDocument(projectId: string, file: File): Promise<ApiResponse<Document>> {
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
    const { data } = await api.get('/documents', { params: { project_id: projectId } });
    return data;
  },

  /** GET /api/v1/documents/:docId */
  async getDocument(docId: string): Promise<ApiResponse<Document>> {
    const { data } = await api.get(`/documents/${docId}`);
    return data;
  },

  /** DELETE /api/v1/documents/:docId */
  async deleteDocument(docId: string): Promise<ApiResponse<boolean>> {
    const { data } = await api.delete(`/documents/${docId}`);
    return data;
  },
};