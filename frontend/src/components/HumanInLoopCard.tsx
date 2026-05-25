import { AlertTriangle } from 'lucide-react';
import { Card } from '@/components/Card';

interface HumanInLoopCardProps {
  className?: string;
}

export function HumanInLoopCard({ className }: HumanInLoopCardProps) {
  return (
    <Card className={className}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-amber-400">人在回路</h4>
          <p className="text-xs text-gray-500">人类科学家可在关键节点介入决策</p>
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
            className="w-full flex items-start gap-2 p-2.5 rounded-lg border border-amber-500/15 bg-amber-500/5 hover:border-amber-500/30 hover:bg-amber-500/10 transition-all text-left"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-gray-200">{item.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}