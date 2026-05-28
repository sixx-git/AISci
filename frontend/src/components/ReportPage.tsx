import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, Loader2, XCircle, AlertTriangle, BookOpen, ExternalLink } from 'lucide-react';
import { Card } from './Card';
import { MarkdownPreview } from './MarkdownPreview';
import { ReportChecklist } from './ReportChecklist';
import { EvidenceChainQualityCard } from './EvidenceChainQualityCard';
import { ExportActions } from './ExportActions';
import type { ExportType } from './ExportActions';
import type { ReportData } from '@/types';
import { MOCK_REPORT, MOCK_REPORT_SECTIONS } from '@/data/mockData';
import { reportService } from '@/services/reportService';
import env from '@/config/env';

interface ReportPageProps {
  projectId: string;
  compact?: boolean;
  /** 文献库中的真实文献总数（从父级 stats 传入） */
  literatureCount?: number;
  revalidateKey?: number;
  latestRunId?: string | null;
}

export function ReportPage({
  projectId,
  compact: _compact = false,
  literatureCount,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: ReportPageProps) {
  const navigate = useNavigate();
  const [report, setReport] = useState<ReportData | null>(env.USE_MOCK ? MOCK_REPORT : null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 2500);
  }, []);

  // 非 Mock 模式下加载最新报告
  useEffect(() => {
    if (env.USE_MOCK || !projectId) return;

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

    // 导出 Markdown / PDF
    if (!report?.id) {
      showAlert('暂无报告可导出');
      return;
    }

    const fileType = action === 'markdown' ? 'md' : 'pdf';
    try {
      const blob = await reportService.download(report.id, fileType);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileType === 'md' ? '科学假设与研究计划.md' : '科学假设与研究计划.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showAlert(`${action === 'markdown' ? 'Markdown' : 'PDF'} 导出成功`);
    } catch {
      showAlert('导出失败，请重试');
    }
  }, [report, showAlert]);

  // 加载中状态
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

  // 错误状态
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

  // 无报告状态
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

  const sections = report.sections || (env.USE_MOCK ? MOCK_REPORT_SECTIONS : []);
  const complianceCheck = report.complianceCheck;
  const hasNoRefs = complianceCheck && complianceCheck.references_verified === 0;
  const pdfFailed = report.pdfSuccess === false;

  return (
    <div className="max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
        <p className="text-gray-400 text-sm">自动生成符合挑战杯 XH-202619 规范的科学假设与研究计划</p>
      </div>

      {/* ── 警告横幅区 ── */}
      <div className="space-y-3 mb-6">
        {/* References 为空 → 红色 warning */}
        {hasNoRefs && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/25">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-300 mb-1">
                当前报告缺少真实文献引用
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

        {/* PDF 导出失败 → 黄色 warning */}
        {pdfFailed && !hasNoRefs && (
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
            {/* 跳转文献库 */}
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
        </div>

        {/* 右侧：比赛规范检查 + 证据链质量 + 操作 */}
        <div className="lg:col-span-1">
          <div className="sticky top-6 space-y-4">
            <ReportChecklist sections={sections} complianceCheck={complianceCheck} />
            <EvidenceChainQualityCard
              complianceCheck={complianceCheck}
              literatureCount={literatureCount}
            />
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