import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface PromptInfo {
  project_id: string;
  stage: string;
  template_name: string;
  default_template: string;
  override_template?: string | null;
  effective_template: string;
  has_override: boolean;
  updated_at?: string | null;
}

export const promptService = {
  async getPrompt(projectId: string, stage: string): Promise<ApiResponse<PromptInfo>> {
    const { data } = await api.get<ApiResponse<PromptInfo>>(`/prompts/${stage}`, {
      params: { project_id: projectId },
    });
    return data;
  },

  async saveOverride(projectId: string, stage: string, promptTemplate: string): Promise<ApiResponse<PromptInfo>> {
    const { data } = await api.post<ApiResponse<PromptInfo>>(`/prompts/${stage}/override`, {
      project_id: projectId,
      prompt_template: promptTemplate,
    });
    return data;
  },

  async deleteOverride(projectId: string, stage: string): Promise<ApiResponse<PromptInfo>> {
    const { data } = await api.delete<ApiResponse<PromptInfo>>(`/prompts/${stage}/override`, {
      params: { project_id: projectId },
    });
    return data;
  },
};

export default promptService;
