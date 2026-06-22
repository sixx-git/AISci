import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, Loader2, XCircle, AlertTriangle, BookOpen, ExternalLink, BarChart3, CheckCircle2, Database, Network } from 'lucide-react';
import { Card } from './Card';
import { MarkdownPreview } from './MarkdownPreview';
import { ReportChecklist } from './ReportChecklist';
import { EvidenceChainQualityCard } from './EvidenceChainQualityCard';
import { QualityCheckCard } from './QualityCheckCard';
import { ExportActions } from './ExportActions';
import type { ExportType } from './ExportActions';
import type { ReportData, ReportPlot } from '@/types';
import { reportService } from '@/services/reportService';
import humanLoopService from '@/services/humanLoopService';
import { useToast } from '@/hooks/useToast';

interface ReportPageProps {
  projectId: string;
  projectMode?: string;
  compact?: boolean;
  literatureCount?: number;
  revalidateKey?: number;
  latestRunId?: string | null;
}

export function ReportPage({
  projectId,
  projectMode,
  compact: _compact = false,
  literatureCount,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: ReportPageProps) {
  const navigate = useNavigate();
  const { message: alertMsg, showAlert } = useToast(2500);
  const [report, setReport] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reviseMessage, setReviseMessage] = useState('');
  const [reviseBusy, setReviseBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (!projectId) return;

    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const data = await reportService.getLatest(projectId);
        if (data) {
          setReport(data);
        }
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : '加载报告失败');
      } finally {
        setIsLoading(false);
      }
    })();
  }, [projectId, _revalidateKey, _latestRunId]);

  const revisionHistory = (report?.extraMetadata?.revision_history as Array<Record<string, unknown>> | undefined) || [];

  const handleReviseReport = useCallback(async () => {
    if (!report?.id || !reviseMessage.trim()) return;
    setReviseBusy(true);
    try {
      const res = await humanLoopService.reviseReport({
        project_id: projectId,
        report_id: report.id,
        message: reviseMessage.trim(),
      });
      if (res.code === 200) {
        showAlert('报告已根据反馈更新');
        setReviseMessage('');
        const data = await reportService.getLatest(projectId);
        if (data) setReport(data);
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '修改失败');
    } finally {
      setReviseBusy(false);
    }
  }, [projectId, report?.id, reviseMessage, showAlert]);

  const handleExport = useCallback(async (action: ExportType) => {
    if (action === 'generate') {
      showAlert('报告生成功能请通过工作流页面触发');
      return;
    }

    if (action === 'copy') {
      if (report?.markdownContent) {
        try {
          await navigator.clipboard.writeText(report.markdownContent);
          showAlert('报告内容已复制到剪贴板');
        } catch {
          showAlert('复制失败，请手动复制');
        }
      }
      return;
    }

    if (!report?.id) {
      showAlert('暂无报告可导出');
      return;
    }

    const fileType = action === 'markdown' ? 'md' : action === 'latex' ? 'tex' : 'pdf';
    const downloadNames: Record<string, string> = {
      md: '科学假设与研究计划.md',
      tex: '科学假设与研究计划.tex',
      pdf: '科学假设与研究计划.pdf',
    };
    const successLabels: Record<string, string> = {
      md: 'Markdown',
      tex: 'LaTeX',
      pdf: 'PDF',
    };
    try {
      const blob = await reportService.download(report.id, fileType as 'pdf' | 'md' | 'tex');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = downloadNames[fileType];
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showAlert(`${successLabels[fileType]} 导出成功`);
    } catch {
      showAlert('导出失败，请重试');
    }
  }, [report, showAlert]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
          <p className="text-gray-400 text-sm">自动生成符合比赛规范的科学假设与研究计划</p>
        </div>
        <Card className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
          <span className="text-gray-400">正在加载报告...</span>
        </Card>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
          <p className="text-gray-400 text-sm">自动生成符合比赛规范的科学假设与研究计划</p>
        </div>
        <Card className="flex flex-col items-center justify-center py-12 gap-4">
          <XCircle className="w-10 h-10 text-red-400" />
          <p className="text-red-300 text-sm">{errorMsg}</p>
          <button
            onClick={() => {
              setErrorMsg(null);
              setIsLoading(true);
              reportService.getLatest(projectId)
                .then(setReport)
                .catch((e) => setErrorMsg(e instanceof Error ? e.message : '加载失败'))
                .finally(() => setIsLoading(false));
            }}
            className="px-4 py-2 rounded-lg bg-primary-500/20 border border-primary-500/30 text-primary-300 text-xs hover:bg-primary-500/30 transition-colors"
          >
            重试
          </button>
        </Card>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
          <p className="text-gray-400 text-sm">自动生成符合比赛规范的科学假设与研究计划</p>
        </div>
        <Card className="flex flex-col items-center justify-center py-12 gap-3">
          <FileText className="w-10 h-10 text-gray-600" />
          <p className="text-gray-500 text-sm">暂无研究报告</p>
          <p className="text-xs text-gray-600">请先通过工作流触发报告生成</p>
        </Card>
      </div>
    );
  }

  const sections = report.sections || [];
  const complianceCheck = report.complianceCheck;
  const hasNoRefs = complianceCheck && !complianceCheck.has_references;
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
        <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="text-gray-400 text-sm">自动生成符合挑战杯 XH-202619 规范的科学假设与研究计划</p>
          <span className={`text-[11px] px-2 py-0.5 rounded border ${
            projectMode === 'federated_learning'
              ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
              : 'border-gray-600 bg-gray-800 text-gray-400'
          }`}>
            {projectMode === 'federated_learning' ? '联邦学习报告' : '通用报告'}
          </span>
          <button
            type="button"
            onClick={() => navigate(`/projects/${projectId}?tab=knowledge_graph`)}
            className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-[#00dc82]/40 bg-[#00dc82]/10 text-[#00dc82] hover:bg-[#00dc82]/20 transition-colors"
          >
            <Network className="w-3 h-3" />
            查看知识图谱
          </button>
        </div>
      </div>

      {/* ── 警告横幅区 ── */}
      <div className="space-y-3 mb-6">
        {/* References 为空 → 红色 warning */}
        {hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/25">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-300 mb-1">
                参考论文缺失或未验证，不符合赛题要求
              </p>
              <p className="text-xs text-red-300/70 mb-2 leading-relaxed">
                参考文献未能在文献库中找到匹配条目，存在虚构引用风险。请先上传 PDF、导入 arXiv 或 BibTeX 文献后再生成报告。
              </p>
              <button
                onClick={() => navigate('/documents')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/30 text-xs text-red-300 hover:bg-red-500/30 transition-colors"
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
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-300 mb-1">
                当前仅有预期结果，建议补充公式推导、模拟验证或小样实验
              </p>
              <p className="text-xs text-amber-300/70 leading-relaxed">
                Results 中未检测到实际执行结果（Actual Results）或模拟结果（Simulated Results）。建议补充小样验证或可行性模拟来增强报告可信度。
              </p>
            </div>
          </div>
        )}

        {/* Dataset 没有真实来源 → 黄色 warning */}
        {hasNoDatasets && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300 mb-1">
                数据集来源不足，请补充真实或合规数据来源
              </p>
              <p className="text-xs text-amber-300/70 leading-relaxed">
                Datasets 章节内容不足，需要说明真实来源或拟采集状态。
              </p>
            </div>
          </div>
        )}

        {/* Source 缺失 → 黄色 warning */}
        {hasNoSource && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300 mb-1">
                缺少真实历史数据来源（Source）
              </p>
              <p className="text-xs text-amber-300/70 leading-relaxed">
                请补充假设推演所依据的历史数据或文献来源。
              </p>
            </div>
          </div>
        )}

        {/* Target 缺失 → 黄色 warning */}
        {hasNoTarget && !hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300 mb-1">
                缺少目标数据特征描述（Target）
              </p>
              <p className="text-xs text-amber-300/70 leading-relaxed">
                请补充验证实验所需的拟采集数据特征描述。
              </p>
            </div>
          </div>
        )}

        {/* 严重问题列表 */}
        {criticalIssues.length > 0 && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/25">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-300 mb-1">赛题合规严重问题</p>
              <ul className="list-disc list-inside text-xs text-red-300/70 leading-relaxed">
                {criticalIssues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* PDF 导出失败 → 黄色 warning */}
        {pdfFailed && !hasNoRefs && criticalIssues.length === 0 && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300 mb-1">
                PDF 导出失败
              </p>
              <p className="text-xs text-amber-300/70 leading-relaxed">
                PDF 导出失败，不影响核心报告生成。Markdown 和 JSON 格式仍可使用。
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 顶部信息栏 + 操作按钮 */}
      <div className="mb-6">
        <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">{report.title}</p>
              <div className="flex items-center gap-1 mt-0.5 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                <span>生成于 {report.generatedAt}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/documents')}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-400 hover:text-gray-200 hover:border-gray-600 transition-colors"
              title="前往文献库导入文献"
            >
              <BookOpen className="w-3.5 h-3.5" />
              导入文献
            </button>
            <ExportActions onAction={handleExport} className="w-full sm:w-auto" />
          </div>
        </Card>
      </div>

      {/* 主体：左侧预览 + 右侧检查 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧：Markdown 预览 */}
        <div className="lg:col-span-3">
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-4 h-4 text-primary-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">报告预览</h3>
                <p className="text-xs text-gray-500">Markdown 格式 · 科学假设与研究计划</p>
              </div>
            </div>
            <div className="bg-gray-950/80 rounded-lg border border-gray-800 p-6 overflow-auto max-h-[calc(100vh-320px)]">
              <MarkdownPreview content={report.markdownContent} />
            </div>
          </Card>

          {/* ── 数据图表区域 ── */}
          {report.plots && report.plots.length > 0 && (
            <Card className="mt-4">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-4 h-4 text-emerald-400" />
                <div>
                  <h3 className="text-sm font-semibold text-white">数据可视化</h3>
                  <p className="text-xs text-gray-500">
                    共 {report.plots.length} 张图表 · 
                    {report.plots.filter(p => p.is_generated_from_real_data).length} 张基于真实数据
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {report.plots.map((plot: ReportPlot) => (
                  <div
                    key={plot.plot_id}
                    className="rounded-lg border border-gray-700 bg-gray-950/60 overflow-hidden"
                  >
                    <div className="px-3 py-2 border-b border-gray-700/60 bg-gray-900/50">
                      <p className="text-xs font-medium text-gray-200 truncate">{plot.title}</p>
                      {plot.description && (
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{plot.description}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="inline-block px-1.5 py-0.5 text-[10px] rounded bg-gray-700/50 text-gray-400">
                          {plot.type}
                        </span>
                        {plot.is_generated_from_real_data ? (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/15 text-emerald-400">
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            真实数据
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] rounded bg-amber-500/15 text-amber-400">
                            <AlertTriangle className="w-2.5 h-2.5" />
                            非真实数据
                          </span>
                        )}
                        {plot.source_dataset_id && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] rounded bg-blue-500/10 text-blue-400">
                            <Database className="w-2.5 h-2.5" />
                            {plot.source_dataset_id.slice(0, 8)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="p-3 flex items-center justify-center bg-gray-950/40 min-h-[200px]">
                      {plot.base64 ? (
                        <img
                          src={`data:image/png;base64,${plot.base64}`}
                          alt={plot.title}
                          className="max-w-full max-h-[300px] object-contain rounded"
                        />
                      ) : plot.url ? (
                        <img
                          src={plot.url}
                          alt={plot.title}
                          className="max-w-full max-h-[300px] object-contain rounded"
                        />
                      ) : (
                        <span className="text-xs text-gray-600">图表不可用</span>
                      )}
                    </div>
                    {plot.markdown_embed && (
                      <div className="px-3 py-1.5 border-t border-gray-700/60 bg-gray-900/30">
                        <code className="text-[10px] text-gray-500 break-all">{plot.markdown_embed}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 无图表时的提示 */}
          {(!report.plots || report.plots.length === 0) && (
            <Card className="mt-4">
              <div className="flex items-start gap-3 p-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-medium text-amber-300 mb-1">缺少真实数据，未生成图表</p>
                  {hasNoDatasets ? (
                    <p className="text-xs text-amber-300/70">
                      请通过"数据集"页面上传 CSV/Excel 等结构化数据文件，以启用统计图表生成。
                    </p>
                  ) : (
                    <p className="text-xs text-amber-300/70">
                      当前数据集可能不包含可分析的结构化数据，无法生成统计图表。
                    </p>
                  )}
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* 右侧：比赛规范检查 + 证据链质量 + 操作 */}
        <div className="lg:col-span-1">
          <div className="overflow-y-auto max-h-[calc(100vh-320px)] space-y-4 pr-1 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
            <ReportChecklist
              sections={sections}
              complianceCheck={complianceCheck}
              warnings={warnings}
            />
            <QualityCheckCard
              complianceCheck={complianceCheck}
            />
            <EvidenceChainQualityCard
              complianceCheck={complianceCheck}
              literatureCount={literatureCount}
            />

            <Card title="根据反馈修改报告" subtitle="多轮人在回路 · 保留修改历史">
              <textarea
                className="w-full min-h-[72px] rounded-lg bg-gray-900/70 border border-gray-800 text-xs text-gray-200 p-2 mb-2"
                placeholder="例如：加强数据集部分 / 加入 VFL 约束 / 结论更保守"
                value={reviseMessage}
                onChange={(e) => setReviseMessage(e.target.value)}
              />
              <button
                type="button"
                onClick={handleReviseReport}
                disabled={reviseBusy || !reviseMessage.trim()}
                className="w-full text-xs py-2 rounded-lg bg-emerald-600/90 hover:bg-emerald-600 text-white disabled:opacity-50"
              >
                {reviseBusy ? '修改中…' : '根据反馈修改报告'}
              </button>
              {revisionHistory.length > 0 && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => setShowHistory(!showHistory)}
                    className="text-[11px] text-gray-500 hover:text-gray-300"
                  >
                    {showHistory ? '隐藏' : '查看'}修改历史 ({revisionHistory.length})
                  </button>
                  {showHistory && (
                    <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                      {revisionHistory.slice().reverse().map((h) => (
                        <div key={String(h.id || h.at)} className="text-[10px] text-gray-500 border border-gray-800 rounded p-2">
                          <div className="text-gray-400">{String(h.at || '')}</div>
                          <div className="text-gray-300 mt-0.5">{String(h.user_message || '')}</div>
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
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-sm text-white shadow-lg animate-fade-in z-50">
          {alertMsg}
        </div>
      )}
    </div>
  );
}