import { useEffect, useState } from 'react';
import { FileText, AlertTriangle, Download, RefreshCw } from 'lucide-react';
import { LoadingState } from '@/components/workspace/LoadingState';
import { reportService } from '@/services/reportService';
import { getReportDisplayTitle } from '@/lib/reportExport';

interface ReportPdfPreviewProps {
  reportId: string;
  /** PDF 重新生成完成后递增，用于刷新 iframe */
  refreshKey?: number;
  onRegeneratePdf?: () => void | Promise<void>;
  regenerating?: boolean;
}

/** 约 A4 一页高度（297mm @ 96dpi ≈ 1123px），便于单页 PDF 预览 */
const PREVIEW_HEIGHT = 'max(1123px, calc(100vh - 200px))';

/** 报告预览：仅 LaTeX 模板 PDF */
export function ReportPdfPreview({
  reportId,
  refreshKey = 0,
  onRegeneratePdf,
  regenerating = false,
}: ReportPdfPreviewProps) {
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pdfLoadFailed, setPdfLoadFailed] = useState(false);

  useEffect(() => {
    if (!reportId) {
      setPdfObjectUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      setLoading(false);
      setPdfLoadFailed(false);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      setPdfLoadFailed(false);
      try {
        const blob = await reportService.download(reportId, 'pdf');
        if (cancelled) return;
        const objectUrl = URL.createObjectURL(blob);
        setPdfObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return objectUrl;
        });
      } catch {
        if (!cancelled) setPdfLoadFailed(true);
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
  }, [reportId, refreshKey]);

  if (loading || regenerating) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ minHeight: PREVIEW_HEIGHT }}
      >
        <LoadingState message={regenerating ? '正在生成 LaTeX PDF…' : '正在加载 PDF 预览…'} />
      </div>
    );
  }

  if (pdfObjectUrl && !pdfLoadFailed) {
    return (
      <div
        id="report-pdf-preview"
        className="rounded-bp border border-bp-border overflow-hidden bg-[#525659]"
      >
        <iframe
          src={`${pdfObjectUrl}#toolbar=1&navpanes=0&view=FitH`}
          className="w-full border-0"
          style={{ height: PREVIEW_HEIGHT }}
          title="LaTeX 模板报告 PDF 预览"
        />
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center justify-center gap-4 p-8 rounded-bp border border-bp-border bg-bp-base/40 text-center"
      style={{ minHeight: PREVIEW_HEIGHT }}
    >
      <AlertTriangle className="w-10 h-10 text-bp-yellow" />
      <div className="space-y-1 max-w-md">
        <p className="text-sm font-semibold text-bp-text">PDF 尚未生成或加载失败</p>
        <p className="text-xs text-bp-muted leading-relaxed">
          报告将使用 LaTeX 模板编译为 PDF。请重新生成 PDF 后在下方预览。
        </p>
      </div>
      {onRegeneratePdf && (
        <button
          type="button"
          onClick={() => void onRegeneratePdf()}
          disabled={regenerating}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-bp-cyan/40 bg-bp-cyan/10 text-bp-cyan hover:bg-bp-cyan/20 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${regenerating ? 'animate-spin' : ''}`} />
          重新生成 PDF
        </button>
      )}
    </div>
  );
}

export function ReportPreviewHeader({
  title,
  onDownloadPdf,
  onRegeneratePdf,
  regenerating = false,
}: {
  title?: string;
  onDownloadPdf?: () => void;
  onRegeneratePdf?: () => void | Promise<void>;
  regenerating?: boolean;
}) {
  const displayTitle = getReportDisplayTitle(title);

  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <div className="flex items-center gap-2 min-w-0">
        <FileText className="w-4 h-4 text-bp-cyan shrink-0" />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-bp-text">报告预览</h3>
          <p className="text-xs text-bp-muted truncate" title={displayTitle}>
            LaTeX 模板 · PDF · {displayTitle}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onRegeneratePdf && (
          <button
            type="button"
            onClick={() => void onRegeneratePdf()}
            disabled={regenerating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-bp-border bg-bp-panel text-bp-text hover:bg-bp-base transition-colors disabled:opacity-50"
            title="重新编译 LaTeX 并生成 PDF"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? 'animate-spin' : ''}`} />
            重新生成
          </button>
        )}
        {onDownloadPdf && (
          <button
            type="button"
            onClick={onDownloadPdf}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-bp-border bg-bp-panel text-bp-text hover:bg-bp-base transition-colors"
            title={`下载：${displayTitle}.pdf`}
          >
            <Download className="w-3.5 h-3.5" />
            下载 PDF
          </button>
        )}
      </div>
    </div>
  );
}
