import type { NavigateFunction } from 'react-router-dom';

export type ProjectTabParams = Record<string, string | undefined>;

/** 构建项目工作台 Tab URL（不改变现有 query 约定） */
export function buildProjectTabUrl(
  projectId: string,
  tab: string,
  params?: ProjectTabParams,
): string {
  const search = new URLSearchParams({ tab });
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value != null && value !== '') {
        search.set(key, value);
      }
    });
  }
  return `/projects/${projectId}?${search.toString()}`;
}

export function navigateToProjectTab(
  navigate: NavigateFunction,
  projectId: string | undefined,
  tab: string,
  params?: ProjectTabParams,
): void {
  if (!projectId) return;
  navigate(buildProjectTabUrl(projectId, tab, params));
}
