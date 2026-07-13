import { ExternalLink, AlertCircle, Database, CheckCircle2, Circle } from 'lucide-react';
import { Card } from '@/components/Card';
import { cn } from '@/lib/utils';
import type { ValidationDataGuidance, UploadRequirement } from '@/lib/validationDataGuidance';

const REQUIREMENT_STYLES: Record<UploadRequirement, { cls: string; icon: typeof AlertCircle }> = {
  required: { cls: 'text-danger-400 border-danger-400/40 bg-danger-400/10', icon: AlertCircle },
  optional: { cls: 'text-bp-yellow border-bp-yellow/40 bg-bp-yellow/10', icon: Circle },
  skip_ok: { cls: 'text-bp-muted border-bp-border bg-bp-panel/50', icon: CheckCircle2 },
};

interface ValidationDataGuidanceCardProps {
  guidance: ValidationDataGuidance;
  blockedReason?: string;
  className?: string;
}

export function ValidationDataGuidanceCard({
  guidance,
  blockedReason,
  className,
}: ValidationDataGuidanceCardProps) {
  const items = guidance.dataset_requirements ?? [];
  const mustCount = guidance.must_upload_count ?? items.filter((i) => i.upload_requirement === 'required').length;
  const optionalCount = guidance.optional_upload_count ?? items.filter((i) => i.upload_requirement === 'optional').length;

  return (
    <Card
      className={cn('border-danger-400/30 bg-danger-400/5', className)}
      title="数据不匹配 · 所需数据集指引"
      subtitle={
        blockedReason
          || guidance.summary
          || '当前数据无法完成假设验证，请按下方说明补充数据集'
      }
    >
      {guidance.discovery_notes && guidance.discovery_notes.length > 0 && (
        <div className="mb-4 p-3 rounded-lg bg-bp-base/60 border border-bp-border text-xs text-bp-muted space-y-1">
          {guidance.discovery_notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
          {guidance.search_query_used && (
            <p className="text-bp-muted">
              检索关键词：
              <span className="text-bp-text ml-1">{guidance.search_query_used}</span>
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4 text-xs">
        <span className="px-2 py-1 rounded-full border text-danger-400 border-danger-400/40 bg-danger-400/10">
          必须上传 {mustCount} 项
        </span>
        <span className="px-2 py-1 rounded-full border text-bp-yellow border-bp-yellow/40 bg-bp-yellow/10">
          可选 {optionalCount} 项
        </span>
        {(guidance.skip_ok_count ?? 0) > 0 && (
          <span className="px-2 py-1 rounded-full border text-bp-muted border-bp-border">
            可不上传 {guidance.skip_ok_count} 项（已上传探索数据）
          </span>
        )}
      </div>

      {(guidance.mismatch_reasons?.length || guidance.what_hypothesis_needs?.length) ? (
        <div className="mb-4 p-3 rounded-lg bg-bp-base/60 border border-bp-border space-y-2 text-sm">
          {guidance.mismatch_reasons && guidance.mismatch_reasons.length > 0 && (
            <div>
              <p className="text-xs text-bp-muted mb-1">不匹配原因</p>
              <ul className="list-disc list-inside text-bp-text space-y-0.5">
                {guidance.mismatch_reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
          {guidance.what_hypothesis_needs && guidance.what_hypothesis_needs.length > 0 && (
            <div>
              <p className="text-xs text-bp-muted mb-1">假设真正需要</p>
              <ul className="list-disc list-inside text-bp-text space-y-0.5">
                {guidance.what_hypothesis_needs.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
          {guidance.what_uploaded_can_do && guidance.what_uploaded_can_do.length > 0 && (
            <div>
              <p className="text-xs text-bp-muted mb-1">当前数据可做（非主验证）</p>
              <ul className="list-disc list-inside text-bp-muted space-y-0.5">
                {guidance.what_uploaded_can_do.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
        </div>
      ) : null}

      {guidance.required_columns && guidance.required_columns.length > 0 && (
        <div className="mb-4 text-xs">
          <span className="text-bp-muted">建议字段：</span>
          <span className="text-bp-text ml-1">{guidance.required_columns.slice(0, 12).join('、')}</span>
        </div>
      )}

      {items.length > 0 && (
        <div className="overflow-x-auto rounded-bp border border-bp-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bp-panel/80 text-left text-xs text-bp-muted">
                <th className="px-3 py-2.5 font-medium min-w-[10rem]">数据集</th>
                <th className="px-3 py-2.5 font-medium whitespace-nowrap">上传要求</th>
                <th className="px-3 py-2.5 font-medium whitespace-nowrap">来源</th>
                <th className="px-3 py-2.5 font-medium whitespace-nowrap">下载地址</th>
                <th className="px-3 py-2.5 font-medium min-w-[8rem]">说明</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const req = (item.upload_requirement || 'optional') as UploadRequirement;
                const style = REQUIREMENT_STYLES[req] || REQUIREMENT_STYLES.optional;
                const ReqIcon = style.icon;
                const url = (item.download_url || '').trim();
                const key = `${item.name}-${req}-${url}`;
                return (
                  <tr key={key} className="border-t border-bp-border/60">
                    <td className="px-3 py-3 align-top">
                      <div className="font-medium text-bp-text flex items-center gap-1.5">
                        <Database className="w-3.5 h-3.5 text-bp-muted shrink-0" />
                        {item.name || '未命名'}
                      </div>
                      {item.required_columns && item.required_columns.length > 0 && (
                        <p className="text-xs text-bp-muted mt-1">
                          字段：{item.required_columns.slice(0, 6).join('、')}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-3 align-top whitespace-nowrap">
                      <span className={cn('inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border', style.cls)}>
                        <ReqIcon className="w-3 h-3 shrink-0" />
                        {item.upload_requirement_label
                          || guidance.upload_requirement_legend?.[req]
                          || req}
                      </span>
                    </td>
                    <td className="px-3 py-3 align-top text-bp-muted text-xs whitespace-nowrap">
                      {item.source_platform || '—'}
                    </td>
                    <td className="px-3 py-3 align-top whitespace-nowrap">
                      {url ? (
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-bp-cyan hover:underline text-xs"
                        >
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          打开下载页
                        </a>
                      ) : (
                        <span className="text-bp-muted text-xs">请自行检索或见实验设计推荐</span>
                      )}
                    </td>
                    <td className="px-3 py-3 align-top text-xs text-bp-muted max-w-xs">
                      <span className="line-clamp-3" title={item.description}>
                        {item.description || '—'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {guidance.next_steps && guidance.next_steps.length > 0 && (
        <ol className="mt-4 text-xs text-bp-muted list-decimal list-inside space-y-1">
          {guidance.next_steps.map((step) => (
            <li key={step} className="text-bp-text">{step}</li>
          ))}
        </ol>
      )}
    </Card>
  );
}
