import { useEffect, useState } from 'react';
import { FileText, AlertTriangle } from 'lucide-react';
import { LoadingState } from '@/components/workspace/LoadingState';
import { MarkdownPreview } from './MarkdownPreview';
import { reportService } from '@/services/reportService';

interface ReportPdfPreviewProps {
  reportId: string;
  markdownContent: string;
  pdfSuccess?: boolean;
}

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

    let objectUrl: string | null = null;
    let cancelled = false;

    (async () => {
      setLoading(true);
      setUseFallback(false);
      try {
        const blob = await reportService.download(reportId, 'pdf');
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfObjectUrl(objectUrl);
      } catch {
        if (!cancelled) setUseFallback(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [reportId, pdfSuccess]);

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-320px)] flex items-center justify-center">
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
          className="bg-bp-base/80 rounded-bp border border-bp-border p-6 overflow-auto max-h-[calc(100vh-320px)]"
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
        className="w-full h-[calc(100vh-320px)] border-0"
        title="报告 PDF 预览"
      />
    </div>
  );
}

export function ReportPreviewHeader({ mode }: { mode: 'pdf' | 'markdown' }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <FileText className="w-4 h-4 text-bp-cyan" />
      <div>
        <h3 className="text-sm font-semibold text-bp-text">报告预览</h3>
        <p className="text-xs text-bp-muted">
          {mode === 'pdf' ? 'PDF 格式' : 'Markdown 格式'} · 科学假设与研究计划
        </p>
      </div>
    </div>
  );
}
