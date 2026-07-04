import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Cpu, FileCode, RotateCcw, AlertTriangle,
  ChevronDown, ChevronRight, Clock, Hash,
  Puzzle,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import type { AgentNodeData } from '@/types';

interface AgentDetailPanelProps {
  node: AgentNodeData | null;
  onRerun?: (id: string) => void;
}

/** 可折叠区域 */
function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-bp-muted hover:text-bp-text mb-2"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        {title}
      </button>
      {open && children}
    </div>
  );
}

/** 格式化 JSON 展示 */
function JsonBlock({ data }: { data: unknown }) {
  if (data === null || data === undefined) {
    return <span className="text-sm text-bp-muted italic">无数据</span>;
  }
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return (
    <pre className="text-xs text-bp-muted font-mono whitespace-pre-wrap bg-bp-base/60 border border-bp-border rounded-bp p-3 max-h-48 overflow-y-auto">
      {text}
    </pre>
  );
}

/** 格式化耗时（毫秒 → 可读） */
function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

function SkillOutputsCard({ skillOutputs }: { skillOutputs?: Record<string, unknown> }) {
  if (!skillOutputs || Object.keys(skillOutputs).length === 0) return null;

  const entries = Object.entries(skillOutputs);

  function renderPreliminaryAnalysisData(skillName: string, s: Record<string, unknown>) {
    const sData = s.data as Record<string, unknown> | undefined;
    if (!sData) return null;

    const items: { label: string; value: string; extra?: string }[] = [];

    if (sData.data_source_flag && typeof sData.data_source_flag === 'string') {
      const flagMap: Record<string, string> = { real_data: '真实数据', simulated: '模拟数据', no_data: '无数据' };
      items.push({ label: '数据来源', value: flagMap[sData.data_source_flag] || sData.data_source_flag });
    }

    if (sData.summary_statistics && typeof sData.summary_statistics === 'object') {
      const ss = sData.summary_statistics as Record<string, unknown>;
      items.push({ label: '分析数据源', value: `${Object.keys(ss).length} 个` });
    }

    if (Array.isArray(sData.feature_vectors)) {
      const fv = sData.feature_vectors as unknown[];
      const totalFeats: number = fv.reduce((sum: number, f) => {
        const features = (f as Record<string, unknown>).features;
        return sum + (Array.isArray(features) ? features.length : 0);
      }, 0);
      items.push({ label: '特征向量', value: `${fv.length} 组`, extra: totalFeats > 0 ? `共 ${totalFeats} 个特征` : undefined });
    }

    if (Array.isArray(sData.plots)) {
      items.push({ label: '图表规格', value: `${sData.plots.length} 个 (供 ReportChartGeneration 使用)` });
    }

    if (Array.isArray(sData.correlations)) {
      const corrs = sData.correlations as unknown[];
      const strongCorrs = corrs.filter((c: unknown) => {
        const r = (c as Record<string, unknown>).pearson_r;
        return typeof r === 'number' && Math.abs(r) > 0.7;
      }).length;
      items.push({ label: '相关性分析', value: `${corrs.length} 对`, extra: strongCorrs > 0 ? `${strongCorrs} 对强相关 (|r|>0.7)` : undefined });
    }

    if (Array.isArray(sData.anomalies)) {
      items.push({ label: '异常点检测', value: `${sData.anomalies.length} 个 (>2.5σ)` });
    }

    if (sData.image_summary && typeof sData.image_summary === 'object') {
      const isum = sData.image_summary as Record<string, unknown>;
      if (isum.total_images && Number(isum.total_images) > 0) {
        items.push({ label: '图像数据', value: `${isum.total_images} 张` });
      }
    }

    if (sData.time_series_summary && typeof sData.time_series_summary === 'object') {
      const tsum = sData.time_series_summary as Record<string, unknown>;
      if (tsum.total_series && Number(tsum.total_series) > 0) {
        items.push({ label: '时序数据', value: `${tsum.total_series} 条序列` });
      }
    }

    if (sData.preliminary_result && typeof sData.preliminary_result === 'object') {
      const pr = sData.preliminary_result as Record<string, unknown>;
      if (Array.isArray(pr.recommendations)) {
        items.push({ label: '分析建议', value: `${pr.recommendations.length} 条` });
      }
    }

    if (items.length === 0) return null;

    return (
      <div className="mb-2">
        <p className="text-xs text-bp-purple/70 font-medium mb-1.5 uppercase tracking-wide">{formatSkillName(skillName)} 分析输出</p>
        <div className="space-y-1">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2 px-2 py-1 rounded bg-bp-base/50 border border-bp-border/50">
              <span className="text-xs text-bp-muted shrink-0">{item.label}</span>
              <span className="text-xs text-bp-text font-medium">{item.value}</span>
              {item.extra && <span className="text-xs text-bp-muted">{item.extra}</span>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  function renderChartGenerationData(skillName: string, s: Record<string, unknown>) {
    const sData = s.data as Record<string, unknown> | undefined;
    if (!sData) return null;

    const items: { label: string; value: string }[] = [];

    if (sData.total_charts != null) {
      items.push({ label: '生成图表', value: `${sData.total_charts} 张` });
    }

    if (Array.isArray(sData.charts)) {
      const charts = sData.charts as unknown[];
      const realCount = charts.filter((c: unknown) => {
        const ch = c as Record<string, unknown>;
        return ch.is_generated_from_real_data === true;
      }).length;
      items.push({ label: '基于真实数据', value: `${realCount} 张` });

      const typeCounts: Record<string, number> = {};
      charts.forEach((c: unknown) => {
        const ch = c as Record<string, unknown>;
        const t = String(ch.type || 'unknown');
        typeCounts[t] = (typeCounts[t] || 0) + 1;
      });
      const typeSummary = Object.entries(typeCounts).map(([t, n]) => `${t}×${n}`).join(', ');
      if (typeSummary) {
        items.push({ label: '图表类型', value: typeSummary });
      }
    }

    if (items.length === 0) return null;

    return (
      <div className="mb-2">
        <p className="text-xs text-bp-green/70 font-medium mb-1.5 uppercase tracking-wide">{formatSkillName(skillName)} 图表输出</p>
        <div className="space-y-1">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2 px-2 py-1 rounded bg-bp-base/50 border border-bp-border/50">
              <span className="text-xs text-bp-muted shrink-0">{item.label}</span>
              <span className="text-xs text-bp-text font-medium">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <Puzzle className="w-4 h-4 text-bp-purple" />
        <h4 className="text-sm font-semibold text-bp-purple">Skill 适配层输出</h4>
      </div>
      <div className="space-y-2">
        {entries.map(([skillName, skillData]) => {
          const s = skillData as Record<string, unknown>;
          const sSuccess = s?.success;
          const sWarnings = (s?.warnings as string[]) || [];
          const sErrors = (s?.errors as string[]) || [];

          const isPreliminary = skillName === 'preliminary_analysis';
          const isChartGeneration = skillName === 'report_chart_generation';

          // 嵌套 hypothesis_novelty_review 等聚合类型
          const isAggregated = s && !('success' in s) && typeof s === 'object';

          if (isAggregated) {
            return (
              <CollapsibleSection key={skillName} title={formatSkillName(skillName)} defaultOpen={false}>
                <div className="space-y-1.5">
                  {Object.entries(s).map(([k, v]) => {
                    const vd = v as Record<string, unknown>;
                    return (
                      <div key={k} className="flex items-center justify-between px-2 py-1 rounded bg-bp-base/50 border border-bp-border/50">
                        <span className="text-xs text-bp-muted">{k}</span>
                        <span className={cn(
                          'text-xs font-medium',
                          vd?.success === true ? 'text-bp-green' :
                          vd?.success === false ? 'text-danger-400' : 'text-bp-muted',
                        )}>
                          {vd?.success === true ? '✓' : vd?.success === false ? '✗' : '—'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CollapsibleSection>
            );
          }

          return (
            <CollapsibleSection key={skillName} title={formatSkillName(skillName)} defaultOpen={isPreliminary}>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'text-xs px-1.5 py-0.5 rounded font-medium',
                    sSuccess === true ? 'bg-bp-green/10 text-bp-green' : 'bg-danger-500/10 text-danger-400',
                  )}>
                    {sSuccess === true ? '成功' : sSuccess === false ? '失败' : '未知'}
                  </span>
                </div>

                {isPreliminary && renderPreliminaryAnalysisData(skillName, s)}
                {isChartGeneration && renderChartGenerationData(skillName, s)}

                {sWarnings.length > 0 && (
                  <div className="space-y-0.5">
                    {sWarnings.map((w, i) => (
                      <div key={i} className="flex items-start gap-1.5 text-xs">
                        <AlertTriangle className="w-3 h-3 text-bp-yellow shrink-0 mt-0.5" />
                        <span className="text-bp-yellow/80">{w}</span>
                      </div>
                    ))}
                  </div>
                )}
                {sErrors.length > 0 && (
                  <div className="space-y-0.5">
                    {sErrors.map((e, i) => (
                      <div key={i} className="flex items-start gap-1.5 text-xs">
                        <AlertTriangle className="w-3 h-3 text-danger-400 shrink-0 mt-0.5" />
                        <span className="text-danger-400/80">{e}</span>
                      </div>
                    ))}
                  </div>
                )}
                {!isPreliminary && !isChartGeneration && sWarnings.length === 0 && sErrors.length === 0 && (
                  <p className="text-xs text-bp-muted">无警告或错误</p>
                )}
              </div>
            </CollapsibleSection>
          );
        })}
      </div>
    </Card>
  );
}

function formatSkillName(key: string): string {
  const map: Record<string, string> = {
    pdf_evidence_extraction: 'PDF 证据提取',
    arxiv_search: 'arXiv 检索',
    citation_grounding: '引用真实性验证',
    hypothesis_novelty_review: '假设新颖性审查',
    experiment_sanity_check: '实验真实性检查',
  };
  return map[key] || key.replace(/_/g, ' ');
}

export function AgentDetailPanel({ node, onRerun }: AgentDetailPanelProps) {
  const hasRealData = !!(node?.input_data || node?.output_data || node?.model_parameters || node?.prompt_used);

  if (!node) {
    return (
      <Card className="h-full flex flex-col items-center justify-center text-center py-16">
        <Cpu className="w-16 h-16 text-bp-border mx-auto mb-4" />
        <p className="text-bp-muted">点击左侧智能体节点查看详情</p>
      </Card>
    );
  }

  const isFailed = node.status === 'failed';
  const showHumanReview = node.status === 'human_review_required' || node.status === 'human_review';

  return (
    <div className="space-y-4">
      {/* ────── 智能体头部 ────── */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-bp bg-bp-cyan-tint border border-bp-cyan/20 flex items-center justify-center">
              <node.icon className="w-5 h-5 text-bp-cyan" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-bp-text">{node.name}</h3>
              <p className="text-xs text-bp-muted">{node.shortDesc}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {node.duration !== null && node.status !== 'pending' && node.status !== 'running' && (
              <span className="text-xs text-bp-muted flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {formatDuration(node.duration)}
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              icon={<RotateCcw className="w-3.5 h-3.5" />}
              onClick={() => onRerun?.(node.id)}
              disabled={node.status === 'running'}
              title="仅重新运行当前智能体，保留上游结果，不重启全流程"
            >
              重新运行本阶段
            </Button>
          </div>
        </div>

        {/* 失败 / 需人工审查 提示 */}
        {isFailed && node.error_message && (
          <div className="p-3 bg-danger-500/10 border border-danger-500/30 rounded-bp flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-danger-400 shrink-0 mt-0.5" />
            <p className="text-xs text-danger-300 whitespace-pre-wrap">{node.error_message}</p>
          </div>
        )}
        {showHumanReview && (
          <div className="p-3 bg-bp-yellow/10 border border-bp-yellow/30 rounded-bp flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
            <p className="text-xs text-bp-yellow">数据采集已完成，请前往数据集页面上传文件后继续生成报告。</p>
          </div>
        )}
      </Card>

      {/* ────── 输入数据 ────── */}
      <Card title="输入数据" subtitle="上游节点传递的上下文信息">
        {hasRealData && node.input_data ? (
          <JsonBlock data={node.input_data} />
        ) : (
          <div className="p-3 bg-bp-base/70 border border-bp-border rounded-bp">
            <p className="text-sm text-bp-text whitespace-pre-wrap">{node.inputSummary}</p>
          </div>
        )}
      </Card>

      {/* ────── 输出结果 ────── */}
      <Card title="输出结果" subtitle="智能体处理后的结构化输出">
        <div className={cn(
          'p-3 rounded-bp border',
          isFailed ? 'bg-danger-500/5 border-danger-500/20' :
          node.status === 'completed' ? 'bg-bp-green/5 border-bp-green/20' :
          node.status === 'running' ? 'bg-bp-cyan-tint border-bp-cyan/20' :
          'bg-bp-base/70 border-bp-border',
        )}>
          {hasRealData && node.output_data ? (
            <JsonBlock data={node.output_data} />
          ) : (
            <p className={cn(
              'text-sm whitespace-pre-wrap',
              node.status === 'completed' ? 'text-bp-text' :
              node.status === 'running' ? 'text-bp-cyan' :
              'text-bp-muted italic',
            )}>
              {node.outputSummary}
            </p>
          )}
        </div>
      </Card>

      {/* ────── 运行日志（默认折叠） ────── */}
      <Card>
        <CollapsibleSection title={`运行日志 (${node.logs.length})`} defaultOpen={false}>
          {node.logs.length === 0 ? (
            <p className="text-sm text-bp-muted italic">暂无日志</p>
          ) : (
            <div className="space-y-0.5 max-h-48 overflow-y-auto">
              {node.logs.map((log, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-1.5 rounded text-xs font-mono hover:bg-bp-panel/50"
                >
                  <span className="text-bp-muted shrink-0 w-4">{idx + 1}</span>
                  <span className="text-bp-text">{log}</span>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>
      </Card>

      {/* ────── Skill 输出 ────── */}
      {node.output_data && typeof node.output_data === 'object' && 'skill_outputs' in node.output_data && (
        <SkillOutputsCard skillOutputs={(node.output_data as Record<string, unknown>).skill_outputs as Record<string, unknown> | undefined} />
      )}

      {/* ────── 技术信息（默认折叠） ────── */}
      <Card>
        <CollapsibleSection title="技术信息 · Prompt / 模型参数" defaultOpen={false}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-bp-muted" />
            <div>
              <div className="text-xs text-bp-muted">使用模型</div>
              <div className="text-xs text-bp-text font-mono">{node.model}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-bp-muted" />
            <div>
              <div className="text-xs text-bp-muted">Prompt 版本</div>
              <div className="text-xs text-bp-text font-mono">{node.promptVersion}</div>
            </div>
          </div>
          {node.token_count != null && (
            <div className="flex items-center gap-2">
              <Hash className="w-4 h-4 text-bp-muted" />
              <div>
                <div className="text-xs text-bp-muted">Token 消耗</div>
                <div className="text-xs text-bp-text font-mono">{node.token_count.toLocaleString()}</div>
              </div>
            </div>
          )}
        </div>

        {/* 真实 API 数据：Prompt & Model Parameters */}
        {hasRealData && (
          <div className="mt-4 pt-4 border-t border-bp-border space-y-3">
            {node.prompt_used && (
              <CollapsibleSection title="Prompt 内容" defaultOpen={false}>
                <pre className="text-xs text-bp-muted font-mono whitespace-pre-wrap bg-bp-base/60 border border-bp-border rounded-bp p-3 max-h-64 overflow-y-auto">
                  {node.prompt_used}
                </pre>
              </CollapsibleSection>
            )}
            {node.model_parameters && (
              <CollapsibleSection title="模型参数" defaultOpen={false}>
                <div className="p-3 bg-bp-base/60 border border-bp-border rounded-bp space-y-1.5">
                  {Object.entries(node.model_parameters).map(([k, v]) => (
                    <div key={k} className="flex items-baseline gap-2 text-xs">
                      <span className="text-bp-muted shrink-0">{k}:</span>
                      <span className="text-bp-text font-mono">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </CollapsibleSection>
            )}
          </div>
        )}
        </CollapsibleSection>
      </Card>
    </div>
  );
}