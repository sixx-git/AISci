import { useState } from 'react';
import { AlertTriangle, Play, RefreshCw, XCircle } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { humanLoopService } from '@/services/humanLoopService';
import type { HitlGateInfo } from '@/types';

interface HitlGatePanelProps {
  projectId: string;
  runId: string;
  gate?: HitlGateInfo | null;
  runStatus?: string;
  onResumed?: (newRunId?: string) => void;
}

export function HitlGatePanel({
  projectId,
  runId,
  gate,
  runStatus,
  onResumed,
}: HitlGatePanelProps) {
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paused = gate?.paused || runStatus === 'human_review_required';
  if (!paused) return null;

  const handleAction = async (action: 'continue' | 'rerun' | 'abort') => {
    setLoading(true);
    setError(null);
    try {
      const res = await humanLoopService.resumeHitlGate({
        project_id: projectId,
        run_id: runId,
        action,
        human_feedback: feedback,
        inject_feedback: true,
      });
      if (res.code !== 200) {
        setError(res.message || '操作失败');
        return;
      }
      const newRunId = res.data?.run_id;
      onResumed?.(action === 'rerun' ? newRunId : runId);
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mb-4 border-amber-500/30 bg-amber-500/5">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-9 h-9 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-amber-300">Teaching HITL Gate · 等待人工确认</h3>
          <p className="text-xs text-bp-muted mt-1">
            阶段「{gate?.stage_label || gate?.stage || '—'}」已完成。请审阅结果后选择继续、从本阶段重跑或终止。
          </p>
          {gate?.paused_at && (
            <p className="text-[10px] text-bp-muted mt-1">暂停于 {gate.paused_at}</p>
          )}
        </div>
      </div>

      <textarea
        className="w-full mb-3 px-3 py-2 text-xs rounded-lg bg-bp-base border border-bp-border text-bp-text placeholder:text-bp-muted min-h-[72px]"
        placeholder="可选：输入人工反馈，将在继续运行时注入下一轮假设/实验设计约束…"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
      />

      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={loading}
          onClick={() => handleAction('continue')}
          className="gap-1.5"
        >
          <Play className="w-3.5 h-3.5" />
          确认并继续
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={loading}
          onClick={() => handleAction('rerun')}
          className="gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          编辑后从本阶段重跑
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={loading}
          onClick={() => handleAction('abort')}
          className="gap-1.5 text-red-400 hover:text-red-300"
        >
          <XCircle className="w-3.5 h-3.5" />
          终止运行
        </Button>
      </div>
    </Card>
  );
}
