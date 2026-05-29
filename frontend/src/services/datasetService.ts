import api from '@/lib/api';
import type { ApiResponse, BackendDataset } from '@/types';

export interface DataContext {
  dataset_count: number;
  available_modalities: string[];
  datasets: DataContextEntry[];
  field_candidates: string[];
  target_candidates: string[];
  quality_summary: Record<string, unknown>;
  warnings: string[];
}

interface DataContextEntry {
  dataset_id: string;
  filename: string;
  data_type: string;
  source_type: string;
  n_rows: number;
  n_columns: number;
  columns: string[];
  dtypes: Record<string, string>;
  missing_count: number;
  missing_rate: number;
  statistics: Record<string, unknown>;
  preview: unknown[];
  use_for_hypothesis: boolean;
  preprocessing_status: string;
  quality_score?: number;
  quality_recommendations?: string[];
  target_candidates?: Record<string, string[]>;
}

export interface QualityResult {
  success: boolean;
  error?: string;
  data?: {
    quality_report: Record<string, unknown>;
    overall_score: number;
    file_reports: unknown[];
    recommendations: string[];
  };
  warnings?: string[];
}

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

  async getDataContext(projectId: string): Promise<ApiResponse<DataContext>> {
    const res = await api.get('/datasets/context', { params: { project_id: projectId } });
    return res.data;
  },

  async runQualityAnalysis(datasetId: string): Promise<ApiResponse<QualityResult>> {
    const res = await api.post(`/datasets/${datasetId}/quality`);
    return res.data;
  },
};

export default datasetService;