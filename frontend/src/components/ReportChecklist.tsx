import { CheckCircle, AlertTriangle, XCircle, Shield } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import { countRealReferences } from '@/lib/reportCompliance';
import type { ComplianceCheck, ReportSection } from '@/types';

interface ReportChecklistProps {
  sections: ReportSection[];
  complianceCheck?: ComplianceCheck;
  className?: string;
  warnings?: string[];
  referencesRaw?: string;
}

const statusConfig: Record<'completed' | 'missing', { icon: typeof CheckCircle; label: string; className: string }> = {
  completed:  { icon: CheckCircle,  label: '已完成',  className: 'text-bp-green bg-bp-green/10 border-bp-green/20' },
  missing:    { icon: XCircle,      label: '缺失',    className: 'text-danger-400 bg-danger-500/10 border-danger-500/20' },
};

function sectionDisplayStatus(status: ReportSection['status']): 'completed' | 'missing' {
  if (status === 'missing') return 'missing';
  return 'completed';
}

export function ReportChecklist({ sections, complianceCheck, className, warnings, referencesRaw }: ReportChecklistProps) {
  const completedCount = sections.filter(
    (s) => s.status === 'completed' || s.status === 'human_review',
  ).length;
  const missingCount = sections.filter(s => s.status === 'missing').length;
  const totalItems = complianceCheck?.total_items ?? sections.length;
  const ratio = totalItems > 0 ? completedCount / totalItems : 0;

  const cc = complianceCheck;
  const realReferenceCount = countRealReferences(referencesRaw);
  const refsMissing = (cc?.references_verified ?? 0) === 0 && realReferenceCount === 0;
  const refsPendingReview = (cc?.references_verified ?? 0) === 0 && realReferenceCount > 0;

  return (
    <div className={cn('space-y-4', className)}>
      {/* 比赛规范完整性检查卡片 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-bp-text">比赛规范完整性检查</h3>
            <p className="text-xs text-bp-muted mt-0.5">
              挑战杯 XH-202619 · {completedCount}/{totalItems} 项完成
            </p>
          </div>
          {/* 进度环 */}
          <div className="relative w-12 h-12">
            <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
              <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
                className="text-bp-panel" strokeWidth="5" />
              <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
                className={cn(
                  ratio >= 1 ? 'text-bp-green' :
                  ratio >= 0.5 ? 'text-bp-yellow' : 'text-danger-400',
                )}
                strokeWidth="5"
                strokeLinecap="round"
                strokeDasharray={`${ratio * 125.66} 125.66`}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-xs font-mono font-bold text-bp-text">
              {Math.round(ratio * 100)}%
            </span>
          </div>
        </div>

        {/* 汇总统计 */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="text-center p-2 rounded-lg bg-bp-green/5 border border-bp-green/10">
            <p className="text-lg font-mono font-bold text-bp-green">{completedCount}</p>
            <p className="text-xs text-bp-muted">已完成</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-danger-500/5 border border-danger-500/10">
            <p className="text-lg font-mono font-bold text-danger-400">{missingCount}</p>
            <p className="text-xs text-bp-muted">缺失</p>
          </div>
        </div>

        {/* 赛题专属指标 */}
        {cc && (
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-2 rounded-lg bg-bp-panel/60 border border-bp-border/50">
              <p className="text-xs text-bp-muted mb-0.5">Evidence 事实数</p>
              <p className="text-sm font-mono font-bold text-bp-purple">
                {cc.evidence_fact_count}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-bp-panel/60 border border-bp-border/50">
              <p className="text-xs text-bp-muted mb-0.5">有证据假设数</p>
              <p className="text-sm font-mono font-bold text-bp-green">
                {cc.hypothesis_with_evidence_count}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-bp-panel/60 border border-bp-border/50">
              <p className="text-xs text-bp-muted mb-0.5">已验证引用</p>
              <p className="text-sm font-mono font-bold text-bp-cyan">
                {cc.references_verified}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-bp-panel/60 border border-bp-border/50">
              <p className="text-xs text-bp-muted mb-0.5">含实际/模拟结果</p>
              <p className="text-sm font-mono font-bold">
                {cc.has_actual_or_simulated_result
                  ? <span className="text-bp-green">有</span>
                  : <span className="text-danger-400">无</span>}
              </p>
            </div>
          </div>
        )}

        {/* Skill 评估指标 */}
        {cc && (cc.novelty_score != null || cc.experiment_sanity_check) && (
          <div className="mb-3 p-3 rounded-lg bg-bp-purple/5 border border-bp-purple/15">
            <p className="text-xs text-bp-purple font-semibold mb-2 uppercase tracking-wide">
              Skill 评估
            </p>
            {cc.novelty_score != null && (
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-bp-muted">新颖性评分</span>
                <span className={cn(
                  'text-xs font-mono font-bold',
                  cc.novelty_score >= 7 ? 'text-bp-green' :
                  cc.novelty_score >= 4 ? 'text-bp-yellow' : 'text-danger-400',
                )}>
                  {cc.novelty_score}/10
                </span>
              </div>
            )}
            {cc.experiment_sanity_check && (
              <div className="space-y-1 mt-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-bp-muted">实验可执行性</span>
                  <span className={cn(
                    'text-xs font-medium',
                    cc.experiment_sanity_check.executable
                      ? 'text-bp-green' : 'text-danger-400',
                  )}>
                    {cc.experiment_sanity_check.executable ? '可执行' : '存在问题'}
                  </span>
                </div>
                {cc.experiment_sanity_check.missing_items?.length > 0 && (
                  <p className="text-xs text-danger-400/70 leading-relaxed">
                    缺失: {cc.experiment_sanity_check.missing_items.join(', ')}
                  </p>
                )}
                {cc.experiment_sanity_check.recommendations?.length > 0 && (
                  <p className="text-xs text-bp-purple/70 leading-relaxed">
                    建议: {cc.experiment_sanity_check.recommendations.slice(0, 2).join('; ')}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* 章节字段检查列表 */}
        <div className="space-y-1.5">
          {sections.map((s) => {
            const displayStatus = sectionDisplayStatus(s.status);
            const cfg = statusConfig[displayStatus];
            const Icon = cfg.icon;
            return (
              <div
                key={s.key}
                className="flex flex-col gap-1 py-2 border-b border-bp-border/50 last:border-0"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-bp-text">{s.label}</span>
                  <span className={cn(
                    'text-xs px-2 py-0.5 rounded-full border font-medium flex items-center gap-1',
                    cfg.className,
                  )}>
                    <Icon className="w-3 h-3" />
                    {cfg.label}
                  </span>
                </div>
                {s.note && (
                  <p className="text-xs text-bp-muted leading-relaxed ml-0">{s.note}</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* References 合规声明卡片 */}
      <Card className={cn(
        'border',
        refsMissing
          ? 'bg-danger-500/[0.04] border-danger-500/20'
          : 'bg-bp-yellow/[0.03] border-bp-yellow/10',
      )}>
        <div className="flex items-start gap-2.5">
          <div className={cn(
            'w-8 h-8 rounded-lg border flex items-center justify-center shrink-0',
            refsMissing
              ? 'bg-danger-500/10 border-danger-500/20'
              : 'bg-bp-yellow/10 border-bp-yellow/20',
          )}>
            <Shield className={cn(
              'w-4 h-4',
              refsMissing ? 'text-danger-400' : 'text-bp-yellow',
            )} />
          </div>
          <div>
            <h4 className={cn(
              'text-xs font-semibold',
              refsMissing ? 'text-danger-300' : 'text-bp-yellow',
            )}>
              References 合规声明
            </h4>
            {refsMissing ? (
              <p className="text-xs text-danger-300/80 mt-1 leading-relaxed">
                当前报告缺少真实文献引用，请先上传 PDF 或导入 arXiv 文献。
              </p>
            ) : refsPendingReview ? (
              <p className="text-xs text-bp-yellow/80 mt-1 leading-relaxed">
                报告正文含 {realReferenceCount} 条参考文献，正在与文献库核对；若数值未更新请刷新页面或重新生成报告。
              </p>
            ) : (
              <p className="text-xs text-bp-yellow/70 mt-1 leading-relaxed">
                参考文献仅来自文献库和证据链，禁止虚构引用。
              </p>
            )}
            {cc && (
              <div className="mt-2 flex items-center gap-3 text-xs">
                <span className={(cc.references_verified ?? 0) > 0 ? 'text-bp-green' : refsPendingReview ? 'text-bp-yellow' : 'text-danger-400'}>
                  已验证 {cc.references_verified ?? 0} 条
                  {refsPendingReview && realReferenceCount > 0 ? `（正文 ${realReferenceCount} 条待核对）` : ''}
                </span>
                {cc.references_suspicious > 0 && (
                  <span className="text-danger-400">
                    疑似虚构 {cc.references_suspicious} 条
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 12 字段合规警告 */}
      {warnings && warnings.length > 0 && (
        <Card className="bg-bp-yellow/[0.03] border border-bp-yellow/10">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-semibold text-bp-yellow mb-1.5">
                赛题合规提示
              </h4>
              <ul className="space-y-1">
                {warnings.map((w, i) => (
                  <li key={i} className="text-xs text-bp-yellow/70 leading-relaxed">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}