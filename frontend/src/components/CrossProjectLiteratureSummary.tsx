import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, FolderOpen, ExternalLink } from 'lucide-react';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { documentService } from '@/services/documentService';
import type { ProjectOverview } from '@/types';

interface ProjectDocSummary {
  projectId: string;
  projectName: string;
  total: number;
  processed: number;
  failed: number;
}

interface CrossProjectLiteratureSummaryProps {
  projects: ProjectOverview[];
}

/** 跨项目文献汇总 — 并行拉取各项目文档数，无需后端聚合 API */
export function CrossProjectLiteratureSummary({ projects }: CrossProjectLiteratureSummaryProps) {
  const [summaries, setSummaries] = useState<ProjectDocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (projects.length === 0) {
      setSummaries([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(
        projects.map(async (p) => {
          try {
            const res = await documentService.getDocuments(p.id, 1, 200);
            const items = res.code === 200 ? res.data?.items ?? [] : [];
            return {
              projectId: p.id,
              projectName: p.name,
              total: items.length,
              processed: items.filter((d) => d.status === 'processed').length,
              failed: items.filter((d) => d.status === 'failed').length,
            };
          } catch {
            return {
              projectId: p.id,
              projectName: p.name,
              total: 0,
              processed: 0,
              failed: 0,
            };
          }
        }),
      );
      setSummaries(results.sort((a, b) => b.total - a.total));
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载跨项目文献汇总失败');
    } finally {
      setLoading(false);
    }
  }, [projects]);

  useEffect(() => {
    load();
  }, [load]);

  const totalDocs = summaries.reduce((n, s) => n + s.total, 0);

  if (loading) {
    return (
      <Card>
        <LoadingState message="正在汇总各项目文献..." />
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <ErrorState message={error} onRetry={load} />
      </Card>
    );
  }

  if (projects.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<FolderOpen className="w-8 h-8" />}
          title="暂无项目"
          description="创建项目后可在各项目工作台上传文献，此处将显示跨项目汇总"
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-cyan">{projects.length}</div>
          <div className="text-bp-muted text-sm">项目数</div>
        </div>
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-green">{totalDocs}</div>
          <div className="text-bp-muted text-sm">文献总数</div>
        </div>
        <div className="bp-metric-box col-span-2 md:col-span-1">
          <div className="text-bp-metric font-bold text-bp-purple">
            {summaries.filter((s) => s.total > 0).length}
          </div>
          <div className="text-bp-muted text-sm">有文献的项目</div>
        </div>
      </div>

      <Card>
        <div className="flex items-center gap-2 mb-4">
          <BookOpen className="w-4 h-4 text-bp-cyan" />
          <h3 className="text-sm font-semibold text-bp-text">各项目文献概览</h3>
        </div>
        {totalDocs === 0 ? (
          <p className="text-sm text-bp-muted py-4 text-center">
            各项目尚未上传文献。请在上方选择具体项目，或进入项目工作台的「文献库」Tab 上传。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-bp-border">
                  <th className="pb-2 text-xs text-bp-muted font-medium">项目</th>
                  <th className="pb-2 text-xs text-bp-muted font-medium text-center">文献数</th>
                  <th className="pb-2 text-xs text-bp-muted font-medium text-center">已解析</th>
                  <th className="pb-2 text-xs text-bp-muted font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {summaries.map((row) => (
                  <tr key={row.projectId} className="border-b border-bp-border/50 last:border-0">
                    <td className="py-2.5 pr-3 text-bp-text font-medium">{row.projectName}</td>
                    <td className="py-2.5 text-center font-mono text-bp-cyan">{row.total}</td>
                    <td className="py-2.5 text-center font-mono text-bp-green">{row.processed}</td>
                    <td className="py-2.5 text-right">
                      <Link
                        to={`/projects/${row.projectId}?tab=literature`}
                        className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-text transition-colors"
                      >
                        进入文献库
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-bp-muted mt-4">
          上传与管理请在上方选择具体项目，或使用各项目工作台的文献库 Tab。
        </p>
      </Card>
    </div>
  );
}
