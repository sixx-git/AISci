import api from '@/lib/api';
import type { ApiResponse, ProjectOverview } from '@/types';

export const projectService = {
  /** GET /api/v1/projects */
  async getProjects(): Promise<ApiResponse<ProjectOverview[]>> {
    const { data } = await api.get<ApiResponse<ProjectOverview[]>>('/projects');
    return data;
  },

  /** GET /api/v1/projects/:id */
  async getProject(projectId: string): Promise<ApiResponse<ProjectOverview>> {
    const { data } = await api.get<ApiResponse<ProjectOverview>>(`/projects/${projectId}`);
    return data;
  },

  /** POST /api/v1/projects */
  async createProject(payload: Record<string, unknown>): Promise<ApiResponse<ProjectOverview>> {
    const { data } = await api.post<ApiResponse<ProjectOverview>>('/projects', payload);
    return data;
  },

  /** PATCH /api/v1/projects/:id */
  async updateProject(projectId: string, payload: Record<string, unknown>): Promise<ApiResponse<ProjectOverview>> {
    const { data } = await api.patch<ApiResponse<ProjectOverview>>(`/projects/${projectId}`, payload);
    return data;
  },

  /** DELETE /api/v1/projects/:id */
  async deleteProject(projectId: string): Promise<ApiResponse<boolean>> {
    const { data } = await api.delete<ApiResponse<boolean>>(`/projects/${projectId}`);
    return data;
  },
};