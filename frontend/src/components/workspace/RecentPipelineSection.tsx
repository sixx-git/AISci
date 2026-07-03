import { Link } from 'react-router-dom';
import { Play, Loader2, ArrowRight } from 'lucide-react';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { formatDate } from '@/lib/utils';
import { normalizeStatusKey, statusBadgeLabel } from '@/lib/projectStatus';
import type { RecentPipelineRow } from '@/hooks/useLatestPipelineRuns';

interface RecentPipelineSectionProps {
  rows: RecentPipelineRow[];
  loading: boolean;
}

export function RecentPipelineSection({ rows, loading }: RecentPipelineSectionProps) {
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
                const rawStatus = run.status || 'pending';
                const badgeStatus = normalizeStatusKey(rawStatus);
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
                      <StatusBadge
                        status={badgeStatus}
                        label={statusBadgeLabel(badgeStatus, rawStatus, true)}
                      />
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
