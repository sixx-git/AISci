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
    <div className="mb-4 p-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
      <h3 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-emerald-400" />
        可验证 spec 对照
        {passed != null && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${passed ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
            {passed ? '通过' : '未通过'}
          </span>
        )}
      </h3>
      {spec?.claim && <p className="text-xs text-gray-400 mb-2 line-clamp-2">{spec.claim}</p>}
      <ul className="space-y-1.5">
        {(checks || []).map((c) => (
          <li key={c.check_id} className="flex items-start gap-2 text-[11px]">
            {c.passed ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
            )}
            <div>
              <span className="text-gray-300">{c.description || c.check_id}</span>
              {c.actual && (
                <span className="text-gray-500 ml-1">· 实际: {c.actual}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
