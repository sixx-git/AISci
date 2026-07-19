import { useState } from 'react';
import { Lightbulb, Sparkles, Check } from 'lucide-react';
import { Button } from '@/components/Button';
import type { HypothesisEvolutionData } from '@/types';

interface HypothesisEvolutionPanelProps {
  data: HypothesisEvolutionData;
  projectId?: string;
  runId?: string | null;
  onSelected?: () => void;
}

const STRATEGY_LABEL: Record<string, string> = {
  simplify: '简化可行',
  out_of_box: '跳出固有思维',
};

export function HypothesisEvolutionPanel({
  data,
  projectId,
  runId,
  onSelected,
}: HypothesisEvolutionPanelProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [localSelected, setLocalSelected] = useState<string | null>(
    data.selected_candidate_id ?? null,
  );

  const candidates = data.candidates ?? [];
  if (!data.enabled || data.skipped || candidates.length === 0) {
    return null;
  }

  const handleSelect = async (candidateId: string) => {
    if (!projectId || !runId) {
      setError('缺少 run_id，请从最新 Pipeline 运行结果进入后再采用');
      return;
    }
    setBusyId(candidateId);
    setError(null);
    try {
      const { humanLoopService } = await import('@/services/humanLoopService');
      const res = await humanLoopService.selectEvolvedHypothesis({
        project_id: projectId,
        run_id: runId,
        candidate_id: candidateId,
      });
      if (res.code !== 200) {
        setError(res.message || '采用失败');
        return;
      }
      setLocalSelected(candidateId);
      onSelected?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '采用失败');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30 space-y-3">
      <h3 className="text-sm font-semibold text-bp-text flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-bp-cyan" />
        假设演化候选
      </h3>
      <p className="text-xs text-bp-muted">
        红蓝对抗后生成的简化 / 跳出固有思维版本。未采用则继续使用原主假设进入实验。
      </p>
      {error && (
        <p className="text-xs text-danger-400">{error}</p>
      )}
      <div className="space-y-3">
        {candidates.map((c) => {
          const selected = localSelected === c.candidate_id;
          const label =
            c.strategy_label ||
            STRATEGY_LABEL[c.strategy || ''] ||
            c.strategy ||
            '演化';
          return (
            <div
              key={c.candidate_id}
              className={`p-3 rounded border text-xs space-y-2 ${
                selected
                  ? 'border-bp-cyan/50 bg-bp-cyan/5'
                  : 'border-bp-border/60 bg-bp-base/40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 font-medium text-bp-text">
                  <Lightbulb className="w-3.5 h-3.5 text-bp-cyan" />
                  {label}
                </span>
                {selected ? (
                  <span className="inline-flex items-center gap-1 text-bp-cyan">
                    <Check className="w-3.5 h-3.5" /> 已采用
                  </span>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!!busyId || !runId}
                    onClick={() => handleSelect(c.candidate_id)}
                  >
                    {busyId === c.candidate_id ? '采用中…' : '采用此假设'}
                  </Button>
                )}
              </div>
              <p className="text-bp-text leading-relaxed">{c.hypothesis}</p>
              {c.rationale && (
                <p className="text-bp-muted leading-relaxed">{c.rationale}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
