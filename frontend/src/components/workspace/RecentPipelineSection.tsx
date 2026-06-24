import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Play, Loader2, ArrowRight } from 'lucide-react';
import { Card } from '@/components/Card';
import { pipelineService } from '@/services/pipelineService';
import { formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';
import type { PipelineRunSummary, ProjectOverview } from '@/types';

const RUN_STATUS_STYLE: Record<string, string> = {
  completed: 'text-bp-green bg-bp-green/10 border-bp-green/20',
  running: 'text-bp-cyan bg-bp-cyan-tint border-bp-cyan/20',
  failed: 'text-danger-400 bg-danger-500/10 border-danger-500/20',
  pending: 'text-bp-muted bg-bp-panel border-bp-border',
};

const RUN_STATUS_LABEL: Record<string, string> = {
  completed: '已完成',
  running: '运行中',
  failed: '失败',
  pending: '等待中',
};

export interface RecentPipelineRow {
  projectId: string;
  projectName: string;
  run: PipelineRunSummary;
}

interface RecentPipelineSectionProps {
  projects: ProjectOverview[];
}

const MAX_PROJECTS_SCAN = 12;
const MAX_ROWS = 6;

export function RecentPipelineSection({ projects }: RecentPipelineSectionProps) {
  const [rows, setRows] = useState<RecentPipelineRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projects.length === 0) {
      setRows([]);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const scan = projects.slice(0, MAX_PROJECTS_SCAN);
        const results = await Promise.allSettled(
          scan.map(async (p) => {
            const res = await pipelineService.getRuns(p.id);
            if (res.code !== 200 || !Array.isArray(res.data) || res.data.length === 0) {
              return [] as RecentPipelineRow[];
            }
            const latest = [...res.data].sort(
              (a, b) => new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime(),
            )[0];
            return [{ projectId: p.id, projectName: p.name, run: latest }];
          }),
        );

        const merged: RecentPipelineRow[] = [];
        results.forEach((r) => {
          if (r.status === 'fulfilled') merged.push(...r.value);
        });

        merged.sort(
          (a, b) => new Date(b.run.created_at || '').getTime() - new Date(a.run.created_at || '').getTime(),
        );

        if (!cancelled) setRows(merged.slice(0, MAX_ROWS));
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [projects]);

  if (!loading && rows.length === 0) return null;

  return (
    <Card
      className="mb-8"
      title="最近 Pipeline 运行"
      subtitle="跨项目最近一次 Pipeline 执行记录"
    >
      {loading ? (
        <div className="flex items-center justify-center py-8 text-bp-muted text-sm gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-bp-cyan" />
          加载最近运行…
        </div>
      ) : (
        <div className="overflow-x-auto rounded-bp border border-bp-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-bp-cyan-dim bg-bp-panel/50">
                <th className="py-2.5 px-4 text-xs text-bp-muted font-medium">项目</th>
                <th className="py-2.5 px-4 text-xs text-bp-muted font-medium">Run ID</th>
                <th className="py-2.5 px-4 text-xs text-bp-muted font-medium">状态</th>
                <th className="py-2.5 px-4 text-xs text-bp-muted font-medium">时间</th>
                <th className="py-2.5 px-4 text-xs text-bp-muted font-medium w-24">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ projectId, projectName, run }) => {
                const runId = run.run_id || run.id;
                const statusKey = run.status || 'pending';
                const statusCls = RUN_STATUS_STYLE[statusKey] ?? RUN_STATUS_STYLE.pending;
                return (
                  <tr
                    key={`${projectId}-${runId}`}
                    className="border-b border-bp-border/50 last:border-0 hover:bg-bp-cyan-tint/30 transition-colors"
                  >
                    <td className="py-3 px-4 text-bp-text font-medium truncate max-w-[200px]" title={projectName}>
                      {projectName}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-bp-cyan truncate max-w-[120px]" title={runId}>
                      {runId.slice(0, 8)}…
                    </td>
                    <td className="py-3 px-4">
                      <span className={cn('text-[11px] px-2 py-0.5 rounded-bp border', statusCls)}>
                        {RUN_STATUS_LABEL[statusKey] ?? statusKey}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-bp-muted whitespace-nowrap">
                      {formatDate(run.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <Link
                        to={`/projects/${projectId}?tab=workflow`}
                        className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-text transition-colors"
                      >
                        <Play className="w-3.5 h-3.5" />
                        工作流
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
