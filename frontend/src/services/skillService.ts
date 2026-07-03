import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface SkillRecord {
  id: string;
  name: string;
  description: string;
  category: string;
  category_label: string;
  module_path: string;
  agents: string[];
  enabled: boolean;
  locked?: boolean;
  source_reference?: string | null;
}

export interface SkillSummary {
  total: number;
  enabled: number;
  disabled: number;
  locked?: number;
  categories: { id: string; label: string; count: number }[];
  agents: string[];
}

export interface AgentSkillBinding {
  agent: string;
  skill_count: number;
  skills: string[];
}

const skillService = {
  async list(params?: {
    category?: string;
    agent?: string;
    keyword?: string;
    refresh?: boolean;
  }): Promise<ApiResponse<SkillRecord[]>> {
    const res = await api.get<ApiResponse<SkillRecord[]>>('/skills', { params });
    return res.data;
  },

  async getSummary(refresh = false): Promise<ApiResponse<SkillSummary>> {
    const res = await api.get<ApiResponse<SkillSummary>>('/skills/summary', {
      params: refresh ? { refresh: true } : undefined,
    });
    return res.data;
  },

  async listAgents(): Promise<ApiResponse<AgentSkillBinding[]>> {
    const res = await api.get<ApiResponse<AgentSkillBinding[]>>('/skills/agents');
    return res.data;
  },

  async setEnabled(skillId: string, enabled: boolean): Promise<ApiResponse<SkillRecord>> {
    const res = await api.patch<ApiResponse<SkillRecord>>(`/skills/${encodeURIComponent(skillId)}`, {
      enabled,
    });
    return res.data;
  },
};

export default skillService;
