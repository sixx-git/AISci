const TIER_STYLES: Record<string, string> = {
  real_sandbox: 'bg-green-500/15 text-green-400 border-green-500/30',
  real_sandbox_docker: 'bg-green-500/15 text-green-400 border-green-500/30',
  runtime_local: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  flower: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  fate_compatible: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
  csv_real: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  csv_simulation: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  gate_blocked: 'bg-red-500/15 text-red-400 border-red-500/30',
  skipped: 'bg-gray-500/15 text-bp-muted border-gray-500/30',
  unknown: 'bg-gray-500/15 text-bp-muted border-gray-500/30',
};

interface ExecutionTierBadgeProps {
  executionTier?: string;
  executionTierLabel?: string;
  dataAuthenticity?: string;
  dataAuthenticityLabel?: string;
}

export function ExecutionTierBadge({
  executionTier,
  executionTierLabel,
  dataAuthenticity,
  dataAuthenticityLabel,
}: ExecutionTierBadgeProps) {
  if (!executionTier && !dataAuthenticity) return null;

  const tierStyle = TIER_STYLES[executionTier || 'unknown'] || TIER_STYLES.unknown;

  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {executionTier && (
        <span className={`text-[10px] px-2 py-1 rounded border ${tierStyle}`}>
          执行层级: {executionTierLabel || executionTier}
        </span>
      )}
      {dataAuthenticity && (
        <span className="text-[10px] px-2 py-1 rounded border border-bp-border bg-bp-base text-bp-text">
          数据来源: {dataAuthenticityLabel || dataAuthenticity}
        </span>
      )}
    </div>
  );
}
