import { FlaskConical, Plus, Trash2, Eye, FileCheck2 } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { cn } from '@/lib/utils';
import type { IterativeExperiment } from '@/types/iterativeExperiment';
import { PHASE_EMOJI, PHASE_LABEL } from './phaseLabels';

interface ExperimentListProps {
  experiments: IterativeExperiment[];
  reportIds: string[];
  onNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onToggleReport: (id: string) => void;
}

export function ExperimentList({
  experiments,
  reportIds,
  onNew,
  onOpen,
  onDelete,
  onToggleReport,
}: ExperimentListProps) {
  const running = experiments.filter((e) => e.status === 'running' || e.phase === 'running').length;
  const completed = experiments.filter((e) => e.phase === 'completed').length;
  const pending = experiments.filter((e) => e.phase === 'created' || e.phase === 'data_recommended').length;

  return (
    <div className="space-y-4">
      <Card title="迭代实验">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <Metric label="总实验数" value={experiments.length} />
          <Metric label="运行中" value={running} />
          <Metric label="已完成" value={completed} />
          <Metric label="待启动" value={pending} />
        </div>

        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <h4 className="text-sm font-semibold text-bp-text">实验列表</h4>
            <p className="text-xs text-bp-muted mt-0.5">
              勾选一个或多个实验作为报告输入（手动指定）
              {reportIds.length > 0 ? ` · 已选 ${reportIds.length}` : ''}
            </p>
          </div>
          <Button icon={<Plus className="w-4 h-4" />} onClick={onNew}>
            新建实验
          </Button>
        </div>

        {experiments.length === 0 ? (
          <EmptyState
            icon={<FlaskConical className="w-8 h-8" />}
            title="暂无实验"
            description="输入实验假设，AI 将推荐数据集并进入设计脚本与迭代闭环"
            action={{ label: '新建实验', onClick: onNew }}
          />
        ) : (
          <ul className="divide-y divide-bp-border rounded-bp border border-bp-border overflow-hidden">
            {experiments.map((exp) => {
              const forReport = reportIds.includes(exp.id);
              return (
                <li
                  key={exp.id}
                  className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-3 bg-bp-panel/20 hover:bg-bp-panel/40 transition-colors"
                >
                  <label className="flex items-start gap-2 min-w-0 flex-1 cursor-pointer">
                    <input
                      type="checkbox"
                      className="mt-1 accent-bp-cyan"
                      checked={forReport}
                      onChange={() => onToggleReport(exp.id)}
                      title="用于报告生成"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm">{PHASE_EMOJI[exp.phase]}</span>
                        <span className="text-sm font-medium text-bp-text truncate">{exp.title}</span>
                        {forReport && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border border-bp-cyan/30 bg-bp-cyan-tint text-bp-cyan inline-flex items-center gap-0.5">
                            <FileCheck2 className="w-3 h-3" />
                            用于报告
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-bp-muted mt-0.5 line-clamp-2">
                        {exp.hypothesis || exp.research_goal}
                      </p>
                      <div className="flex flex-wrap gap-2 mt-1.5 text-[11px] text-bp-muted">
                        <span>阶段: {PHASE_LABEL[exp.phase]}</span>
                        <span>·</span>
                        <span>
                          {exp.current_iteration}/{exp.max_iterations} 轮
                        </span>
                        <span>·</span>
                        <span>{exp.executor_type === 'sandbox' ? '数据驱动' : '模拟实验'}</span>
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Eye className="w-3.5 h-3.5" />}
                      onClick={() => onOpen(exp.id)}
                    >
                      查看
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Trash2 className="w-3.5 h-3.5" />}
                      onClick={() => {
                        if (window.confirm(`确认删除实验「${exp.title}」？`)) onDelete(exp.id);
                      }}
                    >
                      删除
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-base/50 px-3 py-2.5 text-center')}>
      <div className="text-xl font-bold font-mono text-bp-cyan">{value}</div>
      <div className="text-xs text-bp-muted mt-0.5">{label}</div>
    </div>
  );
}
