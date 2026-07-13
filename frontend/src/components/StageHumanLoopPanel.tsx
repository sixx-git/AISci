import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Edit3, Save, MessageSquare, GraduationCap, Play, Tag, Loader2, History, Send,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import humanLoopService, { type HitlInteractionMode, type MentorReview, type RerunMode } from '@/services/humanLoopService';
import { PromptConsole } from '@/components/PromptConsole';

const NODE_ID_TO_STAGE: Record<string, string> = {
  problem: 'problem_understanding',
  literature: 'literature_mining',
  data: 'experiment_design',
  gaps: 'knowledge_gap',
  hypothesis: 'hypothesis_generation',
  evaluation: 'hypothesis_review',
  experiment: 'experiment_design',
  validation: 'small_validation',
  report: 'report_generation',
};

const STAGE_RERUN_OPTIONS: { key: string; label: string }[] = [
  { key: 'problem_understanding', label: '问题理解' },
  { key: 'literature_mining', label: '文献挖掘' },
  { key: 'knowledge_gap', label: '知识缺口' },
  { key: 'hypothesis_generation', label: '假设生成' },
  { key: 'hypothesis_review', label: '假设评审' },
  { key: 'experiment_design', label: '实验设计' },
  { key: 'small_validation', label: '小样验证' },
  { key: 'report_generation', label: '报告生成' },
];

interface ChatTurn {
  id?: string;
  at?: string;
  user_message?: string;
  assistant_explanation?: string;
  changes_summary?: string[];
  applied?: boolean;
  mode?: string;
  revision_mode?: string;
}

const PENDING_LABELS = new Set(['正在思考…', '正在生成修订…', '正在提交重跑…']);

function modeLabel(mode?: string): string {
  if (mode === 'advisory') return '咨询';
  if (mode === 'revise') return '修订';
  if (mode === 'rerun_agent') return '重跑';
  return '对话';
}
const INTERACTION_MODES: { id: HitlInteractionMode; label: string; hint: string }[] = [
  { id: 'advisory', label: '咨询对话', hint: '解释图表/方法、给建议，不修改 Pipeline 输出' },
  { id: 'revise', label: '轻量修订', hint: 'LLM 就地改当前版本，写入人工修订层' },
  { id: 'rerun_agent', label: '重跑智能体', hint: '真正重新执行本阶段 Agent，结果可传递下游' },
];

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
  chatHistory?: ChatTurn[];
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
  chatHistory: chatHistoryProp = [],
  onUpdated,
  onRerunStarted,
}: StageHumanLoopPanelProps) {
  const navigate = useNavigate();
  const stage = NODE_ID_TO_STAGE[nodeId] || nodeId;
  const currentStageLabel = STAGE_RERUN_OPTIONS.find((s) => s.key === stage)?.label || stage;
  const effectiveOutput = humanModifiedOutput || outputData || {};
  const [editJson, setEditJson] = useState('');
  const [feedback, setFeedback] = useState(humanFeedback || '');
  const [chatMessage, setChatMessage] = useState('');
  const [interactionMode, setInteractionMode] = useState<HitlInteractionMode>('advisory');
  const [rerunScope, setRerunScope] = useState<RerunMode>('single_stage');
  const [rerunTargetStage, setRerunTargetStage] = useState(stage);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>(chatHistoryProp);
  const [latestReply, setLatestReply] = useState('');
  const [mentorReview, setMentorReview] = useState<MentorReview | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [globalConstraints, setGlobalConstraints] = useState<string[]>([]);
  const [recentFeedbackEntries, setRecentFeedbackEntries] = useState<Array<Record<string, unknown>>>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const userChattingRef = useRef(false);

  useEffect(() => {
    setRerunTargetStage(stage);
  }, [stage]);

  const loadChatHistory = useCallback(async () => {
    if (!runId || !stage) return;
    try {
      const res = await humanLoopService.getStageDetail(runId, stage);
      if (res.code === 200 && Array.isArray(res.data?.chat_history)) {
        const history = res.data.chat_history as ChatTurn[];
        setChatHistory(history);
        const last = [...history].reverse().find(
          (t) => t.assistant_explanation && !PENDING_LABELS.has(t.assistant_explanation),
        );
        if (last?.assistant_explanation) {
          setLatestReply(last.assistant_explanation);
        }
      }
      if (res.code === 200 && res.data) {
        setGlobalConstraints(res.data.global_constraints || []);
        setRecentFeedbackEntries(res.data.recent_feedback_entries || []);
      }
    } catch {
      /* 忽略加载失败 */
    }
  }, [runId, stage]);

  useEffect(() => {
    setEditJson(JSON.stringify(effectiveOutput, null, 2));
    setFeedback(humanFeedback || '');
  }, [effectiveOutput, humanFeedback, nodeId]);

  useEffect(() => {
    loadChatHistory();
  }, [loadChatHistory, nodeId]);

  useEffect(() => {
    if (chatHistoryProp.length > 0) {
      setChatHistory(chatHistoryProp);
    }
  }, [chatHistoryProp, nodeId, runId]);

  useEffect(() => {
    if (!userChattingRef.current) return;
    const el = chatScrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [chatHistory, busy]);

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
      if (res.code === 200) {
        onUpdated?.();
        await loadChatHistory();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败，请检查 JSON 格式');
    } finally {
      setBusy(null);
    }
  };

  const chatPlaceholder = useMemo(() => {
    if (interactionMode === 'advisory') {
      return '例如：这个图表说明什么？有没有其他推荐方法？';
    }
    if (interactionMode === 'revise') {
      return '例如：把假设 2 改得更具体 / 加强实验对照组描述';
    }
    return '例如：加入 VFL 约束后重新生成本阶段输出';
  }, [interactionMode]);

  const pendingChatLabel = interactionMode === 'advisory'
    ? '正在思考…'
    : interactionMode === 'revise'
      ? '正在生成修订…'
      : '正在提交重跑…';

  const handleChat = async () => {
    if (!chatMessage.trim()) return;
    const userMsg = chatMessage.trim();
    userChattingRef.current = interactionMode !== 'rerun_agent';
    setBusy('chat');
    setError(null);
    setChatMessage('');
    setChatHistory((prev) => [
      ...prev,
      {
        id: `pending-${Date.now()}`,
        user_message: userMsg,
        assistant_explanation: pendingChatLabel,
        mode: interactionMode,
      },
    ]);

    try {
      if (interactionMode === 'rerun_agent') {
        const res = await humanLoopService.rerunFromStage({
          project_id: projectId,
          run_id: runId,
          stage: rerunTargetStage,
          use_human_modified_output: true,
          rerun_mode: rerunScope,
          human_feedback: userMsg,
        });
        const targetLabel = STAGE_RERUN_OPTIONS.find((s) => s.key === rerunTargetStage)?.label || rerunTargetStage;
        const scopeLabel = rerunScope === 'single_stage' ? '仅重跑本阶段' : '从此阶段继续后续流程';
        const explanation = res.code === 200 && res.data?.run_id
          ? (res.data.in_place ?? res.data.run_id === runId)
            ? `已提交智能体重跑（${targetLabel} · ${scopeLabel}），仍在当前运行 ${runId.slice(0, 8)}…\n修改意见已作为约束注入：${userMsg}`
            : `已提交智能体重跑（${targetLabel} · ${scopeLabel}）。新 run: ${res.data.run_id.slice(0, 8)}…\n修改意见已作为约束注入：${userMsg}`
          : res.message || '重跑提交失败';
        setChatHistory((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last) {
            last.assistant_explanation = explanation;
            last.mode = 'rerun_agent';
            last.applied = false;
          }
          return next;
        });
        if (res.code === 200 && res.data?.run_id) {
          const inPlace = res.data.in_place ?? res.data.run_id === runId;
          onRerunStarted?.(inPlace ? runId : res.data.run_id);
        } else {
          setError(explanation);
        }
        return;
      }

      const res = await humanLoopService.stageChat({
        project_id: projectId,
        run_id: runId,
        stage,
        message: userMsg,
        apply_change: interactionMode === 'revise',
        mode: interactionMode,
      });
      if (res.code !== 200 || !res.data) {
        throw new Error(res.message || '对话请求失败');
      }
      if (res.data.chat_history?.length) {
        setChatHistory(res.data.chat_history as ChatTurn[]);
      } else {
        setChatHistory((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last) {
            last.assistant_explanation = res.data?.explanation;
            last.changes_summary = res.data?.changes_summary;
            last.applied = res.data?.applied;
            last.mode = res.data?.mode;
          }
          return next;
        });
      }
      if (res.data.explanation) {
        setLatestReply(res.data.explanation);
      }
      if (res.data.applied && res.data.revised_output) {
        setEditJson(JSON.stringify(res.data.revised_output, null, 2));
      } else if (res.data.explanation?.startsWith('自动修改失败') || res.data.explanation?.startsWith('咨询回答失败')) {
        setError(res.data.explanation);
      }
      onUpdated?.();
      await loadChatHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : '对话失败');
      setChatHistory((prev) => prev.slice(0, -1));
      setChatMessage(userMsg);
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
        stage: rerunTargetStage,
        use_human_modified_output: true,
        rerun_mode: 'from_stage_onward',
        human_feedback: feedback.trim() || undefined,
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
      <Card title="人在回路" subtitle="咨询 · 修订 · 全局约束 · 可选重跑">
        <div className="flex flex-wrap gap-2 mb-3">
          <Button variant="secondary" className="text-xs" onClick={() => setShowPrompt(true)}>
            <Tag className="w-3.5 h-3.5 mr-1" /> 编辑 Prompt
          </Button>
          <Button
            variant="secondary"
            className="text-xs"
            onClick={() => navigate(`/projects/${projectId}?tab=prompts&prompt_stage=${stage}`)}
          >
            <Tag className="w-3.5 h-3.5 mr-1" /> 高级 Prompt
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
            {humanModifiedOutput ? ' · 当前为对话/人工修订版本' : ''}
          </p>
        )}
        {error && <p className="text-xs text-danger-400 mb-2">{error}</p>}

        <CollapsibleBlock title="原始 input_data（阶段生成时的输入）" data={inputData} defaultOpen={false} />
        <CollapsibleBlock title="原始 output_data（Pipeline 首次输出，不会被覆盖）" data={outputData} defaultOpen={false} />

        <div className="mt-4 pt-4 border-t border-bp-border">
          <div className="flex items-center gap-2 mb-2 text-xs text-bp-muted">
            <MessageSquare className="w-3.5 h-3.5" /> 交互模式
          </div>
          <div className="flex flex-wrap gap-2 mb-2">
            {INTERACTION_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setInteractionMode(m.id)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  interactionMode === m.id
                    ? 'border-bp-cyan bg-bp-cyan-tint text-bp-cyan'
                    : 'border-bp-border text-bp-muted hover:text-bp-text'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-bp-muted/80 mb-3">
            {INTERACTION_MODES.find((m) => m.id === interactionMode)?.hint}
          </p>

          {interactionMode === 'rerun_agent' && (
            <div className="space-y-2 mb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-bp-muted">重跑起点</span>
                <select
                  className="text-xs rounded-bp border border-bp-border bg-bp-base px-2 py-1 text-bp-text"
                  value={rerunTargetStage}
                  onChange={(e) => setRerunTargetStage(e.target.value)}
                  disabled={!!busy}
                >
                  {STAGE_RERUN_OPTIONS.map((opt) => (
                    <option key={opt.key} value={opt.key}>{opt.label}</option>
                  ))}
                </select>
                {rerunTargetStage !== stage && (
                  <span className="text-xs text-bp-yellow">
                    从「{STAGE_RERUN_OPTIONS.find((s) => s.key === rerunTargetStage)?.label}」重跑（当前查看：{currentStageLabel}）
                  </span>
                )}
              </div>
              <p className="text-xs text-bp-muted/80">
                跨阶段重跑会保留起点之前的阶段结果，并将你在对话中的问题与下游进展摘要注入目标智能体。
              </p>
              <div className="flex flex-wrap gap-2">
                <label className="flex items-center gap-1.5 text-xs text-bp-muted cursor-pointer">
                  <input
                    type="radio"
                    name="rerun-scope"
                    checked={rerunScope === 'single_stage'}
                    onChange={() => setRerunScope('single_stage')}
                  />
                  仅重跑本阶段
                </label>
                <label className="flex items-center gap-1.5 text-xs text-bp-muted cursor-pointer">
                  <input
                    type="radio"
                    name="rerun-scope"
                    checked={rerunScope === 'from_stage_onward'}
                    onChange={() => setRerunScope('from_stage_onward')}
                  />
                  重跑并继续后续流程
                </label>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-bp-muted">对话记录 ({chatHistory.length})</span>
            <button
              type="button"
              className="text-xs text-bp-cyan hover:underline"
              onClick={() => loadChatHistory()}
              disabled={!!busy}
            >
              刷新记录
            </button>
          </div>

          <div
            ref={chatScrollRef}
            className="rounded-lg border border-bp-border bg-bp-base/50 min-h-[160px] max-h-72 overflow-y-auto p-3 space-y-3 mb-3"
          >
            {chatHistory.length === 0 ? (
              <p className="text-xs text-bp-muted">
                选择上方模式后开始对话。咨询模式可问图表含义、替代方法；重跑模式会真正执行 Agent。
              </p>
            ) : (
              chatHistory.map((turn, idx) => (
                <div key={turn.id || `${turn.at}-${idx}`} className="space-y-1.5">
                  {turn.user_message && (
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-lg bg-bp-cyan-dim/30 border border-bp-cyan-dim px-3 py-2 text-xs text-bp-text">
                        <span className="text-[10px] text-bp-muted block mb-0.5">你 · {modeLabel(turn.mode)}</span>
                        {turn.user_message}
                      </div>
                    </div>
                  )}
                  {turn.assistant_explanation && (
                    <div className="flex justify-start">
                      <div
                        className={`max-w-[85%] rounded-lg border px-3 py-2 text-xs whitespace-pre-wrap ${
                          turn.assistant_explanation.startsWith('自动修改失败')
                            || turn.assistant_explanation.startsWith('咨询回答失败')
                            ? 'border-danger-400/50 text-danger-400 bg-danger-400/5'
                            : PENDING_LABELS.has(turn.assistant_explanation)
                              ? 'border-bp-border text-bp-muted'
                              : turn.mode === 'advisory' || turn.revision_mode === 'advisory'
                                ? 'border-bp-purple/30 text-bp-text bg-bp-purple/5'
                                : turn.mode === 'rerun_agent'
                                  ? 'border-bp-yellow/30 text-bp-yellow bg-bp-yellow/5'
                                  : 'border-bp-green/30 text-bp-green bg-bp-green/5'
                        }`}
                      >
                        <span className="text-[10px] text-bp-muted block mb-0.5">AI · {modeLabel(turn.mode || turn.revision_mode)}</span>
                        <p>{turn.assistant_explanation}</p>
                        {turn.changes_summary && turn.changes_summary.length > 0 && (
                          <ul className="mt-1 list-disc list-inside text-bp-muted">
                            {turn.changes_summary.map((c) => (
                              <li key={c}>{c}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="flex gap-2">
            <textarea
              className="flex-1 min-h-[56px] rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text p-2"
              placeholder={chatPlaceholder}
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (!busy) handleChat();
                }
              }}
            />
            <Button
              variant="secondary"
              className="text-xs self-end shrink-0"
              onClick={handleChat}
              disabled={busy === 'chat' || !chatMessage.trim()}
            >
              {busy === 'chat' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            </Button>
          </div>

          <div className="mt-3">
            <div className="flex items-center gap-2 mb-2 text-xs text-bp-muted">
              <MessageSquare className="w-3.5 h-3.5" /> 对话输出（最新回复）
            </div>
            <textarea
              readOnly
              className="w-full min-h-[140px] rounded-lg bg-bp-base/80 border border-bp-purple/30 text-xs text-bp-text p-3 font-sans leading-relaxed"
              placeholder="发送咨询问题后，AI 回复将显示在这里。例如：「报告中有几张图表？」"
              value={latestReply}
            />
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-bp-border">
          <div className="flex items-center gap-2 mb-2 text-xs text-bp-muted">
            <Edit3 className="w-3.5 h-3.5" /> 当前工作版本（human_modified_output）
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
            手动保存
          </Button>
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
              <History className="w-3.5 h-3.5" /> 修订快照 ({revisionHistory.length})
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {revisionHistory.slice().reverse().slice(0, 5).map((h) => (
                <div key={String(h.id || h.at)} className="text-xs text-bp-muted border border-bp-border rounded p-2">
                  <span className="text-bp-muted">{String(h.at || '')}</span>
                  {h.action ? ` · ${String(h.action)}` : ''}
                  {h.feedback ? ` · ${String(h.feedback)}` : ''}
                </div>
              ))}
            </div>
          </div>
        )}

        {(globalConstraints.length > 0 || recentFeedbackEntries.length > 0) && (
          <div className="mt-4 pt-4 border-t border-bp-border">
            <p className="text-xs font-medium text-bp-purple mb-2">项目全局约束</p>
            <p className="text-xs text-bp-muted mb-2">
              本阶段保存、修订或重跑时的反馈会自动写入全局约束，并注入后续 Pipeline 运行。
            </p>
            {globalConstraints.length > 0 && (
              <ul className="text-xs text-bp-muted space-y-1 max-h-28 overflow-y-auto mb-2">
                {globalConstraints.slice(-6).map((c) => (
                  <li key={c} className="line-clamp-2">• {c}</li>
                ))}
              </ul>
            )}
            {recentFeedbackEntries.length > 0 && (
              <p className="text-xs text-bp-muted">
                最近 {recentFeedbackEntries.length} 条 HITL 反馈已记录
              </p>
            )}
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
