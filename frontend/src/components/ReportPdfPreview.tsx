import { useEffect, useState } from 'react';
import { FileText, AlertTriangle, Download } from 'lucide-react';
import { LoadingState } from '@/components/workspace/LoadingState';
import { MarkdownPreview } from './MarkdownPreview';
import { reportService } from '@/services/reportService';
import { getReportDisplayTitle } from '@/lib/reportExport';

interface ReportPdfPreviewProps {
  reportId: string;
  markdownContent: string;
  pdfSuccess?: boolean;
}

const PREVIEW_HEIGHT = 'calc(100vh - 320px)';

/** 报告 PDF 内嵌预览；无 PDF 时回退 Markdown */
export function ReportPdfPreview({
  reportId,
  markdownContent,
  pdfSuccess,
}: ReportPdfPreviewProps) {
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    if (!reportId || pdfSuccess === false) {
      setUseFallback(true);
      setLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      setUseFallback(false);
      try {
        const blob = await reportService.download(reportId, 'pdf');
        if (cancelled) return;
        const objectUrl = URL.createObjectURL(blob);
        setPdfObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return objectUrl;
        });
      } catch {
        if (!cancelled) setUseFallback(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      setPdfObjectUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [reportId, pdfSuccess]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ minHeight: PREVIEW_HEIGHT }}
      >
        <LoadingState message="正在加载 PDF 预览…" />
      </div>
    );
  }

  if (useFallback || !pdfObjectUrl) {
    return (
      <div className="space-y-3">
        {pdfSuccess === false && (
          <div className="flex items-start gap-2 p-3 rounded-bp bg-bp-yellow/10 border border-bp-yellow/25 text-xs text-bp-yellow">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>PDF 未生成或加载失败，以下为 Markdown 预览。</span>
          </div>
        )}
        <div
          id="report-markdown-preview"
          className="bg-bp-base/80 rounded-bp border border-bp-border p-6 overflow-auto"
          style={{ maxHeight: PREVIEW_HEIGHT }}
        >
          <MarkdownPreview content={markdownContent} />
        </div>
      </div>
    );
  }

  return (
    <div
      id="report-pdf-preview"
      className="rounded-bp border border-bp-border overflow-hidden bg-[#525659]"
    >
      <iframe
        src={`${pdfObjectUrl}#toolbar=1&navpanes=0&view=FitH`}
        className="w-full border-0"
        style={{ height: PREVIEW_HEIGHT }}
        title="报告 PDF 预览"
      />
    </div>
  );
}

export function ReportPreviewHeader({
  mode,
  title,
  onDownloadPdf,
  pdfAvailable = true,
}: {
  mode: 'pdf' | 'markdown';
  title?: string;
  onDownloadPdf?: () => void;
  pdfAvailable?: boolean;
}) {
  const displayTitle = getReportDisplayTitle(title);
  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <div className="flex items-center gap-2 min-w-0">
        <FileText className="w-4 h-4 text-bp-cyan shrink-0" />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-bp-text">报告预览</h3>
          <p className="text-xs text-bp-muted truncate" title={displayTitle}>
            {mode === 'pdf' ? 'PDF 格式' : 'Markdown 格式'} · {displayTitle}
          </p>
        </div>
      </div>
      {mode === 'pdf' && pdfAvailable && onDownloadPdf && (
        <button
          type="button"
          onClick={onDownloadPdf}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-bp-border bg-bp-panel text-bp-text hover:bg-bp-base transition-colors"
          title={`下载：${displayTitle}.pdf`}
        >
          <Download className="w-3.5 h-3.5" />
          下载 PDF
        </button>
      )}
    </div>
  );
}
