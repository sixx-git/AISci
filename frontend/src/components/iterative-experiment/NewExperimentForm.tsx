import { useState } from 'react';
import { ArrowLeft, Database, Plus, Sparkles } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import type { ExecutorType } from '@/types/iterativeExperiment';

interface NewExperimentFormProps {
  initialHypothesis?: string;
  busy?: boolean;
  onBack: () => void;
  onFillPrimaryHypothesis?: () => void;
  onCreate: (input: {
    hypothesis: string;
    research_goal: string;
    constraints: string[];
    executor_type: ExecutorType;
    max_iterations: number;
    skip_dataset_recommend?: boolean;
  }) => void;
}

export function NewExperimentForm({
  initialHypothesis = '',
  busy,
  onBack,
  onFillPrimaryHypothesis,
  onCreate,
}: NewExperimentFormProps) {
  const [experimentType, setExperimentType] = useState<'data' | 'simulation'>('data');
  const [maxIterations, setMaxIterations] = useState(10);
  const [hypothesis, setHypothesis] = useState(initialHypothesis);
  const [researchGoal, setResearchGoal] = useState('');
  const [constraints, setConstraints] = useState<string[]>(['', '', '']);

  const submit = (skipDatasetRecommend: boolean) => {
    onCreate({
      hypothesis: hypothesis.trim(),
      research_goal: researchGoal.trim(),
      constraints: constraints.map((x) => x.trim()).filter(Boolean),
      executor_type: experimentType === 'data' ? 'sandbox' : 'simulation',
      max_iterations: maxIterations,
      skip_dataset_recommend: skipDatasetRecommend,
    });
  };

  return (
    <Card
      title="新建实验"
      subtitle="创建实验将推荐数据集；已有数据集可跳过推荐，直接绑定本地/上传数据"
    >
      <div className="flex justify-between mb-4">
        <Button variant="secondary" size="sm" icon={<ArrowLeft className="w-4 h-4" />} onClick={onBack}>
          返回列表
        </Button>
        {onFillPrimaryHypothesis && (
          <Button
            variant="secondary"
            size="sm"
            icon={<Sparkles className="w-4 h-4" />}
            onClick={() => {
              onFillPrimaryHypothesis();
            }}
            type="button"
          >
            填入主假设
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-sm font-medium text-bp-text mb-1.5 block">实验类型</label>
          <div className="flex flex-wrap gap-2">
            <TypeChip
              active={experimentType === 'data'}
              label="假设验证（数据驱动）"
              onClick={() => setExperimentType('data')}
            />
            <TypeChip
              active={experimentType === 'simulation'}
              label="模拟实验"
              onClick={() => setExperimentType('simulation')}
            />
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-bp-text mb-1.5 block">
            最大迭代轮数：{maxIterations}
          </label>
          <input
            type="range"
            min={1}
            max={20}
            value={maxIterations}
            onChange={(e) => setMaxIterations(Number(e.target.value))}
            className="w-full accent-bp-cyan"
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="text-sm font-medium text-bp-text mb-1.5 block">实验假设</label>
        <textarea
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
          rows={4}
          placeholder="例如：在自然语言处理任务中，使用 Few-shot prompting 比 Zero-shot prompting 的准确率提升至少 10%"
          className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan resize-none"
        />
      </div>

      <div className="mb-4">
        <label className="text-sm font-medium text-bp-text mb-1.5 block">研究目标（可选，辅助说明）</label>
        <textarea
          value={researchGoal}
          onChange={(e) => setResearchGoal(e.target.value)}
          rows={2}
          placeholder="描述更广泛的研究背景和目标…"
          className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan resize-none"
        />
      </div>

      <div className="mb-5">
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-sm font-medium text-bp-text">约束条件</label>
          <button
            type="button"
            className="text-xs text-bp-cyan hover:underline inline-flex items-center gap-1"
            onClick={() => setConstraints((prev) => [...prev, ''])}
          >
            <Plus className="w-3 h-3" /> 添加更多约束
          </button>
        </div>
        <div className="space-y-2">
          {constraints.map((c, i) => (
            <input
              key={i}
              type="text"
              value={c}
              onChange={(e) => {
                const next = [...constraints];
                next[i] = e.target.value;
                setConstraints(next);
              }}
              placeholder={`约束 ${i + 1}，例如：样本量不少于 1000`}
              className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan"
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-2">
        <Button
          className="flex-1"
          disabled={!hypothesis.trim() || busy}
          onClick={() => submit(false)}
        >
          {busy ? '创建中…' : '创建实验'}
        </Button>
        {experimentType === 'data' && (
          <Button
            className="flex-1"
            variant="secondary"
            disabled={!hypothesis.trim() || busy}
            icon={<Database className="w-4 h-4" />}
            onClick={() => submit(true)}
          >
            {busy ? '创建中…' : '已有数据集'}
          </Button>
        )}
      </div>
    </Card>
  );
}

function TypeChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'px-3 py-1.5 rounded-lg text-xs border border-bp-cyan/40 bg-bp-cyan-tint text-bp-cyan'
          : 'px-3 py-1.5 rounded-lg text-xs border border-bp-border text-bp-muted hover:text-bp-text'
      }
    >
      {label}
    </button>
  );
}
