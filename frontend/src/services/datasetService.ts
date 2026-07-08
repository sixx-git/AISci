import api from '@/lib/api';
import type { ApiResponse, BackendDataset } from '@/types';

export interface ModelingMetric {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  roc_auc?: number | null;
  rmse?: number;
  mae?: number;
  r2?: number;
  confusion_matrix?: number[][];
}

export interface ModelingModelResult {
  model_name: string;
  metrics: ModelingMetric;
  feature_importance?: { feature: string; importance: number }[];
}

export interface SelfCorrectionSuggestion {
  reason: string;
  suggestion: string;
  next_action: string;
}

export interface ModelingChart {
  plot_id: string;
  title: string;
  type: string;
  base64?: string;
  description?: string;
}

export interface ModelingResult {
  success: boolean;
  dataset_id: string;
  project_id: string;
  research_task?: string;
  task_type: string;
  target_column: string;
  profile: Record<string, unknown>;
  models: ModelingModelResult[];
  best_model: string;
  charts: ModelingChart[];
  self_correction_suggestions: SelfCorrectionSuggestion[];
  is_pilot_validation?: boolean;
  warnings?: string[];
  created_at?: string;
  error?: string;
}

export interface ModelingRunPayload {
  target_column?: string;
  task_type?: string;
  research_task?: string;
}

export interface DatasetAssistantChatPayload {
  message: string;
  history?: { role: string; content: string }[];
}

export interface DatasetAssistantChatResult {
  reply: string;
  action: string;
  action_success: boolean;
  action_result?: Record<string, unknown>;
  modeling_result?: ModelingResult;
}

export interface DataContext {
  dataset_count: number;
  available_modalities: string[];
  datasets: DataContextEntry[];
  field_candidates: string[];
  target_candidates: string[];
  quality_summary: Record<string, unknown>;
  warnings: string[];
  project_mode?: string;
  fl_context?: FlDataContext;
}

export interface FlDataContext {
  project_mode?: string;
  fl_setting?: string;
  federated_setting?: string;
  vfl_detected?: boolean;
  detected_fields?: string[];
  client_fields?: string[];
  party_fields?: string[];
  metrics_fields?: string[];
  metrics_candidates?: string[];
  target_candidates?: string[];
  parties?: string[];
  feature_parties?: string[];
  label_party?: string;
  alignment_keys?: string[];
  privacy_fields?: string[];
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
      timeout: 3600000,
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

  async runModeling(datasetId: string, payload: ModelingRunPayload = {}): Promise<ApiResponse<ModelingResult>> {
    const res = await api.post<ApiResponse<ModelingResult>>(`/datasets/${datasetId}/modeling/run`, payload, {
      timeout: 3600000,
    });
    return res.data;
  },

  async getModelingResult(datasetId: string): Promise<ApiResponse<ModelingResult>> {
    const res = await api.get<ApiResponse<ModelingResult>>(`/datasets/${datasetId}/modeling/result`);
    return res.data;
  },

  async assistantChat(
    datasetId: string,
    payload: DatasetAssistantChatPayload,
  ): Promise<ApiResponse<DatasetAssistantChatResult>> {
    const res = await api.post<ApiResponse<DatasetAssistantChatResult>>(
      `/datasets/${datasetId}/assistant/chat`,
      payload,
      { timeout: 3600000 },
    );
    return res.data;
  },

  async getDataCatalog(projectId: string, refresh = false): Promise<ApiResponse<Record<string, unknown>>> {
    const res = await api.get('/datasets/catalog', {
      params: { project_id: projectId, refresh },
    });
    return res.data;
  },
};

export default datasetService;