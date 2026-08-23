import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Lightbulb, Play } from 'lucide-react';
import { Button } from '@/components/Button';
import { getHitlGateReviewTarget } from '@/config/hitlGateReview';
import { humanLoopService } from '@/services/humanLoopService';
import { pipelineService } from '@/services/pipelineService';
import { navigateToProjectTab } from '@/lib/projectNavigation';
import { activeRunKey, activeRunStatusKey } from '@/lib/storageKeys';
import type { HitlGateInfo } from '@/types';

interface HitlGateContinueBarProps {
  projectId: string;
  runId?: string | null;
  /** 仅在这些 gate stage 下显示；不传则任意暂停阶段均显示 */
  stages?: string[];
  revalidateKey?: number;
}

export function HitlGateContinueBar({
  projectId,
  runId,
  stages,
  revalidateKey,
}: HitlGateContinueBarProps) {
  const navigate = useNavigate();
  const [resolvedRunId, setResolvedRunId] = useState<string | null>(runId ?? null);
  const [gate, setGate] = useState<HitlGateInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (runId) {
      setResolvedRunId(runId);
      return;
    }
    let cancelled = false;
    pipelineService.getRuns(projectId).then((res) => {
      if (cancelled) return;
      if (res.code === 200 && res.data?.length) {
        setResolvedRunId(res.data[0].run_id);
      } else {
        setResolvedRunId(null);
      }
    }).catch(() => {
      if (!cancelled) setResolvedRunId(null);
    });
    return () => { cancelled = true; };
  }, [projectId, runId, revalidateKey]);

  useEffect(() => {
    if (!resolvedRunId) {
      setGate(null);
      return;
    }
    let cancelled = false;
    humanLoopService.getHitlGateStatus(resolvedRunId).then((res) => {
      if (cancelled) return;
      if (res.code === 200 && res.data?.paused) {
        setGate({
          paused: res.data.paused,
          stage: res.data.stage,
          stage_label: res.data.stage_label,
          paused_at: res.data.paused_at,
        });
      } else {
        setGate(null);
      }
    }).catch(() => {
      if (!cancelled) setGate(null);
    });
    return () => { cancelled = true; };
  }, [resolvedRunId, revalidateKey]);

  const handleContinue = useCallback(async () => {
    if (!resolvedRunId || !gate?.stage) return;
    const target = getHitlGateReviewTarget(gate.stage);

    // 可行性评估后：只跳转迭代实验页，不恢复 Pipeline 自动跑实验/报告
    if (target.continueAction === 'navigate') {
      navigateToProjectTab(navigate, projectId, target.tab);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await humanLoopService.resumeHitlGate({
        project_id: projectId,
        run_id: resolvedRunId,
        action: 'continue',
        inject_feedback: false,
      });
      if (res.code !== 200) {
        setError(res.message || '启动失败');
        return;
      }
      const nextRunId = res.data?.run_id || resolvedRunId;
      setGate(null);
      try {
        localStorage.setItem(activeRunKey(projectId), nextRunId);
        localStorage.setItem(activeRunStatusKey(projectId), 'running');
      } catch { /* ignore */ }
      navigateToProjectTab(navigate, projectId, 'workflow');
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, resolvedRunId, navigate, gate?.stage]);

  if (!gate?.paused) return null;
  if (stages?.length && gate.stage && !stages.includes(gate.stage)) return null;

  const target = getHitlGateReviewTarget(gate.stage);
  const isNavigate = target.continueAction === 'navigate';

  return (
    <div className="mb-6 p-4 bg-bp-cyan-tint border border-bp-cyan/25 rounded-bp flex items-start gap-3">
      <div className="w-9 h-9 rounded-lg bg-bp-cyan/15 flex items-center justify-center shrink-0">
        <Lightbulb className="w-5 h-5 text-bp-cyan" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-bp-text font-medium">{target.continueTitle}</p>
        <p className="text-xs text-bp-muted mt-1">{target.continueDescription}</p>
        {error && <p className="text-xs text-danger-400 mt-2">{error}</p>}
      </div>
      <Button
        size="sm"
        variant="primary"
        disabled={loading}
        isLoading={loading}
        onClick={() => void handleContinue()}
        className="gap-1.5 shrink-0"
      >
        {isNavigate ? <ArrowRight className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
        {target.continueButtonLabel}
      </Button>
    </div>
  );
}
