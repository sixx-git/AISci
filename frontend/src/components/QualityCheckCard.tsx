﻿﻿﻿import { AlertTriangle, CheckCircle, Shield, BarChart3, BookOpen, AlertCircle, FlaskConical, Loader2 } from 'lucide-react';
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

  if (!qc) {
    return (
      <Card className={cn(className)}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-bp-text">报告质量检查</h3>
            <p className="text-xs text-bp-muted mt-0.5">赛题规范 · 完整性 · 真实性</p>
          </div>
        </div>
        <div className="flex items-center justify-center py-8 text-bp-muted">
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          <span className="text-xs">报告生成完成后将显示质量检查结果</span>
        </div>
      </Card>
    );
  }

  if (!qc.data && !qc.error) {
    return (
      <Card className={cn(className)}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-bp-text">报告质量检查</h3>
            <p className="text-xs text-bp-muted mt-0.5">赛题规范 · 完整性 · 真实性</p>
          </div>
        </div>
        <div className="flex items-center justify-center py-8 text-bp-muted">
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          <span className="text-xs">暂无检测结果，等待数据...</span>
        </div>
      </Card>
    );
  }

  if (!qc.data) {
    return (
      <Card className={cn(className)}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-bp-text">报告质量检查</h3>
            <p className="text-xs text-bp-muted mt-0.5">赛题规范 · 完整性 · 真实性</p>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-bp-yellow/10 border border-bp-yellow/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-yellow">质量检查未完成</p>
              <p className="text-xs text-bp-yellow/70 mt-0.5">
                {String(qc.error || '未知错误')}
              </p>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  const qcData = qc.data as Record<string, unknown>;
  const score = typeof qcData.score === 'number' ? qcData.score : 0;
  const passed = !!qcData.passed;
  const missingFields = (Array.isArray(qcData.missing_fields) ? qcData.missing_fields : []) as string[];
  const warnings = (Array.isArray(qcData.warnings) ? qcData.warnings : []) as string[];
  const criticalIssues = (Array.isArray(qcData.critical_issues) ? qcData.critical_issues : []) as string[];
  const recommendations = (Array.isArray(qcData.recommendations) ? qcData.recommendations : []) as string[];
  const refsVerified = typeof qcData.references_verified === 'number' ? qcData.references_verified : 0;
  const hasRealPlots = !!qcData.has_real_data_plots;
  const hasActualOrSimulated = !!qcData.has_actual_or_simulated_results;

  const scoreColor = score >= 80 ? 'text-bp-green' : score >= 60 ? 'text-bp-yellow' : 'text-danger-400';
  const scoreBg = score >= 80 ? 'bg-bp-green/10 border-bp-green/20' : score >= 60 ? 'bg-bp-yellow/10 border-bp-yellow/20' : 'bg-danger-500/10 border-danger-500/20';
  const scoreLabel = score >= 80 ? '良好' : score >= 60 ? '待改进' : '不合格';

  return (
    <Card className={cn(className)}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-bp-text">报告质量检查</h3>
          <p className="text-xs text-bp-muted mt-0.5">赛题规范 · 完整性 · 真实性</p>
        </div>
      </div>

      <div className={cn('p-3 rounded-lg border mb-3', scoreBg)}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Shield className={cn('w-5 h-5', scoreColor)} />
            <span className={cn('text-xl font-bold', scoreColor)}>{score}</span>
            <span className="text-xs text-bp-muted">/ 100</span>
          </div>
          <span className={cn('text-xs font-semibold px-2 py-0.5 rounded', passed ? 'bg-bp-green/20 text-bp-green' : score >= 60 ? 'bg-bp-yellow/20 text-bp-yellow' : 'bg-danger-500/20 text-danger-400')}>
            {passed ? '✓ 合格' : scoreLabel}
          </span>
        </div>
        {!passed && score >= 60 && (
          <p className="text-xs text-bp-yellow/70">存在关键问题需整改后重新检查</p>
        )}
        {!passed && score < 60 && (
          <p className="text-xs text-danger-300/70">报告质量未达标，建议补充文献、数据或实验结果。</p>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="p-2.5 rounded-lg bg-bp-panel/60 border border-bp-border/50">
          <div className="flex items-center gap-1.5 mb-1">
            <BookOpen className="w-3.5 h-3.5 text-bp-cyan" />
            <span className="text-xs text-bp-muted">已验证引用</span>
          </div>
          <p className={cn('text-lg font-mono font-bold', refsVerified > 0 ? 'text-bp-cyan' : 'text-danger-400')}>
            {refsVerified}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-bp-panel/60 border border-bp-border/50">
          <div className="flex items-center gap-1.5 mb-1">
            <BarChart3 className="w-3.5 h-3.5 text-bp-green" />
            <span className="text-xs text-bp-muted">真实图表</span>
          </div>
          <p className={cn('text-sm font-mono font-bold', hasRealPlots ? 'text-bp-green' : 'text-danger-400')}>
            {hasRealPlots ? '是' : '否'}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-bp-panel/60 border border-bp-border/50">
          <div className="flex items-center gap-1.5 mb-1">
            <FlaskConical className="w-3.5 h-3.5 text-bp-purple" />
            <span className="text-xs text-bp-muted">实验结果</span>
          </div>
          <p className={cn('text-sm font-mono font-bold', hasActualOrSimulated ? 'text-bp-purple' : 'text-danger-400')}>
            {hasActualOrSimulated ? '是' : '否'}
          </p>
        </div>
      </div>

      {refsVerified === 0 && (
        <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-danger-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-danger-300">参考文献未验证</p>
              <p className="text-xs text-danger-300/70 mt-0.5">
                参考文献未验证，不符合赛题要求。
              </p>
            </div>
          </div>
        </div>
      )}

      {!hasRealPlots && (
        <div className="p-3 rounded-lg bg-bp-yellow/10 border border-bp-yellow/20 mb-3">
          <div className="flex items-start gap-2">
            <BarChart3 className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-yellow">缺少真实数据图表</p>
              <p className="text-xs text-bp-yellow/70 mt-0.5">
                当前报告缺少真实数据图表。
              </p>
            </div>
          </div>
        </div>
      )}

      {score < 60 && (
        <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-danger-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-danger-300">报告质量未达标</p>
              <p className="text-xs text-danger-300/70 mt-0.5">
                报告质量未达标，建议补充文献、数据或实验结果。
              </p>
            </div>
          </div>
        </div>
      )}

      {criticalIssues.length > 0 && (
        <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-danger-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-danger-300 mb-1">关键问题 ({criticalIssues.length})</p>
              <ul className="list-disc list-inside text-xs text-danger-300/70 space-y-0.5">
                {criticalIssues.slice(0, 4).map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
                {criticalIssues.length > 4 && (
                  <li className="text-danger-400/50">...及其他 {criticalIssues.length - 4} 个问题</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {missingFields.length > 0 && (
        <div className="p-3 rounded-lg bg-bp-yellow/10 border border-bp-yellow/20 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-yellow mb-1">缺失字段 ({missingFields.length})</p>
              <p className="text-xs text-bp-yellow/70">
                {missingFields.join('、')}
              </p>
            </div>
          </div>
        </div>
      )}

      {warnings.length > 0 && criticalIssues.length === 0 && (
        <div className="p-3 rounded-lg bg-bp-panel/60 border border-bp-border/50 mb-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-bp-muted shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-text mb-1">警告 ({warnings.length})</p>
              <ul className="list-disc list-inside text-xs text-bp-muted space-y-0.5">
                {warnings.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="p-3 rounded-lg bg-bp-cyan/10 border border-bp-cyan/20">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-bp-cyan mb-1">改进建议</p>
              <ul className="list-disc list-inside text-xs text-bp-cyan/70 space-y-0.5">
                {recommendations.slice(0, 4).map((r, i) => (
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