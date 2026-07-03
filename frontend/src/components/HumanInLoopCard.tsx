import { AlertTriangle } from 'lucide-react';
import { Card } from '@/components/Card';

interface HumanInLoopCardProps {
  className?: string;
}

export function HumanInLoopCard({ className }: HumanInLoopCardProps) {
  return (
    <Card className={className}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-bp-yellow/15 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-bp-yellow" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-bp-yellow">人在回路</h4>
          <p className="text-xs text-bp-muted">人类科学家可在关键节点介入决策</p>
        </div>
      </div>
      <div className="space-y-2">
        {[
          { label: '查看证据链', desc: '追溯假设生成背后的文献依据和推理路径' },
          { label: '修改研究边界', desc: '调整研究范围、约束条件或评估标准' },
          { label: '确认继续迭代', desc: '审查中间结果，决定是否继续下一阶段' },
        ].map((item) => (
          <button
            key={item.label}
            className="w-full flex items-start gap-2 p-2.5 rounded-lg border border-bp-yellow/15 bg-bp-yellow/5 hover-accent-left-yellow hover:bg-bp-yellow/10 transition-all text-left"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-bp-yellow mt-1.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-bp-text">{item.label}</div>
              <div className="text-xs text-bp-muted mt-0.5">{item.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}