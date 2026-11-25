import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface SixGTopic {
  id: string;
  label: string;
  domain: string;
  research_question: string;
  research_goal: string;
  research_background: string;
  constraints: string;
  expected_output: string;
  tool: string | null;
  verification_status: string;
  verification_note: string;
  coordinator_role: string;
}

export interface SixGParameter {
  name: string;
  value: string;
  unit: string;
  origin: string;
  confirmed: boolean;
  is_measured: boolean;
  note: string;
}

export interface SixGParse {
  domain: string;
  research_goal: string;
  task_summary: string;
  constraints_text: string;
  parameters: SixGParameter[];
  applicable_tools: string[];
  missing_information: string[];
  verification_status: string;
  verification_note: string;
}

export interface SixGProfile {
  topic: SixGTopic;
  execution_mode: 'quick' | 'full' | string;
  verification_status: string;
  verification_note: string;
  coordinator_role: string;
  custom_parse: SixGParse | null;
  emergency_tool_enabled: boolean;
  research_question?: string;
}

export const sixgService = {
  async topics(): Promise<ApiResponse<SixGTopic[]>> {
    const { data } = await api.get<ApiResponse<SixGTopic[]>>('/sixg/topics');
    return data;
  },

  async profile(projectId: string): Promise<ApiResponse<SixGProfile>> {
    const { data } = await api.get<ApiResponse<SixGProfile>>(`/projects/${projectId}/sixg`);
    return data;
  },

  async parse(projectId: string, text: string): Promise<ApiResponse<SixGProfile>> {
    const { data } = await api.post<ApiResponse<SixGProfile>>(`/projects/${projectId}/sixg/parse`, { text });
    return data;
  },

  async confirmParameters(
    projectId: string,
    parameters: Array<Pick<SixGParameter, 'name' | 'value' | 'unit' | 'confirmed'>>,
  ): Promise<ApiResponse<SixGProfile>> {
    const { data } = await api.put<ApiResponse<SixGProfile>>(
      `/projects/${projectId}/sixg/parameters`,
      { parameters },
    );
    return data;
  },

  async saveReport(projectId: string): Promise<ApiResponse<{ report_id: string; title: string }>> {
    const { data } = await api.post<ApiResponse<{ report_id: string; title: string }>>(
      `/projects/${projectId}/sixg/report`,
    );
    return data;
  },
};
