import { Layers, Link2, CheckCircle, AlertTriangle } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ComplianceCheck } from '@/types';

interface EvidenceChainQualityCardProps {
  complianceCheck?: ComplianceCheck;
  /** 文献库中的真实文献总数 */
  literatureCount?: number;
  className?: string;
}

export function EvidenceChainQualityCard({
  complianceCheck,
  literatureCount,
  className,
}: EvidenceChainQualityCardProps) {
  const cc = complianceCheck;
  const hasSuspicious = (cc?.references_suspicious ?? 0) > 0;
  const hasNoRefs = (cc?.references_verified ?? 0) === 0;

  const metrics = [
    {
      label: '文献数量',
      value: literatureCount ?? '—',
      icon: Layers,
      color: 'text-bp-cyan',
    },
    {
      label: 'Evidence 事实',
      value: cc?.evidence_fact_count ?? '—',
      icon: Link2,
      color: 'text-bp-purple',
    },
    {
      label: '有证据假设',
      value: cc?.hypothesis_with_evidence_count ?? '—',
      icon: CheckCircle,
      color: 'text-bp-green',
    },
    {
      label: '已验证引用',
      value: cc?.references_verified ?? '—',
      icon: CheckCircle,
      color: 'text-bp-cyan',
    },
  ];

  return (
    <Card className={cn(className)}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-bp-text">证据链质量</h3>
          <p className="text-xs text-bp-muted mt-0.5">文献事实 · 假设支撑 · 引用真实性</p>
        </div>
      </div>

      {/* 四宫格指标 */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div
              key={m.label}
              className="p-2.5 rounded-lg bg-bp-panel/60 border border-bp-border/50"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <Icon className={cn('w-3.5 h-3.5', m.color)} />
                <span className="text-[10px] text-bp-muted">{m.label}</span>
              </div>
              <p className={cn('text-lg font-mono font-bold', m.color)}>{m.value}</p>
            </div>
          );
        })}
      </div>

      {/* 虚构引用风险 */}
      {hasNoRefs && (
        <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-danger-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-danger-300">虚构引用风险</p>
              <p className="text-[11px] text-danger-300/70 mt-0.5">
                当前报告没有任何经过文献库验证的真实引用。所有引用均由 LLM 编造，不符合比赛规范。
              </p>
            </div>
          </div>
        </div>
      )}

      {!hasNoRefs && hasSuspicious && (
        <div className="p-3 rounded-lg bg-bp-yellow/10 border border-bp-yellow/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-yellow">部分引用存疑</p>
              <p className="text-[11px] text-bp-yellow/70 mt-0.5">
                发现 {cc?.references_suspicious} 条引用未在文献库中找到匹配，建议核实后补充。
              </p>
            </div>
          </div>
        </div>
      )}

      {!hasNoRefs && !hasSuspicious && (
        <div className="p-3 rounded-lg bg-bp-green/10 border border-bp-green/20">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-bp-green shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-green">引用验证通过</p>
              <p className="text-[11px] text-bp-green/70 mt-0.5">
                全部 {cc?.references_verified} 条引用均可追溯至文献库中的真实文献。
              </p>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}