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

export interface PromptPresetVariant {
  id: string;
  label: string;
  file: string;
  description?: string;
}

export interface PromptPresetPack {
  id: string;
  label: string;
  description: string;
  reference?: string | null;
  recommended_pipeline_mode?: string | null;
  requires_federated: boolean;
  stages: Record<string, PromptPresetVariant[]>;
}

export interface PromptPresetCatalog {
  version: number;
  excluded_stages: string[];
  excluded_reason: string;
  packs: PromptPresetPack[];
  default_pack_id: string;
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

  async getPresetCatalog(projectId: string): Promise<ApiResponse<PromptPresetCatalog>> {
    const { data } = await api.get<ApiResponse<PromptPresetCatalog>>('/prompts/presets/catalog', {
      params: { project_id: projectId },
    });
    return data;
  },

  async getPresetContent(
    packId: string,
    stage: string,
    variantId: string,
  ): Promise<ApiResponse<{ content: string; description?: string; variant_label?: string }>> {
    const { data } = await api.get<ApiResponse<{ content: string; description?: string; variant_label?: string }>>(
      `/prompts/presets/${packId}/${stage}/${variantId}`,
    );
    return data;
  },

  async applyPreset(
    projectId: string,
    packId: string,
    options: { stage?: string; variantId?: string; applyAllStages?: boolean },
  ): Promise<ApiResponse<{ count: number; applied: Array<{ stage: string; variant_id: string }> }>> {
    const { data } = await api.post<ApiResponse<{ count: number; applied: Array<{ stage: string; variant_id: string }> }>>(
      '/prompts/presets/apply',
      {
        project_id: projectId,
        pack_id: packId,
        stage: options.stage,
        variant_id: options.variantId,
        apply_all_stages: options.applyAllStages ?? false,
      },
    );
    return data;
  },
};

export default promptService;
