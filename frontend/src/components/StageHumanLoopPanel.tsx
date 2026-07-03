import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Edit3, Save, MessageSquare, GraduationCap, Play, Tag, Loader2, History,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import humanLoopService, { type MentorReview } from '@/services/humanLoopService';
import { PromptConsole } from '@/components/PromptConsole';

const NODE_ID_TO_STAGE: Record<string, string> = {
  problem: 'problem_understanding',
  literature: 'literature_mining',
  gaps: 'knowledge_gap',
  hypothesis: 'hypothesis_generation',
  evaluation: 'hypothesis_review',
  experiment: 'experiment_design',
  validation: 'small_validation',
  report: 'report_generation',
};

interface StageHumanLoopPanelProps {
  projectId: string;
  runId: string;
  nodeId: string;
  researchQuestion?: string;
  inputData?: Record<string, unknown> | null;
  outputData?: Record<string, unknown> | null;
  humanModifiedOutput?: Record<string, unknown> | null;
  humanReviewed?: boolean;
  humanFeedback?: string | null;
  editedAt?: string | null;
  revisionHistory?: Array<Record<string, unknown>>;
  onUpdated?: () => void;
  onRerunStarted?: (newRunId: string) => void;
}

export function StageHumanLoopPanel({
  projectId,
  runId,
  nodeId,
  researchQuestion = '',
  inputData,
  outputData,
  humanModifiedOutput,
  humanReviewed,
  humanFeedback,
  editedAt,
  revisionHistory = [],
  onUpdated,
  onRerunStarted,
}: StageHumanLoopPanelProps) {
  const navigate = useNavigate();
  const stage = NODE_ID_TO_STAGE[nodeId] || nodeId;
  const effectiveOutput = humanModifiedOutput || outputData || {};
  const [editJson, setEditJson] = useState('');
  const [feedback, setFeedback] = useState(humanFeedback || '');
  const [chatMessage, setChatMessage] = useState('');
  const [chatReply, setChatReply] = useState('');
  const [mentorReview, setMentorReview] = useState<MentorReview | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEditJson(JSON.stringify(effectiveOutput, null, 2));
    setFeedback(humanFeedback || '');
  }, [effectiveOutput, humanFeedback, nodeId]);

  const mentorTarget = useMemo(() => {
    if (stage.includes('hypothesis')) return 'hypothesis' as const;
    if (stage.includes('experiment') || stage.includes('validation')) return 'experiment_design' as const;
    if (stage.includes('report')) return 'report' as const;
    return 'hypothesis' as const;
  }, [stage]);

  const handleSaveEdit = async () => {
    setBusy('save');
    setError(null);
    try {
      const parsed = JSON.parse(editJson) as Record<string, unknown>;
      const res = await humanLoopService.saveStageOutput({
        project_id: projectId,
        run_id: runId,
        stage,
        output_data: parsed,
        human_feedback: feedback,
        mark_reviewed: true,
      });
      if (res.code === 200) onUpdated?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败，请检查 JSON 格式');
    } finally {
      setBusy(null);
    }
  };

  const handleChat = async () => {
    if (!chatMessage.trim()) return;
    setBusy('chat');
    setError(null);
    try {
      const res = await humanLoopService.stageChat({
        project_id: projectId,
        run_id: runId,
        stage,
        message: chatMessage,
        apply_change: true,
      });
      if (res.code === 200 && res.data) {
        setChatReply(res.data.explanation);
        setEditJson(JSON.stringify(res.data.revised_output, null, 2));
        onUpdated?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '对话修改失败');
    } finally {
      setBusy(null);
    }
  };

  const handleMentorReview = async () => {
    setBusy('mentor');
    setError(null);
    try {
      const res = await humanLoopService.mentorReview({
        project_id: projectId,
        run_id: runId,
        stage,
        target_type: mentorTarget,
        content: JSON.parse(editJson) as Record<string, unknown>,
        research_question: researchQuestion,
        user_notes: feedback,
      });
      if (res.code === 200 && res.data?.review) {
        setMentorReview(res.data.review);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '导师评审失败');
    } finally {
      setBusy(null);
    }
  };

  const handleRerun = async () => {
    setBusy('rerun');
    setError(null);
    try {
      const res = await humanLoopService.rerunFromStage({
        project_id: projectId,
        run_id: runId,
        stage,
        use_human_modified_output: true,
        rerun_mode: 'from_stage_onward',
      });
      if (res.code === 200 && res.data?.run_id) {
        onRerunStarted?.(res.data.run_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '重跑失败');
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <Card title="人在回路" subtitle="查看 · 编辑 · 追问 · 重跑">
        <div className="flex flex-wrap gap-2 mb-3">
          <Button variant="secondary" className="text-xs" onClick={() => setShowPrompt(true)}>
            <Tag className="w-3.5 h-3.5 mr-1" /> 编辑 Prompt
          </Button>
          <Button
            variant="secondary"
            className="text-xs"
            onClick={() => navigate(`/projects/${projectId}?tab=prompts&prompt_stage=${stage}`)}
          >
            <Tag className="w-3.5 h-3.5 mr-1" /> Prompt 管理
          </Button>
          <Button variant="secondary" className="text-xs" onClick={handleMentorReview} disabled={!!busy}>
            {busy === 'mentor' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <GraduationCap className="w-3.5 h-3.5 mr-1" />}
            导师评审
          </Button>
          <Button variant="secondary" className="text-xs" onClick={handleRerun} disabled={!!busy}>
            {busy === 'rerun' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Play className="w-3.5 h-3.5 mr-1" />}
            从此阶段继续后续流程
          </Button>
        </div>

        {humanReviewed && (
          <p className="text-xs text-bp-yellow mb-2">
            已人工审阅 {editedAt ? `· ${editedAt}` : ''}
          </p>
        )}
        {error && <p className="text-xs text-danger-400 mb-2">{error}</p>}

        <CollapsibleBlock title="输入 input_data" data={inputData} defaultOpen={false} />
        <CollapsibleBlock title="原始 output_data" data={outputData} defaultOpen={false} />

        <div className="mt-3">
          <div className="flex items-center gap-2 mb-2 text-xs text-bp-muted">
            <Edit3 className="w-3.5 h-3.5" /> 编辑 output_data（保存为人工修改）
          </div>
          <textarea
            className="w-full min-h-[180px] rounded-lg bg-bp-base/70 border border-bp-border text-xs font-mono text-bp-text p-3"
            value={editJson}
            onChange={(e) => setEditJson(e.target.value)}
          />
          <input
            className="w-full mt-2 rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text p-2"
            placeholder="修改说明 / human_feedback"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
          <Button className="mt-2 text-xs" onClick={handleSaveEdit} disabled={busy === 'save'}>
            {busy === 'save' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Save className="w-3.5 h-3.5 mr-1" />}
            保存人工修改
          </Button>
        </div>

        <div className="mt-4 pt-4 border-t border-bp-border">
          <div className="flex items-center gap-2 mb-2 text-xs text-bp-muted">
            <MessageSquare className="w-3.5 h-3.5" /> 多轮追问修改
          </div>
          <textarea
            className="w-full min-h-[64px] rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text p-2"
            placeholder="例如：重新生成更具体 / 加入 VFL 约束 / 加强数据集部分"
            value={chatMessage}
            onChange={(e) => setChatMessage(e.target.value)}
          />
          <Button variant="secondary" className="mt-2 text-xs" onClick={handleChat} disabled={busy === 'chat'}>
            {busy === 'chat' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
            发送并应用修改
          </Button>
          {chatReply && <p className="text-xs text-bp-green mt-2">{chatReply}</p>}
        </div>

        {mentorReview && (
          <div className="mt-4 pt-4 border-t border-bp-border space-y-2">
            <p className="text-xs font-medium text-bp-green">导师评审结果</p>
            <ReviewList title="优点" items={mentorReview.strengths} />
            <ReviewList title="不足" items={mentorReview.weaknesses} />
            <ReviewList title="修改建议" items={mentorReview.revision_suggestions} />
            <ReviewList title="风险点" items={mentorReview.risk_points} />
            <ReviewList title="需补充证据" items={mentorReview.required_additional_evidence} />
            {mentorReview.overall_assessment && (
              <p className="text-xs text-bp-muted">{mentorReview.overall_assessment}</p>
            )}
          </div>
        )}

        {revisionHistory.length > 0 && (
          <div className="mt-4 pt-4 border-t border-bp-border">
            <div className="flex items-center gap-2 text-xs text-bp-muted mb-2">
              <History className="w-3.5 h-3.5" /> 修改历史 ({revisionHistory.length})
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {revisionHistory.slice().reverse().slice(0, 5).map((h) => (
                <div key={String(h.id || h.at)} className="text-xs text-bp-muted border border-bp-border rounded p-2">
                  <span className="text-bp-muted">{String(h.at || '')}</span>
                  {h.feedback ? ` · ${String(h.feedback)}` : ''}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <PromptConsole
        projectId={projectId}
        stage={stage}
        open={showPrompt}
        onClose={() => setShowPrompt(false)}
      />
    </>
  );
}

function CollapsibleBlock({
  title,
  data,
  defaultOpen = false,
}: {
  title: string;
  data?: Record<string, unknown> | null;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!data) return null;
  return (
    <div className="mb-2">
      <button type="button" onClick={() => setOpen(!open)} className="text-xs text-bp-muted hover:text-bp-text">
        {open ? '▼' : '▶'} {title}
      </button>
      {open && (
        <pre className="mt-1 text-xs text-bp-muted font-mono bg-bp-base/60 border border-bp-border rounded p-2 max-h-40 overflow-y-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ReviewList({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-xs text-bp-muted mb-1">{title}</p>
      <ul className="text-xs text-bp-text space-y-0.5 list-disc list-inside">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default StageHumanLoopPanel;
