import api from '@/lib/api';
import env from '@/config/env';
import type { ApiResponse, Project, ProjectCreate } from '@/types';
import { MOCK_PROJECTS } from '@/data/mockData';

// 本地 Mock 数据转换
const mockProjectsList: Project[] = Object.values(MOCK_PROJECTS).map((p) => ({
  id: p.id,
  name: p.name,
  description: p.description,
  status: p.status,
  created_at: p.created_at,
  updated_at: p.updated_at,
}));

export const projectService = {
  /** GET /api/v1/projects */
  async getProjects(): Promise<ApiResponse<Project[]>> {
    if (env.USE_MOCK) {
      console.log('[Mock] projectService.getProjects');
      return {
        code: 200,
        message: '获取项目列表成功 (Mock)',
        data: mockProjectsList,
      };
    }

    const { data } = await api.get('/projects');
    if (data?.data?.list) {
      data.data = data.data.list;
    }
    return data;
  },

  /** GET /api/v1/projects/:id */
  async getProject(projectId: string): Promise<ApiResponse<Project>> {
    if (env.USE_MOCK) {
      console.log('[Mock] projectService.getProject', projectId);
      const project = mockProjectsList.find((p) => p.id === projectId) || mockProjectsList[0];
      return {
        code: 200,
        message: '获取项目详情成功 (Mock)',
        data: project,
      };
    }

    const { data } = await api.get(`/projects/${projectId}`);
    return data;
  },

  /** POST /api/v1/projects */
  async createProject(payload: ProjectCreate): Promise<ApiResponse<Project>> {
    if (env.USE_MOCK) {
      console.log('[Mock] projectService.createProject', payload);
      const newProject: Project = {
        id: Date.now().toString(),
        name: payload.name,
        description: payload.description,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        status: 'draft',
      };
      return {
        code: 200,
        message: '创建项目成功 (Mock)',
        data: newProject,
      };
    }

    const { data } = await api.post('/projects', payload);
    return data;
  },

  /** PUT /api/v1/projects/:id */
  async updateProject(projectId: string, payload: Partial<ProjectCreate>): Promise<ApiResponse<Project>> {
    if (env.USE_MOCK) {
      console.log('[Mock] projectService.updateProject', projectId, payload);
      const project = mockProjectsList.find((p) => p.id === projectId) || mockProjectsList[0];
      return {
        code: 200,
        message: '更新项目成功 (Mock)',
        data: { ...project, ...payload, updated_at: new Date().toISOString() },
      };
    }

    const { data } = await api.put(`/projects/${projectId}`, payload);
    return data;
  },

  /** DELETE /api/v1/projects/:id */
  async deleteProject(projectId: string): Promise<ApiResponse<boolean>> {
    if (env.USE_MOCK) {
      console.log('[Mock] projectService.deleteProject', projectId);
      return {
        code: 200,
        message: '删除项目成功 (Mock)',
        data: true,
      };
    }

    const { data } = await api.delete(`/projects/${projectId}`);
    return data;
  },
};