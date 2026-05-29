import api from '@/lib/api';
import type { ApiResponse, BackendDataset } from '@/types';

const datasetService = {
  async uploadDataset(projectId: string, file: File): Promise<ApiResponse<BackendDataset>> {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', file);
    const res = await api.post('/datasets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return res.data;
  },

  async getProjectDatasets(projectId: string): Promise<ApiResponse<BackendDataset[]>> {
    const res = await api.get('/datasets', { params: { project_id: projectId } });
    return res.data;
  },

  async getDataset(datasetId: string): Promise<ApiResponse<BackendDataset>> {
    const res = await api.get(`/datasets/${datasetId}`);
    return res.data;
  },

  async preprocessDataset(datasetId: string): Promise<ApiResponse<BackendDataset>> {
    const res = await api.post(`/datasets/${datasetId}/preprocess`);
    return res.data;
  },

  async toggleHypothesisUse(datasetId: string): Promise<ApiResponse<BackendDataset>> {
    const res = await api.put(`/datasets/${datasetId}/toggle-hypothesis`);
    return res.data;
  },

  async deleteDataset(datasetId: string): Promise<ApiResponse<unknown>> {
    const res = await api.delete(`/datasets/${datasetId}`);
    return res.data;
  },
};

export default datasetService;