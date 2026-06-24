import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Clock, Loader2, ArrowRight, FlaskConical, AlertTriangle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { projectService } from '@/services/projectService';
import { reportService } from '@/services/reportService';
import type { ProjectOverview, ReportData } from '@/types';

interface ReportEntry {
  projectId: string;
  projectName: string;
  report: ReportData;
}

export function Reports() {
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
  }, []);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader
          title="报告中心"
          subtitle="查看和管理 AI Scientist 生成的研究报告"
        />
        <Card className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-bp-cyan animate-spin mr-3" />
          <span className="text-bp-muted">正在加载报告...</span>
        </Card>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader
          title="报告中心"
          subtitle="查看和管理 AI Scientist 生成的研究报告"
        />
        <Card className="flex flex-col items-center justify-center py-12 gap-3 border-danger-500/30 bg-danger-500/5">
          <AlertTriangle className="w-8 h-8 text-danger-400" />
          <p className="text-danger-300 text-sm">{errorMsg}</p>
          <Button onClick={() => window.location.reload()} variant="secondary" size="sm">
            重试
          </Button>
        </Card>
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader
          title="报告中心"
          subtitle="查看和管理 AI Scientist 生成的研究报告"
        />
        <Card className="flex flex-col items-center justify-center py-12 gap-3">
          <FileText className="w-10 h-10 text-bp-muted" />
          <p className="text-bp-muted text-sm">暂无研究报告</p>
          <p className="text-xs text-bp-muted/80">
            请先创建项目并通过工作流生成研究报告
          </p>
          <Link to="/">
            <Button variant="secondary" size="sm">
              前往项目列表
            </Button>
          </Link>
        </Card>
      </div>
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
