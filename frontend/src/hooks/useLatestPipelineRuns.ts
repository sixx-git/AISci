import { useEffect, useState, useMemo } from 'react';
import { pipelineService } from '@/services/pipelineService';
import type { ProjectOverview, PipelineRunSummary } from '@/types';
import type { StatusType } from '@/components/StatusBadge';
import { normalizeStatusKey, resolveProjectDisplayStatus } from '@/lib/projectStatus';

/** 拉取各项目最近一次 Pipeline，用于首页状态徽章与运行中轮询。 */
export function useLatestPipelineRuns(projects: ProjectOverview[]) {
  const [pipelineStatusByProjectId, setPipelineStatusByProjectId] = useState<
    Map<string, PipelineRunSummary>
  >(() => new Map());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projects.length === 0) {
      setPipelineStatusByProjectId(new Map());
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const results = await Promise.allSettled(
          projects.map(async (p) => {
            const res = await pipelineService.getRuns(p.id);
            if (res.code !== 200 || !Array.isArray(res.data) || res.data.length === 0) {
              return null;
            }
            const latest = [...res.data].sort(
              (a, b) => new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime(),
            )[0];
            return { projectId: p.id, run: latest };
          }),
        );

        const runMap = new Map<string, PipelineRunSummary>();
        results.forEach((r) => {
          if (r.status === 'fulfilled' && r.value) {
            runMap.set(r.value.projectId, r.value.run);
          }
        });

        if (!cancelled) {
          setPipelineStatusByProjectId(runMap);
        }
      } catch {
        if (!cancelled) {
          setPipelineStatusByProjectId(new Map());
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [projects]);

  const displayStatusByProjectId = useMemo(() => {
    const map = new Map<string, StatusType>();
    for (const project of projects) {
      const latest = pipelineStatusByProjectId.get(project.id);
      map.set(
        project.id,
        resolveProjectDisplayStatus(project.status, latest?.status),
      );
    }
    return map;
  }, [projects, pipelineStatusByProjectId]);

  const getDisplayStatus = (project: ProjectOverview): StatusType =>
    displayStatusByProjectId.get(project.id) ?? normalizeStatusKey(project.status);

  return {
    loading,
    pipelineStatusByProjectId,
    displayStatusByProjectId,
    getDisplayStatus,
  };
}
