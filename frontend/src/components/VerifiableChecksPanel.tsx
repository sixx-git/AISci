import { ShieldCheck, CheckCircle2, XCircle } from 'lucide-react';
import type { VerifiableCheck } from '@/types';

interface VerifiableChecksPanelProps {
  checks?: VerifiableCheck[] | null;
  passed?: boolean | null;
  spec?: { claim?: string; primary_metric?: string; falsification_criteria?: string } | null;
}

export function VerifiableChecksPanel({ checks, passed, spec }: VerifiableChecksPanelProps) {
  if (!checks?.length && !spec) return null;

  return (
    <div className="mb-4 p-4 rounded-bp border border-bp-green/20 bg-bp-green/5">
      <h3 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-bp-green" />
        可验证 spec 对照
        {passed != null && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded-bp ${passed ? 'bg-bp-green/15 text-bp-green' : 'bg-danger-500/15 text-danger-400'}`}>
            {passed ? '通过' : '未通过'}
          </span>
        )}
      </h3>
      {spec?.claim && <p className="text-xs text-bp-muted mb-2 line-clamp-2">{spec.claim}</p>}
      <ul className="space-y-1.5">
        {(checks || []).map((c) => (
          <li key={c.check_id} className="flex items-start gap-2 text-[11px]">
            {c.passed ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-bp-green shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-3.5 h-3.5 text-danger-400 shrink-0 mt-0.5" />
            )}
            <div>
              <span className="text-bp-text">{c.description || c.check_id}</span>
              {c.actual && (
                <span className="text-bp-muted ml-1">· 实际: {c.actual}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
