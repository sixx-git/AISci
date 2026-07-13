import { AlertTriangle, CheckCircle2, Database, ImageIcon, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  extractValidationDataGuidance,
  formatValidationBlockedSummary,
} from '@/lib/validationDataGuidance';

interface ValidationResultCardProps {
  outputData: Record<string, unknown>;
  className?: string;
}

type ValidationStatus = 'blocked' | 'completed' | 'failed' | 'need_data' | 'skipped' | 'unknown';

function resolveStatus(data: Record<string, unknown>): ValidationStatus {
  const raw = data.validation_status;
  if (raw === 'blocked' || data.validation_blocked === true) return 'blocked';
  if (raw === 'completed') return 'completed';
  if (raw === 'failed') return 'failed';
  if (raw === 'need_data') return 'need_data';
  if (raw === 'skipped') return 'skipped';
  return 'unknown';
}

const STATUS_META: Record<ValidationStatus, { label: string; cls: string; icon: typeof CheckCircle2 }> = {
  blocked: { label: '待补充数据', cls: 'text-danger-400 bg-danger-400/10 border-danger-400/30', icon: Database },
  need_data: { label: '尚无数据', cls: 'text-bp-yellow bg-bp-yellow/10 border-bp-yellow/30', icon: Database },
  completed: { label: '验证成功', cls: 'text-bp-green bg-bp-green/10 border-bp-green/30', icon: CheckCircle2 },
  failed: { label: '验证失败', cls: 'text-danger-400 bg-danger-400/10 border-danger-400/30', icon: XCircle },
  skipped: { label: '未执行', cls: 'text-bp-muted bg-bp-panel border-bp-border', icon: AlertTriangle },
  unknown: { label: '状态未知', cls: 'text-bp-muted bg-bp-panel border-bp-border', icon: AlertTriangle },
};

function extractPrimaryMetric(data: Record<string, unknown>): string | null {
  const arts = data.artifacts as Record<string, unknown> | undefined;
  const metrics = (arts?.metrics ?? (data.sandbox_execution as Record<string, unknown> | undefined)?.metrics) as Record<string, unknown> | undefined;
  if (!metrics || typeof metrics !== 'object') return null;
  const primary = metrics.primary_metric ?? metrics.primary_metric_value;
  if (primary != null) return String(primary);
  const keys = ['f1_score', 'accuracy', 'rmse', 'auc', 'proposed_score'];
  for (const k of keys) {
    if (metrics[k] != null) return `${k}=${metrics[k]}`;
  }
  return null;
}

function extractPlotPreviews(data: Record<string, unknown>): Array<{ title: string; url?: string }> {
  const arts = data.artifacts as Record<string, unknown> | undefined;
  const plots = (arts?.plots ?? []) as unknown[];
  return plots
    .filter((p): p is Record<string, unknown> => !!p && typeof p === 'object')
    .slice(0, 4)
    .map((p, i) => ({
      title: String(p.title || p.plot_id || `图表 ${i + 1}`),
      url: typeof p.url === 'string' ? p.url : typeof p.file_path === 'string' ? p.file_path : undefined,
    }));
}

export function ValidationResultCard({ outputData, className }: ValidationResultCardProps) {
  const status = resolveStatus(outputData);
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  const hypothesis = typeof outputData.hypothesis === 'string' ? outputData.hypothesis : '';
  const blockedSummary = formatValidationBlockedSummary(outputData);
  const blockedReason = typeof outputData.validation_blocked_reason === 'string'
    ? outputData.validation_blocked_reason
    : '';
  const primaryMetric = extractPrimaryMetric(outputData);
  const plots = extractPlotPreviews(outputData);
  const warnings = Array.isArray(outputData.warnings)
    ? outputData.warnings.filter((w): w is string => typeof w === 'string').slice(0, 5)
    : [];
  const sandbox = outputData.sandbox_execution as Record<string, unknown> | undefined;
  const stderr = typeof sandbox?.stderr === 'string' ? sandbox.stderr.slice(0, 500) : '';

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-start gap-3">
        <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium', meta.cls)}>
          <Icon className="w-3.5 h-3.5" />
          {meta.label}
        </span>
        {typeof outputData.script_source === 'string' && (
          <span className="text-xs text-bp-muted font-mono">
            脚本来源: {outputData.script_source}
          </span>
        )}
      </div>

      {hypothesis ? (
        <div className="text-sm text-bp-text">
          <span className="text-bp-muted text-xs">假设 · </span>
          {hypothesis}
        </div>
      ) : (
        <p className="text-xs text-bp-yellow">未记录假设文本（请检查上游假设评审是否完成）</p>
      )}

      {(status === 'blocked' || status === 'need_data') && (blockedSummary || blockedReason) && (
        <div className="p-3 rounded-bp border border-danger-400/30 bg-danger-400/5 text-sm text-bp-text">
          {blockedSummary || blockedReason}
        </div>
      )}

      {status === 'completed' && (
        <div className="space-y-2">
          {primaryMetric && (
            <p className="text-sm text-bp-text">
              <span className="text-bp-muted text-xs">主指标 · </span>
              {primaryMetric}
            </p>
          )}
          {plots.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {plots.map((p) => (
                <div
                  key={p.title}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-bp border border-bp-border bg-bp-base/60 text-xs text-bp-muted"
                >
                  <ImageIcon className="w-3.5 h-3.5" />
                  {p.title}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {status === 'failed' && (
        <div className="space-y-2">
          {blockedReason && (
            <p className="text-sm text-danger-300">{blockedReason}</p>
          )}
          {stderr && (
            <pre className="text-xs text-bp-muted font-mono whitespace-pre-wrap bg-bp-base/60 border border-bp-border rounded-bp p-3 max-h-32 overflow-y-auto">
              {stderr}
            </pre>
          )}
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="text-xs text-bp-muted space-y-1 list-disc list-inside">
          {warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}

      {outputData.has_uploaded_data === 1 && outputData.has_real_data === 0 && status === 'blocked' && (
        <p className="text-xs text-bp-muted">
          已检测到上传文件，但与当前假设验证目标不匹配，因此未执行沙箱出图。
        </p>
      )}
    </div>
  );
}

export function hasValidationResultSummary(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return Boolean(
    d.validation_status
    || d.validation_blocked
    || d.hypothesis
    || d.sandbox_execution
    || extractValidationDataGuidance(data),
  );
}
