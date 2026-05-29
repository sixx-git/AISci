import { AlertTriangle, CheckCircle, Shield, BarChart3, BookOpen, AlertCircle } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ComplianceCheck } from '@/types';

interface QualityCheckCardProps {
  complianceCheck?: ComplianceCheck;
  className?: string;
}

export function QualityCheckCard({
  complianceCheck,
  className,
}: QualityCheckCardProps) {
  const cc = complianceCheck;
  const qc = (cc as Record<string, unknown> | undefined)?.report_quality_check as Record<string, unknown> | undefined;

  if (!qc || !qc.data) {
    return null;
  }

  const qcData = qc.data as Record<string, unknown>;
  const score = typeof qcData.score === 'number' ? qcData.score : 0;
  const missingFields = (Array.isArray(qcData.missing_fields) ? qcData.missing_fields : []) as string[];
  const warnings = (Array.isArray(qcData.warnings) ? qcData.warnings : []) as string[];
  const criticalIssues = (Array.isArray(qcData.critical_issues) ? qcData.critical_issues : []) as string[];
  const recommendations = (Array.isArray(qcData.recommendations) ? qcData.recommendations : []) as string[];
  const refsVerified = typeof qcData.references_verified === 'number' ? qcData.references_verified : 0;
  const hasRealPlots = !!qcData.has_real_data_plots;

  const scoreColor = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-amber-400' : 'text-red-400';
  const scoreBg = score >= 80 ? 'bg-green-500/10 border-green-500/20' : score >= 60 ? 'bg-amber-500/10 border-amber-500/20' : 'bg-red-500/10 border-red-500/20';
  const scoreLabel = score >= 80 ? '良好' : score >= 60 ? '待改进' : '不合格';

  return (
    <Card className={cn(className)}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">报告质量检查</h3>
          <p className="text-xs text-gray-500 mt-0.5">赛题规范 · 完整性 · 真实性</p>
        </div>
      </div>

      <div className={cn('p-3 rounded-lg border mb-3', scoreBg)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className={cn('w-5 h-5', scoreColor)} />
            <span className={cn('text-xl font-bold', scoreColor)}>{score}</span>
            <span className="text-xs text-gray-600">/ 100</span>
          </div>
          <span className={cn('text-xs font-semibold px-2 py-0.5 rounded', score >= 80 ? 'bg-green-500/20 text-green-400' : score >= 60 ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400')}>
            {scoreLabel}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="p-2.5 rounded-lg bg-gray-800/60 border border-gray-700/50">
          <div className="flex items-center gap-1.5 mb-1">
            <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px] text-gray-500">已验证引用</span>
          </div>
          <p className={cn('text-lg font-mono font-bold', refsVerified > 0 ? 'text-cyan-400' : 'text-red-400')}>
            {refsVerified}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-gray-800/60 border border-gray-700/50">
          <div className="flex items-center gap-1.5 mb-1">
            <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] text-gray-500">真实数据图表</span>
          </div>
          <p className={cn('text-lg font-mono font-bold', hasRealPlots ? 'text-emerald-400' : 'text-red-400')}>
            {hasRealPlots ? '是' : '否'}
          </p>
        </div>
      </div>

      {refsVerified === 0 && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-red-300">参考文献未验证</p>
              <p className="text-[11px] text-red-300/70 mt-0.5">
                参考文献未验证，不符合赛题要求。
              </p>
            </div>
          </div>
        </div>
      )}

      {!hasRealPlots && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-3">
          <div className="flex items-start gap-2">
            <BarChart3 className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-amber-300">缺少真实数据图表</p>
              <p className="text-[11px] text-amber-300/70 mt-0.5">
                当前报告缺少真实数据图表。
              </p>
            </div>
          </div>
        </div>
      )}

      {criticalIssues.length > 0 && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-red-300 mb-1">关键问题 ({criticalIssues.length})</p>
              <ul className="list-disc list-inside text-[11px] text-red-300/70 space-y-0.5">
                {criticalIssues.slice(0, 3).map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
                {criticalIssues.length > 3 && (
                  <li className="text-red-400/50">...及其他 {criticalIssues.length - 3} 个问题</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {missingFields.length > 0 && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-amber-300 mb-1">缺失字段 ({missingFields.length})</p>
              <p className="text-[11px] text-amber-300/70">
                {missingFields.join('、')}
              </p>
            </div>
          </div>
        </div>
      )}

      {warnings.length > 0 && criticalIssues.length === 0 && (
        <div className="p-3 rounded-lg bg-gray-800/60 border border-gray-700/50 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-gray-300 mb-1">警告 ({warnings.length})</p>
              <ul className="list-disc list-inside text-[11px] text-gray-400 space-y-0.5">
                {warnings.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-blue-300 mb-1">改进建议</p>
              <ul className="list-disc list-inside text-[11px] text-blue-300/70 space-y-0.5">
                {recommendations.slice(0, 3).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}