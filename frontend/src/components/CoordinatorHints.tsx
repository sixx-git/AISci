import { useState } from 'react';
import { Brain, AlertTriangle, AlertCircle, Info, Sparkles, RotateCcw, Eye, ChevronDown, ChevronRight, Wrench, XCircle, Clock, CheckCircle } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';

export interface ContentQualityIssue {
  chapter: string;
  type: 'garbled' | 'truncated' | 'repeated_punctuation';
  detail: string;
  sample?: string;
}

export interface ContentQualityResult {
  has_issues: boolean;
  issue_count: number;
  issues: ContentQualityIssue[];
  detail: string;
}

export interface CoordinatorHintExtra {
  quality_score?: number;
  publish_ready?: boolean;
  review_score?: number;
  content_quality?: ContentQualityResult;
}

export interface CoordinatorHint {
  id: string;
  stage: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  message: string;
  remediation: string | null;
  action: {
    type: 'hint' | 'auto' | 'pass';
    suggestion: string;
    description: string;
  };
  source: string;
  pattern_id?: string;
  extra?: CoordinatorHintExtra;
  fix_status?: 'completed' | 'failed' | 'running';
  fix_detail?: string;
  decision_status?: 'pending' | 'awaiting_user' | 'running' | 'completed' | 'rejected';
  await_stage?: string;
  rerun_stages?: string[];
  timestamp: string;
}

interface CoordinatorHintsProps {
  hints: CoordinatorHint[];
  onRerunStage?: (stage: string) => void;
  onViewDetail?: (hint: CoordinatorHint) => void;
  onEvidenceIterationDecision?: (hint: CoordinatorHint, decision: 'approve' | 'reject') => void;
  evidenceIterationLoading?: boolean;
  compact?: boolean;
}

const severityConfig: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode; label: string }> = {
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/40',
    icon: <AlertCircle className="w-4 h-4" />,
    label: '严重',
  },
  high: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/40',
    icon: <AlertTriangle className="w-4 h-4" />,
    label: '高',
  },
  medium: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    icon: <AlertTriangle className="w-4 h-4" />,
    label: '中',
  },
  low: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/40',
    icon: <Info className="w-4 h-4" />,
    label: '低',
  },
  info: {
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/40',
    icon: <Sparkles className="w-4 h-4" />,
    label: '信息',
  },
};

const stageLabelMap: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '可行性评估',
  iterative_experiment: '迭代实验',
  report_generation: '报告生成',
};

const issueTypeLabel: Record<string, string> = {
  garbled: '乱码',
  truncated: '截断',
  repeated_punctuation: '标点重复',
};

const issueTypeIcon: Record<string, React.ReactNode> = {
  garbled: <XCircle className="w-3 h-3 text-red-400" />,
  truncated: <AlertTriangle className="w-3 h-3 text-amber-400" />,
  repeated_punctuation: <AlertCircle className="w-3 h-3 text-orange-400" />,
};

// ── 内容质量详情展开面板 ──
function ContentQualityDetail({ quality }: { quality: ContentQualityResult }) {
  const [expanded, setExpanded] = useState(false);

  if (!quality || !quality.has_issues) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-cyan-light transition-colors"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {expanded ? '收起详情' : `查看详情 (${quality.issue_count} 个问题)`}
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          {quality.issues.map((issue, i) => (
            <div key={i} className="flex items-start gap-1.5 text-xs text-bp-muted pl-4 py-0.5">
              <span className="mt-0.5 shrink-0">{issueTypeIcon[issue.type] || <Info className="w-3 h-3" />}</span>
              <div>
                <span className="text-bp-text font-medium">{stageLabelMap[issue.chapter] || issue.chapter}</span>
                <span className="mx-1">·</span>
                <span className={issue.type === 'garbled' ? 'text-red-400' : issue.type === 'truncated' ? 'text-amber-400' : 'text-orange-400'}>
                  {issueTypeLabel[issue.type] || issue.type}
                </span>
                <span className="ml-1">{issue.detail}</span>
                {issue.sample && issue.sample.length > 0 && (
                  <div className="font-mono text-[10px] text-bp-muted/60 mt-0.5 bg-black/10 rounded px-1 py-0.5 truncate max-w-md">
                    {issue.sample}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 自动修复状态标签 ──
function AutoFixBadge({ remediation, fixStatus, fixDetail }: { remediation: string | null; fixStatus?: string; fixDetail?: string }) {
  if (remediation === 'auto_fix_report') {
    if (fixStatus === 'completed') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded-full" title={fixDetail}>
          <CheckCircle className="w-2.5 h-2.5" />
          已修复
        </span>
      );
    }
    if (fixStatus === 'failed') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded-full" title={fixDetail}>
          <XCircle className="w-2.5 h-2.5" />
          修复失败
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-bp-cyan bg-bp-cyan/10 px-1.5 py-0.5 rounded-full">
        <Wrench className="w-2.5 h-2.5" />
        修复中...
      </span>
    );
  }
  if (remediation === 'llm_analysis') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-full">
        <Clock className="w-2.5 h-2.5" />
        LLM 分析中
      </span>
    );
  }
  return null;
}

function EvidenceIterationDecisionBadge({ status }: { status?: CoordinatorHint['decision_status'] }) {
  if (!status || status === 'awaiting_user') return null;
  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-full">
        <Clock className="w-2.5 h-2.5" />
        等待可行性评估完成
      </span>
    );
  }
  if (status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-bp-cyan bg-bp-cyan/10 px-1.5 py-0.5 rounded-full">
        <RotateCcw className="w-2.5 h-2.5 animate-spin" />
        证据链迭代重跑中
      </span>
    );
  }
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded-full">
        <CheckCircle className="w-2.5 h-2.5" />
        迭代已完成
      </span>
    );
  }
  if (status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-bp-muted bg-bp-muted/10 px-1.5 py-0.5 rounded-full">
        已跳过迭代
      </span>
    );
  }
  return null;
}

export function CoordinatorHints({
  hints,
  onRerunStage,
  onViewDetail,
  onEvidenceIterationDecision,
  evidenceIterationLoading = false,
  compact = false,
}: CoordinatorHintsProps) {
  // 已通过检查（含自动修复完成）
  const passedHints = hints.filter(
    (h) => h.action?.type === 'pass' || (h.severity === 'info' && !h.remediation)
      || (h.remediation === 'auto_fix_report' && h.fix_status === 'completed')
  );
  // 待处理的问题（需要用户操作）
  const pendingHints = hints.filter(
    (h) => h.action?.type === 'hint' && h.source !== 'llm_analysis'
      && h.pattern_id !== 'hg_all_low_evidence',
  );
  const evidenceIterationHints = hints.filter(
    (h) => h.pattern_id === 'hg_all_low_evidence'
      || h.action?.suggestion === 'evidence_iteration_decision',
  );
  // 自动执行（含 LLM 分析结果，排除已完成的自动修复）
  const autoHints = hints.filter(
    (h) => (h.action?.type === 'auto' || h.source === 'llm_analysis')
      && !(h.remediation === 'auto_fix_report' && h.fix_status === 'completed')
  );
  const llmHints = autoHints.filter(
    (h) => h.source === 'llm_analysis' || h.source === 'llm_fallback' || h.source === 'anomaly_detected'
  );
  const predefinedAutoHints = autoHints.filter(
    (h) => h.source !== 'llm_analysis' && h.source !== 'llm_fallback' && h.source !== 'anomaly_detected'
  );

  const totalChecked = passedHints.length + pendingHints.length + autoHints.length;
  const hasIssues = pendingHints.length > 0 || autoHints.length > 0;
  const allPassed = totalChecked > 0 && !hasIssues;

  // 已检查的阶段列表（按预定义顺序排序）
  const stageOrder = [
    'problem_understanding', 'literature_mining', 'knowledge_gap',
    'hypothesis_generation', 'hypothesis_review', 'iterative_experiment',
    'report_generation',
  ];
  const checkedStageSet = new Set(hints.map((h) => h.stage));
  const passedStageSet = new Set(passedHints.map((h) => h.stage));
  const issueStageSet = new Set(
    [...pendingHints, ...autoHints, ...evidenceIterationHints].map((h) => h.stage)
  );

  // 渲染单个 hint 卡片
  const renderHintCard = (hint: CoordinatorHint, isLLM: boolean = false) => {
    const config = severityConfig[hint.severity] || severityConfig.info;
    const isContentQuality = hint.pattern_id === 'rg_content_quality';
    const qualityData = hint.extra?.content_quality;

    // 如果 hint 有 extra，在 message 中追加已修复的章节数
    let displayMessage = hint.message;
    if (hint.remediation === 'auto_fix_report' && qualityData) {
      displayMessage = `${hint.message} — 已自动修复 ${qualityData.issue_count} 个问题`;
    }

    return (
      <div
        key={hint.id}
        className={`border-l-2 ${config.border} ${config.bg} pl-3 pr-2 py-2 rounded-r ${isLLM ? 'border-l-blue-400 bg-blue-500/5' : ''}`}
      >
        <div className="flex items-center gap-2 text-xs text-bp-muted mb-1">
          <span>{config.icon}</span>
          <span className={config.color}>{config.label}</span>
          <span>·</span>
          <span>{stageLabelMap[hint.stage] || hint.stage}</span>
          {hint.source === 'llm_analysis' && (
            <>
              <span>·</span>
              <span className="text-blue-400">LLM 分析</span>
            </>
          )}
          {hint.source === 'llm_fallback' && (
            <>
              <span>·</span>
              <span className="text-bp-muted/60">兜底分析</span>
            </>
          )}
          <div className="ml-auto flex items-center gap-1">
            <EvidenceIterationDecisionBadge status={hint.decision_status} />
            <AutoFixBadge remediation={hint.remediation} fixStatus={hint.fix_status} fixDetail={hint.fix_detail} />
          </div>
        </div>
        <p className="text-sm text-bp-text">{displayMessage}</p>

        {/* 内容质量详情 */}
        {isContentQuality && qualityData && qualityData.has_issues && (
          <ContentQualityDetail quality={qualityData} />
        )}

        <p className="text-xs text-bp-cyan mt-1">
          {isLLM ? '⟳' : '⟳'} {hint.action.description}
        </p>

        {/* 操作按钮 — 仅对需要用户操作的提示显示 */}
        {!compact && (
          <div className="flex items-center gap-2 mt-2">
            {hint.action.suggestion === 'rerun_stage' && onRerunStage && (
              <Button
                variant="primary"
                size="sm"
                icon={<RotateCcw className="w-3 h-3" />}
                onClick={() => onRerunStage(hint.stage)}
              >
                重跑 {stageLabelMap[hint.stage] || hint.stage}
              </Button>
            )}
            {hint.action.suggestion === 'revise_report' && onViewDetail && (
              <Button
                variant="secondary"
                size="sm"
                icon={<Eye className="w-3 h-3" />}
                onClick={() => onViewDetail(hint)}
              >
                查看详情
              </Button>
            )}
            {hint.action.suggestion === 'evidence_iteration_decision'
              && hint.decision_status === 'awaiting_user'
              && onEvidenceIterationDecision && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<RotateCcw className="w-3 h-3" />}
                  disabled={evidenceIterationLoading}
                  onClick={() => onEvidenceIterationDecision(hint, 'approve')}
                >
                  同意迭代
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={evidenceIterationLoading}
                  onClick={() => onEvidenceIterationDecision(hint, 'reject')}
                >
                  不同意迭代
                </Button>
              </>
            )}
            {/* 自动执行提示：显示状态标签而非按钮 */}
            {hint.action.type === 'auto' && hint.action.suggestion !== 'fix_report'
              && hint.action.suggestion !== 'evidence_iteration_decision' && (
              <span className="text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded-full">
                ✅ 自动执行中
              </span>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-bp-cyan" />
          大家长 Agent
        </span>
      }
      subtitle="阶段检查与补救建议"
    >
      {hints.length === 0 ? (
        <div className="text-center py-4">
          <Brain className="w-6 h-6 mx-auto mb-2 opacity-30 text-bp-muted" />
          <p className="text-sm text-bp-muted">暂无待处理提示</p>
          <p className="text-xs text-bp-muted mt-1">
            Pipeline 运行后将自动显示检查结果
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* ── 进度概览 ── */}
          <div className="flex flex-wrap gap-1.5">
            {stageOrder.map((s) => {
              const label = stageLabelMap[s] || s;
              const isChecked = checkedStageSet.has(s);
              const isPassed = passedStageSet.has(s);
              const hasIssue = issueStageSet.has(s);
              return (
                <span
                  key={s}
                  className={`text-[10px] px-1.5 py-0.5 rounded-full border transition-colors ${
                    !isChecked
                      ? 'border-bp-muted/20 text-bp-muted/40'
                      : hasIssue
                      ? 'border-amber-500/40 text-amber-400 bg-amber-500/10'
                      : isPassed
                      ? 'border-green-500/40 text-green-400 bg-green-500/10'
                      : 'border-bp-cyan/30 text-bp-cyan bg-bp-cyan/10'
                  }`}
                >
                  {!isChecked && '⏳ '}
                  {hasIssue && '⚠ '}
                  {isPassed && '✓ '}
                  {label}
                </span>
              );
            })}
          </div>

          {/* ── 全部通过总结 ── */}
          {allPassed && (
            <div className="bg-green-500/5 border border-green-500/20 rounded p-3 text-center">
              <Sparkles className="w-5 h-5 mx-auto mb-1 text-green-400" />
              <p className="text-sm text-green-400 font-medium">
                已通过 {totalChecked} 项阶段检查
              </p>
              <p className="text-xs text-bp-muted mt-1">
                全部正常，无待处理问题
              </p>
            </div>
          )}

          {/* ── LLM 分析结果 ── */}
          {llmHints.length > 0 && (
            <div>
              <div className="text-xs text-blue-400 mb-2">🧠 LLM 分析</div>
              <div className="space-y-2">
                {llmHints.map((hint) => renderHintCard(hint, true))}
              </div>
            </div>
          )}

          {/* ── 自动执行（预定义规则） ── */}
          {predefinedAutoHints.length > 0 && (
            <div>
              <div className="text-xs text-bp-muted mb-2">⚡ 自动执行</div>
              <div className="space-y-2">
                {predefinedAutoHints.map((hint) => renderHintCard(hint))}
              </div>
            </div>
          )}

          {/* ── 证据链迭代决策 ── */}
          {evidenceIterationHints.length > 0 && (
            <div>
              <div className="text-xs text-amber-400 mb-2">🔗 证据链迭代</div>
              <div className="space-y-2">
                {evidenceIterationHints.map((hint) => renderHintCard(hint))}
              </div>
            </div>
          )}

          {/* ── 待处理提示 ── */}
          {pendingHints.length > 0 && (
            <div>
              <div className="text-xs text-bp-muted mb-2">💡 待处理提示</div>
              <div className="space-y-2">
                {pendingHints.map((hint) => renderHintCard(hint))}
              </div>
            </div>
          )}

          {/* ── 已通过的检查（折叠显示） ── */}
          {passedHints.length > 0 && !allPassed && (
            <div className="border-t border-bp-cyan-dim pt-2 mt-2">
              <div className="text-xs text-bp-muted mb-1">
                ✅ 已通过 {passedHints.length} 阶段检查
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}