import { CheckCircle, AlertTriangle, XCircle, Shield } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ComplianceCheck, ReportSection } from '@/types';

interface ReportChecklistProps {
  sections: ReportSection[];
  complianceCheck?: ComplianceCheck;
  className?: string;
}

const statusConfig: Record<ReportSection['status'], { icon: typeof CheckCircle; label: string; className: string }> = {
  completed:  { icon: CheckCircle,  label: '已完成',  className: 'text-green-400 bg-green-500/10 border-green-500/20' },
  missing:    { icon: XCircle,      label: '缺失',    className: 'text-red-400 bg-red-500/10 border-red-500/20' },
  human_review: { icon: AlertTriangle, label: '需人工确认', className: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
};

export function ReportChecklist({ sections, complianceCheck, className }: ReportChecklistProps) {
  const completedCount = sections.filter(s => s.status === 'completed').length;
  const missingCount = sections.filter(s => s.status === 'missing').length;
  const reviewCount = sections.filter(s => s.status === 'human_review').length;
  const total = sections.length;

  return (
    <div className={cn('space-y-4', className)}>
      {/* 比赛规范完整性检查卡片 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">比赛规范完整性检查</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              挑战杯 XH-202619 · {completedCount}/{total} 项完成
            </p>
          </div>
          {/* 进度环 */}
          <div className="relative w-12 h-12">
            <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
              <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
                className="text-gray-800" strokeWidth="5" />
              <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
                className={cn(
                  completedCount === total ? 'text-green-400' :
                  completedCount > total / 2 ? 'text-amber-400' : 'text-red-400',
                )}
                strokeWidth="5"
                strokeLinecap="round"
                strokeDasharray={`${(completedCount / total) * 125.66} 125.66`}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-xs font-mono font-bold text-white">
              {Math.round((completedCount / total) * 100)}%
            </span>
          </div>
        </div>

        {/* 汇总统计 */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="text-center p-2 rounded-lg bg-green-500/5 border border-green-500/10">
            <p className="text-lg font-mono font-bold text-green-400">{completedCount}</p>
            <p className="text-[10px] text-gray-500">已完成</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-red-500/5 border border-red-500/10">
            <p className="text-lg font-mono font-bold text-red-400">{missingCount}</p>
            <p className="text-[10px] text-gray-500">缺失</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-amber-500/5 border border-amber-500/10">
            <p className="text-lg font-mono font-bold text-amber-400">{reviewCount}</p>
            <p className="text-[10px] text-gray-500">需人工确认</p>
          </div>
        </div>

        {/* 12 项字段检查列表 */}
        <div className="space-y-1.5">
          {sections.map((s) => {
            const cfg = statusConfig[s.status];
            const Icon = cfg.icon;
            return (
              <div
                key={s.key}
                className="flex flex-col gap-1 py-2 border-b border-gray-800/50 last:border-0"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-300">{s.label}</span>
                  <span className={cn(
                    'text-[10px] px-2 py-0.5 rounded-full border font-medium flex items-center gap-1',
                    cfg.className,
                  )}>
                    <Icon className="w-3 h-3" />
                    {cfg.label}
                  </span>
                </div>
                {s.note && (
                  <p className="text-[11px] text-gray-500 leading-relaxed ml-0">{s.note}</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* References 合规声明卡片 */}
      <Card className="bg-amber-500/[0.03] border-amber-500/10">
        <div className="flex items-start gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
            <Shield className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-amber-300">References 合规声明</h4>
            <p className="text-[11px] text-amber-300/70 mt-1 leading-relaxed">
              参考文献仅来自文献库和证据链，禁止虚构引用。
            </p>
            {complianceCheck && (
              <div className="mt-2 flex items-center gap-3 text-[10px]">
                <span className="text-green-400">
                  已验证 {complianceCheck.references_verified} 条
                </span>
                {complianceCheck.references_suspicious > 0 && (
                  <span className="text-red-400">
                    疑似虚构 {complianceCheck.references_suspicious} 条
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}