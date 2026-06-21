import api from '@/lib/api';

export interface MultimodalEvidenceFact {
  fact_id: string;
  modality: string;
  fact_text: string;
  source_file?: string;
  confidence?: number;
  relevance_to_question?: string;
}

export interface MultimodalAsset {
  id: string;
  project_id: string;
  dataset_id?: string;
  file_name: string;
  file_path: string;
  modality: string;
  mime_type?: string;
  extracted_text?: string;
  extracted_summary?: string;
  evidence_facts?: MultimodalEvidenceFact[];
  metadata?: Record<string, unknown>;
  parse_status: string;
  use_for_hypothesis: boolean;
  created_at: string;
}

export const multimodalService = {
  async list(projectId: string) {
    const { data } = await api.get(`/multimodal?project_id=${encodeURIComponent(projectId)}`);
    return data;
  },

  async getContext(projectId: string) {
    const { data } = await api.get(`/multimodal/context?project_id=${encodeURIComponent(projectId)}`);
    return data;
  },

  async upload(projectId: string, file: File, researchQuestion = '') {
    const form = new FormData();
    form.append('project_id', projectId);
    form.append('research_question', researchQuestion);
    form.append('file', file);
    const { data } = await api.post('/multimodal/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async toggleHypothesis(assetId: string) {
    const { data } = await api.put(`/multimodal/${assetId}/toggle-hypothesis`);
    return data;
  },

  async reparse(assetId: string, researchQuestion = '') {
    const form = new FormData();
    form.append('research_question', researchQuestion);
    const { data } = await api.post(`/multimodal/${assetId}/reparse`, form);
    return data;
  },
};

export default multimodalService;
