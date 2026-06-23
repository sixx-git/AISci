import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Clock, Loader2, ArrowRight, FlaskConical, AlertTriangle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
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
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
          <span className="text-gray-400">正在加载报告...</span>
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
        <Card className="flex flex-col items-center justify-center py-12 gap-3">
          <AlertTriangle className="w-8 h-8 text-red-400" />
          <p className="text-red-300 text-sm">{errorMsg}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-primary-500/20 border border-primary-500/30 text-primary-300 text-xs hover:bg-primary-500/30 transition-colors"
          >
            重试
          </button>
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
          <FileText className="w-10 h-10 text-gray-600" />
          <p className="text-gray-500 text-sm">暂无研究报告</p>
          <p className="text-xs text-gray-600">
            请先创建项目并通过工作流生成研究报告
          </p>
          <Link
            to="/"
            className="px-4 py-2 rounded-lg bg-primary-500/20 border border-primary-500/30 text-primary-300 text-xs hover:bg-primary-500/30 transition-colors"
          >
            前往项目列表
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
            <Card className="hover:border-primary-500/30 transition-colors cursor-pointer group">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-primary-400" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-white truncate group-hover:text-primary-400 transition-colors">
                      {entry.report.title}
                    </h3>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
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
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-primary-400 shrink-0 transition-colors" />
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}