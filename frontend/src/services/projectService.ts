import api from '@/lib/api';
import type { ApiResponse, Project, ProjectCreate } from '@/types';

export const projectService = {
  /** GET /api/v1/projects */
  async getProjects(): Promise<ApiResponse<Project[]>> {
    const { data } = await api.get('/projects');
    // 后端可能返回 { list, pagination } 包装，提取纯数组
    if (data?.data?.list) {
      data.data = data.data.list;
    }
    return data;
  },

  /** GET /api/v1/projects/:id */
  async getProject(projectId: string): Promise<ApiResponse<Project>> {
    const { data } = await api.get(`/projects/${projectId}`);
    return data;
  },

  /** POST /api/v1/projects */
  async createProject(payload: ProjectCreate): Promise<ApiResponse<Project>> {
    const { data } = await api.post('/projects', payload);
    return data;
  },

  /** PUT /api/v1/projects/:id */
  async updateProject(projectId: string, payload: Partial<ProjectCreate>): Promise<ApiResponse<Project>> {
    const { data } = await api.put(`/projects/${projectId}`, payload);
    return data;
  },

  /** DELETE /api/v1/projects/:id */
  async deleteProject(projectId: string): Promise<ApiResponse<boolean>> {
    const { data } = await api.delete(`/projects/${projectId}`);
    return data;
  },
};