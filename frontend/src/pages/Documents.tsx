import { useState, useEffect } from 'react';
import { LiteratureLibrary } from '@/components/LiteratureLibrary';
import { CrossProjectLiteratureSummary } from '@/components/CrossProjectLiteratureSummary';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { projectService } from '@/services';
import type { ProjectOverview } from '@/types';

export function Documents() {
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingProjects(true);
      try {
        const res = await projectService.getProjects();
        if (cancelled) return;
        const list = (res.data as { list?: ProjectOverview[] })?.list ?? res.data ?? [];
        setProjects(Array.isArray(list) ? list : []);
      } catch {
        if (!cancelled) setProjects([]);
      } finally {
        if (!cancelled) setLoadingProjects(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="文献中心"
        subtitle="跨项目文献检索与汇总；选择具体项目后可上传、arXiv 导入与解析"
      />

      <Card className="mb-6 p-4">
        <label htmlFor="literature-project-scope" className="text-xs text-bp-muted block mb-1.5">
          项目范围
        </label>
        {loadingProjects ? (
          <LoadingState message="加载项目列表..." compact />
        ) : (
          <select
            id="literature-project-scope"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="input-field py-2 text-sm max-w-md"
          >
            <option value="all">全部项目（跨项目汇总）</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </Card>

      {selectedProjectId === 'all' ? (
        <CrossProjectLiteratureSummary projects={projects} />
      ) : (
        <LiteratureLibrary projectId={selectedProjectId} showHeader={false} />
      )}
    </div>
  );
}
