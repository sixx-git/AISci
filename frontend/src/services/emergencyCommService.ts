import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface EmergencyCheckItem {
  id: string;
  title: string;
  passed: boolean;
  detail: string;
  demand_mbps?: number;
  available_mbps?: number;
  required_min?: number;
  available_min?: number;
}

export interface EmergencyPlan {
  coverage: string;
  serve_terminal_count: number;
  mbps_per_terminal: number;
  uses_uav_relay: boolean;
  uav_used: number;
  uav_continuous_min: number;
  service_requirement_changed?: boolean;
  change_note?: string;
  source?: string;
  source_note?: string;
}

export interface EmergencyScenario {
  location: string;
  disaster: string;
  networks?: string[];
  terminals: number;
  priority_terminals: number;
  demand_mbps_per_terminal: number;
  satellite_backhaul_mbps: number;
  ground_backhaul_mbps: number;
  uav_count: number;
  uav_endurance_min: number;
  mission_duration_min: number;
  parameter_origin?: string;
}

export interface EmergencyVersion {
  version: number;
  created_at: string;
  origin: string;
  status: 'pass' | 'fail' | 'partial';
  summary: string;
  plan: EmergencyPlan;
  check: {
    engine: string;
    items: EmergencyCheckItem[];
    failed_ids: string[];
    all_passed: boolean;
    demand_mbps: number;
    backhaul_mbps: number;
    disclaimer: string;
    not_verified?: string[];
  };
  coordinator: {
    agent: string;
    suggestion: string;
    message: string;
    status: string;
  };
  comparison?: {
    from_version: number;
    to_version: number;
    demand_mbps: { before: number; after: number };
    serve_terminal_count: { before: number; after: number };
    uav_continuous_min: { before: number; after: number };
    newly_passed: string[];
    still_failing: string[];
  };
}

export interface EmergencySuggestion {
  id: string;
  applicable: boolean;
  requires_user_confirmation: boolean;
  changes_service_requirement: boolean;
  title: string;
  detail: string;
}

export interface EmergencyCommState {
  app: string;
  disclaimer: string;
  scenario: EmergencyScenario;
  versions: EmergencyVersion[];
  active_version: number;
  pending_suggestions: EmergencySuggestion[];
  integration: Record<string, string>;
}

export const emergencyCommService = {
  async get(projectId: string): Promise<ApiResponse<EmergencyCommState>> {
    const { data } = await api.get<ApiResponse<EmergencyCommState>>(
      `/projects/${projectId}/emergency-comm`,
    );
    return data;
  },

  async updateScenario(
    projectId: string,
    patch: Partial<EmergencyScenario>,
  ): Promise<ApiResponse<EmergencyCommState>> {
    const { data } = await api.put<ApiResponse<EmergencyCommState>>(
      `/projects/${projectId}/emergency-comm/scenario`,
      patch,
    );
    return data;
  },

  async confirm(
    projectId: string,
    suggestionId: string,
  ): Promise<ApiResponse<EmergencyCommState>> {
    const { data } = await api.post<ApiResponse<EmergencyCommState>>(
      `/projects/${projectId}/emergency-comm/suggestions/${suggestionId}/confirm`,
    );
    return data;
  },
};
