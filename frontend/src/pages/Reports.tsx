import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, Clock, ArrowRight, FlaskConical } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { projectService } from '@/services/projectService';
import { reportService } from '@/services/reportService';
import type { ProjectOverview, ReportData } from '@/types';

interface ReportEntry {
  projectId: string;
  projectName: string;
  report: ReportData;
}

export function Reports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const res = await projectService.getProjects();
        if (res.code !== 200 || !res.data) {
          setReports([]);
          return;
        }

        const data = res.data as unknown as { list?: ProjectOverview[]; pagination?: unknown };
        const projects: ProjectOverview[] = Array.isArray(data) ? data : (data.list ?? []);
        if (projects.length === 0) {
          setReports([]);
          return;
        }
        const results = await Promise.allSettled(
          projects.map(async (p) => {
            const report = await reportService.getLatest(p.id);
            return report ? { projectId: p.id, projectName: p.name, report } : null;
          }),
        );

        const entries: ReportEntry[] = [];
        results.forEach((r) => {
          if (r.status === 'fulfilled' && r.value) {
            entries.push(r.value);
          }
        });

        setReports(entries);
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : '加载失败');
      } finally {
        setIsLoading(false);
      }
    })();
  }, [reloadTick]);

  const shell = (children: React.ReactNode) => (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="报告中心"
        subtitle="查看和管理 AI Scientist 生成的研究报告"
      />
      {children}
    </div>
  );

  if (isLoading) {
    return shell(
      <Card>
        <LoadingState message="正在加载报告..." />
      </Card>,
    );
  }

  if (errorMsg) {
    return shell(
      <Card>
        <ErrorState
          message={errorMsg}
          onRetry={() => setReloadTick((t) => t + 1)}
        />
      </Card>,
    );
  }

  if (reports.length === 0) {
    return shell(
      <Card>
        <EmptyState
          icon={<FileText className="w-8 h-8" />}
          title="暂无研究报告"
          description="请先创建项目并通过工作流生成研究报告"
          action={{ label: '前往项目列表', onClick: () => navigate('/') }}
        />
      </Card>,
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="报告中心"
        subtitle={`共 ${reports.length} 份研究报告`}
      />
      <div className="space-y-4">
        {reports.map((entry) => (
          <Link
            key={entry.projectId}
            to={`/projects/${entry.projectId}?tab=reports`}
            className="block"
          >
            <Card className="hover:border-bp-cyan/30 transition-colors cursor-pointer group">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-bp bg-bp-cyan-tint border border-bp-cyan/20 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-bp-cyan" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-bp-text truncate group-hover:text-bp-cyan transition-colors">
                      {entry.report.title}
                    </h3>
                    <div className="flex items-center gap-3 mt-1 text-xs text-bp-muted">
                      <span className="flex items-center gap-1">
                        <FlaskConical className="w-3 h-3" />
                        {entry.projectName}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {entry.report.generatedAt}
                      </span>
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-bp-muted group-hover:text-bp-cyan shrink-0 transition-colors" />
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
