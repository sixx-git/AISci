import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FileText, Clock, Loader2, AlertTriangle, BookOpen, ExternalLink, BarChart3, CheckCircle2, GraduationCap, MessageSquare, FileDown, History, Code2 } from 'lucide-react';
import { Card } from './Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { ReportPdfPreview, ReportPreviewHeader } from './ReportPdfPreview';
import { ReportChecklist } from './ReportChecklist';
import { EvidenceChainQualityCard } from './EvidenceChainQualityCard';
import { QualityCheckCard } from './QualityCheckCard';
import type { ReportData, ReportPlot } from '@/types';
import { reportService } from '@/services/reportService';
import humanLoopService, { type MentorReview } from '@/services/humanLoopService';
import { useToast } from '@/hooks/useToast';
import { REPORT_SECTION_OPTIONS } from '@/config/reportSections';
import { countRealReferences } from '@/lib/reportCompliance';
import { buildReportDownloadFilename } from '@/lib/reportExport';
import { cn } from '@/lib/utils';

interface ReportPageProps {
  projectId: string;
  projectMode?: string;
  compact?: boolean;
  literatureCount?: number;
  revalidateKey?: number;
  latestRunId?: string | null;
}

const selectChevronStyle = {
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2364748B' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: '2.5rem',
} as const;

function formatReportVersionLabel(entry: ReportData, index: number, total: number) {
  const ordinal = total - index;
  const prefix = index === 0 ? '最新' : `第 ${ordinal} 版`;
  const title = entry.title.length > 40 ? `${entry.title.slice(0, 37)}…` : entry.title;
  return `${prefix} · ${entry.generatedAt} · ${title}`;
}

function plotSourceLabel(plot: ReportPlot): { text: string; tone: 'green' | 'yellow' | 'muted' } {
  if (plot.chart_kind === 'descriptive_stat') {
    return { text: '数据探索', tone: 'muted' };
  }
  const source = (plot.source || '').toLowerCase();
  if (
    source === 'sandbox_execution'
    || source === 'pilot_analysis'
    || plot.chart_kind === 'experiment_result'
    || plot.type === 'sandbox_plot'
  ) {
    return { text: '实验产出', tone: 'green' };
  }
  if (plot.is_generated_from_real_data) {
    return { text: '待验证', tone: 'yellow' };
  }
  return { text: '待验证', tone: 'yellow' };
}

function ReportPlotImage({
  reportId,
  plot,
}: {
  reportId: string;
  plot: ReportPlot;
}) {
  const candidates = useMemo(() => {
    const urls: string[] = [];
    if (plot.url) urls.push(plot.url);
    if (reportId && plot.plot_id) {
      urls.push(`/api/v1/reports/plots/${reportId}/${plot.plot_id}/image`);
    }
    if (plot.base64) {
      urls.push(`data:image/png;base64,${plot.base64}`);
    }
    return [...new Set(urls)];
  }, [reportId, plot]);

  const [idx, setIdx] = useState(0);
  const [exhausted, setExhausted] = useState(false);
  const src = !exhausted ? (candidates[idx] ?? null) : null;

  if (!src) {
    return (
      <span className="text-xs text-bp-muted text-center px-2">
        图表不可用
        {plot.plot_id ? `（${plot.plot_id}）` : ''}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={plot.title}
      loading="lazy"
      className="max-w-full max-h-[300px] object-contain rounded"
      onError={() => {
        setIdx((prev) => {
          if (prev + 1 < candidates.length) return prev + 1;
          setExhausted(true);
          return prev;
        });
      }}
    />
  );
}

export function ReportPage({
  projectId,
  projectMode: _projectMode,
  compact: _compact = false,
  literatureCount,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: ReportPageProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { message: alertMsg, showAlert } = useToast(2500);
  const [report, setReport] = useState<ReportData | null>(null);
  const [reportVersions, setReportVersions] = useState<ReportData[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSwitchingVersion, setIsSwitchingVersion] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [reviseMessage, setReviseMessage] = useState('');
  const [reviseBusy, setReviseBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [reviseScope, setReviseScope] = useState<'full' | 'section'>('full');
  const [selectedSections, setSelectedSections] = useState<string[]>([]);
  const [mentorNotes, setMentorNotes] = useState('');
  const [mentorReview, setMentorReview] = useState<MentorReview | null>(null);
  const [mentorBusy, setMentorBusy] = useState(false);
  const [lastChatReply, setLastChatReply] = useState('');
  const [regeneratingPdf, setRegeneratingPdf] = useState(false);
  const [pdfRefreshKey, setPdfRefreshKey] = useState(0);

  const loadProjectReports = useCallback(async (preferReportId?: string | null) => {
    const list = await reportService.getList(projectId);
    setReportVersions(list);

    if (list.length === 0) {
      setReport(null);
      setSelectedReportId(null);
      return null;
    }

    const targetId = preferReportId && list.some((item) => item.id === preferReportId)
      ? preferReportId
      : list[0].id;
    const target = list.find((item) => item.id === targetId) ?? list[0];
    setSelectedReportId(target.id);
    setReport(target);
    return target;
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;

    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        await loadProjectReports(null);
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : '加载报告失败');
      } finally {
        setIsLoading(false);
      }
    })();
  }, [projectId, _revalidateKey, _latestRunId, loadProjectReports]);

  useEffect(() => {
    if (!projectId || reloadTick === 0) return;

    (async () => {
      try {
        await loadProjectReports(selectedReportId);
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : '加载报告失败');
      }
    })();
  }, [reloadTick, projectId, selectedReportId, loadProjectReports]);

  const handleVersionChange = useCallback(async (reportId: string) => {
    if (reportId === selectedReportId) return;
    setIsSwitchingVersion(true);
    setSelectedReportId(reportId);
    try {
      const cached = reportVersions.find((item) => item.id === reportId);
      if (cached) {
        setReport(cached);
        return;
      }
      const detail = await reportService.getDetail(reportId);
      if (detail) {
        setReport(detail);
        setReportVersions((prev) => prev.map((item) => (item.id === detail.id ? detail : item)));
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '切换报告版本失败');
    } finally {
      setIsSwitchingVersion(false);
    }
  }, [reportVersions, selectedReportId, showAlert]);

  const reportPageHeader = (
    <div className="mb-6">
      <h1 className="text-3xl font-bold text-bp-text mb-1">研究报告</h1>
      <p className="text-bp-muted text-sm">自动生成符合比赛规范的科学假设与研究计划</p>
    </div>
  );

  const revisionHistory = (report?.extraMetadata?.revision_history as Array<Record<string, unknown>> | undefined) || [];
  const chatHistory = (report?.extraMetadata?.chat_history as Array<Record<string, unknown>> | undefined) || [];

  const reloadReport = useCallback(async () => {
    const currentId = selectedReportId ?? report?.id ?? null;
    if (currentId) {
      const detail = await reportService.getDetail(currentId);
      if (detail) {
        setReport(detail);
        setReportVersions((prev) => {
          const exists = prev.some((item) => item.id === detail.id);
          if (!exists) return [detail, ...prev];
          return prev.map((item) => (item.id === detail.id ? detail : item));
        });
        setSelectedReportId(detail.id);
        return detail;
      }
    }
    return loadProjectReports(currentId);
  }, [selectedReportId, report?.id, loadProjectReports]);

  const handleMentorReview = useCallback(async () => {
    if (!report?.id) return;
    setMentorBusy(true);
    try {
      const res = await humanLoopService.mentorReview({
        project_id: projectId,
        report_id: report.id,
        target_type: 'report',
        content: report.reportContent,
        user_notes: mentorNotes,
      });
      if (res.code === 200 && res.data?.review) {
        setMentorReview(res.data.review);
        showAlert('导师评审完成');
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '导师评审失败');
    } finally {
      setMentorBusy(false);
    }
  }, [projectId, report?.id, report?.reportContent, mentorNotes, showAlert]);

  const handleReviseReport = useCallback(async () => {
    if (!report?.id || !reviseMessage.trim()) return;
    if (reviseScope === 'section' && selectedSections.length === 0) {
      showAlert('请至少选择一个章节');
      return;
    }
    setReviseBusy(true);
    try {
      const res = await humanLoopService.reviseReport({
        project_id: projectId,
        report_id: report.id,
        message: reviseMessage.trim(),
        section_keys: reviseScope === 'section' ? selectedSections : [],
        apply_change: true,
      });
      if (res.code === 200) {
        setLastChatReply(res.data?.explanation || '报告已更新');
        setReviseMessage('');
        await reloadReport();
        showAlert(reviseScope === 'section' ? '选定章节已更新' : '报告已根据反馈更新');
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '修改失败');
    } finally {
      setReviseBusy(false);
    }
  }, [projectId, report?.id, reviseMessage, reviseScope, selectedSections, reloadReport, showAlert]);

  const handleExport = useCallback(async (fileType: 'pdf' | 'tex') => {
    if (!report?.id) {
      showAlert('暂无报告可导出');
      return;
    }

    const downloadFilename = buildReportDownloadFilename(report.title, fileType);
    const successLabels = { tex: 'LaTeX', pdf: 'PDF' } as const;
    try {
      const blob = await reportService.download(report.id, fileType);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showAlert(`${successLabels[fileType]} 导出成功`);
    } catch {
      showAlert('导出失败，请重试');
    }
  }, [report, showAlert]);

  const handleRegeneratePdf = useCallback(async () => {
    if (!report?.id) return;
    const handEdited = Boolean(report.extraMetadata?.latex_hand_edited);
    if (handEdited) {
      const ok = window.confirm(
        '该报告曾在 LaTeX 编辑器中手工修改。「重新生成 PDF」会从章节内容重建源码并覆盖手改，是否继续？\n\n若只想编译当前手改源码，请使用「打开 LaTeX 编辑器」→「编译 PDF」。',
      );
      if (!ok) return;
    }
    setRegeneratingPdf(true);
    try {
      const res = await reportService.regeneratePdf(report.id);
      if (res.code === 200) {
        await reloadReport();
        setPdfRefreshKey((k) => k + 1);
        showAlert(res.data?.pdf_success ? 'PDF 生成成功' : 'PDF 生成失败，请检查 LaTeX 环境');
      } else {
        showAlert(res.message || 'PDF 重新生成失败');
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : 'PDF 重新生成失败');
    } finally {
      setRegeneratingPdf(false);
    }
  }, [report?.id, report?.extraMetadata?.latex_hand_edited, reloadReport, showAlert]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto">
        {reportPageHeader}
        <Card>
          <LoadingState message="正在加载报告..." />
        </Card>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="max-w-7xl mx-auto">
        {reportPageHeader}
        <Card>
          <ErrorState
            message={errorMsg}
            onRetry={() => setReloadTick((t) => t + 1)}
          />
        </Card>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-7xl mx-auto">
        {reportPageHeader}
        <Card>
          <EmptyState
            icon={<FileText className="w-8 h-8" />}
            title="暂无研究报告"
            description="请先在「迭代实验」页勾选实验并点击「生成报告」"
          />
        </Card>
      </div>
    );
  }

  const sections = report.sections || [];
  const complianceCheck = report.complianceCheck;
  const realReferenceCount = countRealReferences(report.reportContent?.references);
  const hasNoRefs = complianceCheck
    && (complianceCheck.references_verified ?? 0) === 0
    && realReferenceCount === 0;
  const hasOnlyExpected = complianceCheck?.result_type === 'expected_result' || complianceCheck?.result_type === 'none';
  const hasNoDatasets = complianceCheck && !complianceCheck.has_datasets;
  const hasNoSource = complianceCheck && !complianceCheck.has_source;
  const hasNoTarget = complianceCheck && !complianceCheck.has_target;
  const pdfFailed = report.pdfSuccess === false;
  const criticalIssues = complianceCheck?.critical_issues || [];
  const warnings = complianceCheck?.warnings || [];

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-bp-text mb-1">研究报告</h1>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="text-bp-muted text-sm">自动生成符合挑战杯 XH-202619 规范的科学假设与研究计划</p>
          <span className="text-xs px-2 py-0.5 rounded border border-bp-border bg-bp-panel text-bp-muted">
            通用报告
          </span>
        </div>

        {reportVersions.length > 0 && (
          <div className="mt-4 flex flex-col sm:flex-row sm:items-end gap-3">
            <div className="flex-1 min-w-0">
              <label htmlFor="report-version-select" className="flex items-center gap-1.5 text-xs text-bp-muted mb-1.5">
                <History className="w-3.5 h-3.5" />
                报告版本
                <span className="text-bp-muted/70">（共 {reportVersions.length} 份）</span>
              </label>
              <select
                id="report-version-select"
                value={selectedReportId ?? report.id}
                disabled={isSwitchingVersion || reportVersions.length <= 1}
                onChange={(e) => void handleVersionChange(e.target.value)}
                className="input-field py-2.5 w-full max-w-3xl appearance-none cursor-pointer disabled:cursor-default disabled:opacity-80"
                style={selectChevronStyle}
              >
                {reportVersions.map((entry, index) => (
                  <option key={entry.id} value={entry.id}>
                    {formatReportVersionLabel(entry, index, reportVersions.length)}
                  </option>
                ))}
              </select>
            </div>
            {reportVersions.length > 1 && selectedReportId === reportVersions[0]?.id && (
              <span className="text-xs text-bp-green shrink-0 pb-2.5">当前为最新生成结果</span>
            )}
            {reportVersions.length > 1 && selectedReportId !== reportVersions[0]?.id && (
              <span className="text-xs text-bp-yellow shrink-0 pb-2.5">正在查看历史版本</span>
            )}
          </div>
        )}
      </div>

      {/* ── 警告横幅区 ── */}
      <div className="space-y-3 mb-6">
        {/* References 为空 → 红色 warning */}
        {hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-danger-500/10 border border-danger-500/25">
            <AlertTriangle className="w-5 h-5 text-danger-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-danger-300 mb-1">
                参考论文缺失或未验证，不符合赛题要求
              </p>
              <p className="text-xs text-danger-300/70 mb-2 leading-relaxed">
                参考文献未能在文献库中找到匹配条目，存在虚构引用风险。请先上传 PDF 或导入 arXiv 文献后再生成报告。
              </p>
              <button
                onClick={() => navigate('/documents')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-bp bg-danger-500/20 border border-danger-500/30 text-xs text-danger-300 hover:bg-danger-500/30 transition-colors"
              >
                <BookOpen className="w-3.5 h-3.5" />
                前往文献库导入文献
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}

        {/* 仅有预期结果 → 黄色 warning */}
        {hasOnlyExpected && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-bp-yellow/10 border border-bp-yellow/25">
            <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-bp-yellow mb-1">
                当前仅有预期结果，建议补充公式推导、模拟验证或小样实验
              </p>
              <p className="text-xs text-bp-yellow/70 leading-relaxed">
                Results 中未检测到实际执行结果（Actual Results）或模拟结果（Simulated Results）。建议在「迭代实验」完成至少一轮 smoke/full 推演以增强报告可信度。
              </p>
            </div>
          </div>
        )}

        {/* Dataset 没有真实来源 → 黄色 warning */}
        {hasNoDatasets && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-bp-yellow/10 border border-bp-yellow/25">
            <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-bp-yellow mb-1">
                数据集来源不足，请补充真实或合规数据来源
              </p>
              <p className="text-xs text-bp-yellow/70 leading-relaxed">
                Datasets 章节内容不足，需要说明真实来源或拟采集状态。
              </p>
            </div>
          </div>
        )}

        {/* Source 缺失 → 黄色 warning */}
        {hasNoSource && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-bp-yellow/10 border border-bp-yellow/25">
            <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-bp-yellow mb-1">
                缺少真实历史数据来源（Source）
              </p>
              <p className="text-xs text-bp-yellow/70 leading-relaxed">
                请补充假设推演所依据的历史数据或文献来源。
              </p>
            </div>
          </div>
        )}

        {/* Target 缺失 → 黄色 warning */}
        {hasNoTarget && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-bp-yellow/10 border border-bp-yellow/25">
            <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-bp-yellow mb-1">
                缺少目标数据特征描述（Target）
              </p>
              <p className="text-xs text-bp-yellow/70 leading-relaxed">
                请补充验证实验所需的拟采集数据特征描述。
              </p>
            </div>
          </div>
        )}

        {/* 严重问题列表 */}
        {criticalIssues.length > 0 && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-danger-500/10 border border-danger-500/25">
            <AlertTriangle className="w-5 h-5 text-danger-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-danger-300 mb-1">赛题合规严重问题</p>
              <ul className="list-disc list-inside text-xs text-danger-300/70 leading-relaxed">
                {criticalIssues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* PDF 导出失败 → 黄色 warning */}
        {pdfFailed && !hasNoRefs && criticalIssues.length === 0 && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-bp-yellow/10 border border-bp-yellow/25">
            <AlertTriangle className="w-5 h-5 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-bp-yellow mb-1">
                PDF 导出失败
              </p>
              <p className="text-xs text-bp-yellow/70 leading-relaxed">
                LaTeX PDF 编译失败。请点击预览区「重新生成 PDF」，或检查服务器是否已安装 XeLaTeX。
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 顶部信息栏 + 操作按钮 */}
      <div className="mb-6">
        <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-bp-cyan-tint border border-bp-cyan/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-bp-cyan" />
            </div>
            <div>
              <p className="text-sm font-medium text-bp-text">{report.title}</p>
              <div className="flex items-center gap-1 mt-0.5 text-xs text-bp-muted">
                <Clock className="w-3 h-3" />
                <span>生成于 {report.generatedAt}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => navigate('/documents')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bp-panel border border-bp-border text-xs text-bp-muted hover:text-bp-text hover-accent-left transition-colors"
              title="前往文献库导入文献"
            >
              <BookOpen className="w-3.5 h-3.5" />
              导入文献
            </button>
            <button
              type="button"
              onClick={() => {
                const next = new URLSearchParams(searchParams);
                next.set('tab', 'reports');
                next.set('view', 'latex');
                next.set('reportId', report.id);
                setSearchParams(next);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bp-cyan/15 border border-bp-cyan/30 text-xs text-bp-cyan hover:bg-bp-cyan/25 transition-colors"
              title="打开内置 LaTeX 编辑器（类似 Overleaf）"
            >
              <Code2 className="w-3.5 h-3.5" />
              打开 LaTeX 编辑器
            </button>
            <button
              type="button"
              onClick={() => handleExport('tex')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bp-panel border border-bp-border text-xs text-bp-muted hover:text-bp-text hover-accent-left transition-colors"
              title="导出 LaTeX 源文件"
            >
              <FileDown className="w-3.5 h-3.5" />
              导出 LaTeX
            </button>
          </div>
        </Card>
      </div>

      {/* 主体：PDF 预览 · 右侧检查 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 space-y-4">
          <Card className="min-w-0">
            <ReportPreviewHeader
              title={report.title}
              onDownloadPdf={() => handleExport('pdf')}
              onRegeneratePdf={handleRegeneratePdf}
              regenerating={regeneratingPdf}
            />
            <ReportPdfPreview
              reportId={report.id}
              refreshKey={pdfRefreshKey}
              onRegeneratePdf={handleRegeneratePdf}
              regenerating={regeneratingPdf}
            />
          </Card>

          {/* ── 实验结果图表 ── */}
          {report.plots && report.plots.length > 0 && (
            <Card className="mt-4">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-4 h-4 text-bp-green" />
                <div>
                  <h3 className="text-sm font-semibold text-bp-text">实验结果图表</h3>
                  <p className="text-xs text-bp-muted">
                    共 {report.plots.length} 张 · 含实验条件、评估指标与基线对比说明
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {report.plots.map((plot: ReportPlot) => (
                  <div
                    key={plot.plot_id}
                    className="rounded-bp border border-bp-border bg-bp-base/60 overflow-hidden"
                  >
                    <div className="px-3 py-2 border-b border-bp-border/60 bg-bp-base/50">
                      <p className="text-xs font-medium text-bp-text">{plot.title}</p>
                      {(plot.caption || plot.description) && (
                        <p className="text-xs text-bp-muted mt-1 leading-relaxed line-clamp-4">
                          {plot.caption || plot.description}
                        </p>
                      )}
                      <div className="mt-2 space-y-1">
                        {plot.experiment_condition && (
                          <p className="text-[11px] text-bp-muted">
                            <span className="text-bp-text/80">实验条件：</span>
                            {plot.experiment_condition}
                          </p>
                        )}
                        {plot.metric && (
                          <p className="text-[11px] text-bp-muted">
                            <span className="text-bp-text/80">评估指标：</span>
                            {plot.metric}
                            {plot.metric_direction === 'higher_is_better' && '（越高越好）'}
                            {plot.metric_direction === 'lower_is_better' && '（越低越好）'}
                          </p>
                        )}
                        {plot.baseline_comparison && (
                          <p className="text-[11px] text-bp-muted">
                            <span className="text-bp-text/80">对比结论：</span>
                            {plot.baseline_comparison}
                          </p>
                        )}
                        {(plot.x_label || plot.y_label) && (
                          <p className="text-[11px] text-bp-muted">
                            <span className="text-bp-text/80">坐标轴：</span>
                            {[plot.x_label, plot.y_label].filter(Boolean).join(' · ')}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <span className="inline-block px-1.5 py-0.5 text-xs rounded bg-bp-surface/50 text-bp-muted">
                          {plot.type}
                        </span>
                        {(() => {
                          const badge = plotSourceLabel(plot);
                          return (
                            <span
                              className={cn(
                                'inline-flex items-center gap-0.5 px-1.5 py-0.5 text-xs rounded',
                                badge.tone === 'green' && 'bg-bp-green/15 text-bp-green',
                                badge.tone === 'yellow' && 'bg-bp-yellow/15 text-bp-yellow',
                                badge.tone === 'muted' && 'bg-bp-surface/50 text-bp-muted',
                              )}
                            >
                              {badge.tone === 'green' ? (
                                <CheckCircle2 className="w-2.5 h-2.5" />
                              ) : (
                                <AlertTriangle className="w-2.5 h-2.5" />
                              )}
                              {badge.text}
                            </span>
                          );
                        })()}
                        {plot.has_legend && (
                          <span className="text-[11px] text-bp-muted">含图例</span>
                        )}
                      </div>
                    </div>
                    <div className="p-3 flex items-center justify-center bg-bp-base/40 min-h-[200px]">
                      <ReportPlotImage reportId={report.id} plot={plot} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 无图表时的提示 */}
          {(!report.plots || report.plots.length === 0) && (
            <Card className="mt-4">
              <div className="flex items-start gap-3 p-2">
                <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-medium text-bp-yellow mb-1">暂无实验结果图表</p>
                  <p className="text-xs text-bp-yellow/70 leading-relaxed">
                    报告图表需来自迭代实验（smoke/full）沙箱产物（含方法对比指标、误差棒与显著性），
                    不再从原始 FITS/CSV 自动生成均值/标准差描述图。
                    请先在「迭代实验」页完成推演，并确保分析脚本输出 metrics.json 与实验图。
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* 右侧：比赛规范检查 + 证据链质量 + 操作 */}
        <div className="lg:col-span-4">
          <div className="overflow-y-auto max-h-[calc(100vh-320px)] space-y-4 pr-1 scrollbar-thin scrollbar-thumb-bp-muted scrollbar-track-transparent">
            <ReportChecklist
              sections={sections}
              complianceCheck={complianceCheck}
              warnings={warnings}
              referencesRaw={report.reportContent?.references}
            />
            <QualityCheckCard
              complianceCheck={complianceCheck}
            />
            <EvidenceChainQualityCard
              complianceCheck={complianceCheck}
              literatureCount={literatureCount}
            />

            <Card title="人在回路 · 报告" subtitle="导师评审 · 多轮追问 · 局部修订">
              <button
                type="button"
                onClick={handleMentorReview}
                disabled={mentorBusy}
                className="w-full flex items-center justify-center gap-2 text-xs py-2 mb-3 rounded-bp border border-bp-yellow/30 bg-bp-yellow/10 text-bp-yellow hover:bg-bp-yellow/15 disabled:opacity-50"
              >
                {mentorBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <GraduationCap className="w-3.5 h-3.5" />}
                导师式评审
              </button>
              <textarea
                className="w-full min-h-[48px] rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text p-2 mb-2"
                placeholder="导师评审补充说明（可选）"
                value={mentorNotes}
                onChange={(e) => setMentorNotes(e.target.value)}
              />
              {mentorReview && (
                <div className="mb-3 p-2 rounded-bp border border-bp-yellow/20 bg-bp-yellow/5 text-xs space-y-1.5 max-h-48 overflow-y-auto">
                  {mentorReview.overall_assessment && (
                    <p className="text-bp-yellow/90">{mentorReview.overall_assessment}</p>
                  )}
                  {mentorReview.readiness_score != null && (
                    <p className="text-bp-muted">就绪度：{mentorReview.readiness_score}/10</p>
                  )}
                  {mentorReview.weaknesses?.length > 0 && (
                    <div>
                      <p className="text-bp-muted mb-0.5">不足</p>
                      <ul className="list-disc pl-4 text-bp-text">
                        {mentorReview.weaknesses.slice(0, 4).map((w) => <li key={w}>{w}</li>)}
                      </ul>
                    </div>
                  )}
                  {mentorReview.revision_suggestions?.length > 0 && (
                    <div>
                      <p className="text-bp-muted mb-0.5">修订建议</p>
                      <ul className="list-disc pl-4 text-bp-text">
                        {mentorReview.revision_suggestions.slice(0, 4).map((s) => <li key={s}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-2 mb-2">
                <button
                  type="button"
                  onClick={() => setReviseScope('full')}
                  className={cn(
                    'flex-1 text-xs py-1.5 rounded-lg border',
                    reviseScope === 'full'
                      ? 'border-bp-cyan/40 bg-bp-cyan-tint text-bp-cyan'
                      : 'border-bp-border text-bp-muted',
                  )}
                >
                  整份报告
                </button>
                <button
                  type="button"
                  onClick={() => setReviseScope('section')}
                  className={cn(
                    'flex-1 text-xs py-1.5 rounded-lg border',
                    reviseScope === 'section'
                      ? 'border-bp-cyan/40 bg-bp-cyan-tint text-bp-cyan'
                      : 'border-bp-border text-bp-muted',
                  )}
                >
                  选定章节
                </button>
              </div>

              {reviseScope === 'section' && (
                <div className="mb-2 max-h-28 overflow-y-auto grid grid-cols-1 gap-1">
                  {REPORT_SECTION_OPTIONS.map((opt) => (
                    <label key={opt.key} className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedSections.includes(opt.key)}
                        onChange={(e) => {
                          setSelectedSections((prev) =>
                            e.target.checked
                              ? [...prev, opt.key]
                              : prev.filter((k) => k !== opt.key),
                          );
                        }}
                        className="rounded border-bp-border"
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-1.5 text-xs text-bp-muted mb-1">
                <MessageSquare className="w-3.5 h-3.5" />
                追问修改
              </div>
              <textarea
                className="w-full min-h-[72px] rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text p-2 mb-2"
                placeholder="例如：加强 Methods 部分 / 结论更保守 / 补充 VFL 约束"
                value={reviseMessage}
                onChange={(e) => setReviseMessage(e.target.value)}
              />
              <button
                type="button"
                onClick={handleReviseReport}
                disabled={reviseBusy || !reviseMessage.trim()}
                className="w-full text-xs py-2 rounded-bp bg-bp-green/90 hover:bg-bp-green text-bp-text disabled:opacity-50"
              >
                {reviseBusy ? '修改中…' : reviseScope === 'section' ? '修改选定章节' : '根据反馈修改报告'}
              </button>

              {lastChatReply && (
                <p className="mt-2 text-xs text-bp-green/90 border border-bp-green/20 rounded-bp p-2">
                  {lastChatReply}
                </p>
              )}

              {chatHistory.length > 0 && (
                <div className="mt-3 space-y-1.5 max-h-44 overflow-y-auto">
                  <p className="text-xs text-bp-muted">对话记录 ({chatHistory.length})</p>
                  {chatHistory.slice().reverse().map((h) => (
                    <div key={String(h.id || h.at)} className="text-xs border border-bp-border rounded p-2 space-y-1">
                      <div className="text-bp-muted">{String(h.at || '')}</div>
                      <div className="text-bp-cyan/90">你：{String(h.user_message || '')}</div>
                      {h.assistant_explanation ? (
                        <div className="text-bp-muted">助手：{String(h.assistant_explanation)}</div>
                      ) : null}
                      {Array.isArray(h.section_keys) && (h.section_keys as string[]).length > 0 && (
                        <div className="text-bp-muted">章节：{(h.section_keys as string[]).join(', ')}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {revisionHistory.length > 0 && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => setShowHistory(!showHistory)}
                    className="text-xs text-bp-muted hover:text-bp-text"
                  >
                    {showHistory ? '隐藏' : '查看'}修订快照 ({revisionHistory.length})
                  </button>
                  {showHistory && (
                    <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                      {revisionHistory.slice().reverse().map((h) => (
                        <div key={String(h.id || h.at)} className="text-xs text-bp-muted border border-bp-border rounded p-2">
                          <div className="text-bp-muted">{String(h.at || '')}</div>
                          <div className="text-bp-text mt-0.5">{String(h.user_message || '')}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>

      {/* Toast */}
      {alertMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-lg bg-bp-panel border border-bp-border text-sm text-bp-text shadow-lg animate-fade-in z-50">
          {alertMsg}
        </div>
      )}
    </div>
  );
}