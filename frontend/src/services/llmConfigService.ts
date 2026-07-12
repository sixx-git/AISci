import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface LlmConfig {
  use_env_api_key: boolean;
  api_key_source: 'env' | 'custom';
  env_api_key_configured: boolean;
  custom_api_key_configured: boolean;
  api_key_configured: boolean;
  api_key_masked: string;
  model: string;
  base_url: string;
  use_mock_llm: boolean;
  env_model: string;
  env_base_url: string;
  available_models: string[];
  model_override?: string | null;
}

export interface LlmConfigUpdate {
  use_env_api_key?: boolean;
  api_key?: string;
  clear_custom_api_key?: boolean;
  model?: string;
  base_url?: string;
  use_mock_llm?: boolean;
}

export const llmConfigService = {
  async getConfig(): Promise<ApiResponse<LlmConfig>> {
    const { data } = await api.get<ApiResponse<LlmConfig>>('/llm/config');
    return data;
  },

  async updateConfig(payload: LlmConfigUpdate): Promise<ApiResponse<LlmConfig>> {
    const { data } = await api.put<ApiResponse<LlmConfig>>('/llm/config', payload);
    return data;
  },

  async testConnection(): Promise<ApiResponse<{ ok: boolean; model: string; message: string; latency_ms?: number }>> {
    const { data } = await api.post<ApiResponse<{ ok: boolean; model: string; message: string; latency_ms?: number }>>('/llm/test');
    return data;
  },
};
