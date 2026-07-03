const TIER_STYLES: Record<string, string> = {
  real_sandbox: 'bg-bp-green/15 text-bp-green border-bp-green/30',
  real_sandbox_docker: 'bg-bp-green/15 text-bp-green border-bp-green/30',
  runtime_local: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30',
  flower: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30',
  fate_compatible: 'bg-bp-purple/15 text-bp-purple border-bp-purple/30',
  csv_real: 'bg-bp-green/15 text-bp-green border-bp-green/30',
  csv_simulation: 'bg-bp-yellow/15 text-bp-yellow border-bp-yellow/30',
  gate_blocked: 'bg-danger-500/15 text-danger-400 border-danger-500/30',
  skipped: 'bg-bp-panel text-bp-muted border-bp-border',
  unknown: 'bg-bp-panel text-bp-muted border-bp-border',
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
        <span className={`text-xs px-2 py-1 rounded border ${tierStyle}`}>
          执行层级: {executionTierLabel || executionTier}
        </span>
      )}
      {dataAuthenticity && (
        <span className="text-xs px-2 py-1 rounded border border-bp-border bg-bp-base text-bp-text">
          数据来源: {dataAuthenticityLabel || dataAuthenticity}
        </span>
      )}
    </div>
  );
}
