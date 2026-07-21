import api from '@/lib/api';
import type { ApiResponse, ProjectOverview } from '@/types';

export interface ProjectListParams {
  page?: number;
  page_size?: number;
  status?: string;
  keyword?: string;
}

export interface ProjectListPagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ProjectListPage {
  list: ProjectOverview[];
  pagination: ProjectListPagination;
}

function parseProjectListResponse(data: unknown): ProjectListPage {
  const payload = data as {
    list?: ProjectOverview[];
    pagination?: Partial<ProjectListPagination>;
  } | ProjectOverview[] | null | undefined;

  if (Array.isArray(payload)) {
    return {
      list: payload,
      pagination: {
        page: 1,
        page_size: payload.length,
        total: payload.length,
        total_pages: 1,
      },
    };
  }

  const list = Array.isArray(payload?.list) ? payload.list : [];
  const pagination = payload?.pagination ?? {};
  const total = Number(pagination.total ?? list.length) || 0;
  const pageSize = Number(pagination.page_size ?? list.length) || 20;
  const page = Number(pagination.page ?? 1) || 1;
  const totalPages =
    Number(pagination.total_pages) ||
    Math.max(1, Math.ceil(total / Math.max(pageSize, 1)));

  return {
    list,
    pagination: {
      page,
      page_size: pageSize,
      total,
      total_pages: totalPages,
    },
  };
}

export const projectService = {
  /** GET /api/v1/projects — 服务端分页；默认 page_size=20 */
  async getProjects(
    params?: ProjectListParams,
  ): Promise<ApiResponse<ProjectListPage>> {
    const { data } = await api.get<ApiResponse<unknown>>('/projects', {
      params: {
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
        ...(params?.status ? { status: params.status } : {}),
        ...(params?.keyword ? { keyword: params.keyword } : {}),
      },
    });
    return {
      ...data,
      data: parseProjectListResponse(data?.data),
    };
  },

  /** GET /api/v1/projects/:id */
  async getProject(
    projectId: string,
    options?: { timeout?: number },
  ): Promise<ApiResponse<ProjectOverview>> {
    const { data } = await api.get<ApiResponse<ProjectOverview>>(`/projects/${projectId}`, {
      timeout: options?.timeout,
    });
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
