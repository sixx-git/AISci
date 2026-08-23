import { PipelineProgress, type PipelineProgressNode } from '@/components/PipelineProgress';
import { SideDrawer } from '@/components/overview/SideDrawer';
import { LoadingState } from '@/components/workspace/LoadingState';
import { EVENT_LABELS } from '@/components/ClosedLoopTimeline';
import type { RunFeedbackSnapshot, SnapshotItem } from '@/lib/overviewSubmission';
import type { ClosedLoopEvent } from '@/types';

function eventTitle(evt: ClosedLoopEvent): string {
  return EVENT_LABELS[evt.type] || evt.type;
}

function eventDetail(evt: ClosedLoopEvent): string {
  const parts: string[] = [];
  if (evt.summary) parts.push(String(evt.summary));
  if (evt.decision) parts.push(`决策 ${String(evt.decision)}`);
  if (typeof evt.overall === 'number') parts.push(`综合 ${evt.overall}`);
  if (evt.gap_count != null && String(evt.gap_count) !== '') parts.push(`缺口 ${String(evt.gap_count)} 条`);
  if (typeof evt.composite_score === 'number') parts.push(`分支分 ${evt.composite_score}`);
  if (evt.success === true) parts.push('执行成功');
  if (evt.success === false) parts.push('执行失败');
  if (evt.stage_label) parts.push(String(evt.stage_label));
  else if (evt.stage && EVENT_LABELS[String(evt.stage)]) parts.push(EVENT_LABELS[String(evt.stage)]);
  return [...new Set(parts.filter(Boolean))].join(' · ');
}

interface RunFeedbackDrawerProps {
  open: boolean;
  loading?: boolean;
  snapshot: RunFeedbackSnapshot | null;
  pipelineNodes: PipelineProgressNode[];
  onClose: () => void;
}

function FeedbackList({ title, items, empty }: { title: string; items: SnapshotItem[]; empty: string }) {
  return (
    <div className="rounded-bp border border-bp-border bg-bp-panel/40 p-3">
      <h4 className="text-sm font-medium text-bp-text mb-2">
        {title}
        <span className="text-xs text-bp-muted font-normal ml-2">{items.length}</span>
      </h4>
      {items.length === 0 ? (
        <p className="text-xs text-bp-muted">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 8).map((item, idx) => (
            <li key={`${item.title}-${idx}`} className="text-sm text-bp-text leading-relaxed">
              {item.title}
              {(item.source || item.detail) && (
                <span className="block text-xs text-bp-muted mt-0.5">
                  {[item.source, item.detail].filter(Boolean).join(' · ')}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RunFeedbackDrawer({
  open,
  loading = false,
  snapshot,
  pipelineNodes,
  onClose,
}: RunFeedbackDrawerProps) {
  return (
    <SideDrawer
      open={open}
      title="完整运行与反馈"
      subtitle="对照提交模板 P12：从接收科学问题到候选假设与研究计划，并标明反馈回流环节"
      onClose={onClose}
    >
      {loading && <LoadingState compact message="正在加载本项目运行记录…" />}
      {!loading && !snapshot && (
        <p className="text-sm text-bp-muted">未能加载运行详情，请稍后重试。</p>
      )}
      {!loading && snapshot && (
        <div className="space-y-6">
          <section>
            <h3 className="text-sm font-semibold text-bp-text mb-3">一次完整运行</h3>
            {pipelineNodes.length > 0 ? (
              <PipelineProgress nodes={pipelineNodes} />
            ) : (
              <p className="text-xs text-bp-muted">暂无阶段进度</p>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold text-bp-text mb-2">反馈回流</h3>
            <ul className="space-y-2">
              {snapshot.loops.map((loop) => (
                <li
                  key={loop.id}
                  className="flex items-start justify-between gap-3 rounded-bp border border-bp-border px-3 py-2"
                >
                  <div>
                    <p className="text-sm text-bp-text">{loop.label}</p>
                    <p className="text-xs text-bp-muted mt-0.5">
                      {loop.fromLabel} → {loop.toLabel}
                      {loop.evidence ? ` · ${loop.evidence}` : ''}
                    </p>
                  </div>
                  <span
                    className={
                      loop.fired
                        ? 'shrink-0 text-xs px-1.5 py-0.5 rounded-bp bg-bp-cyan-tint text-bp-cyan'
                        : 'shrink-0 text-xs px-1.5 py-0.5 rounded-bp bg-bp-panel text-bp-muted'
                    }
                  >
                    {loop.fired ? '本项目已触发' : '未触发'}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FeedbackList
              title="系统自动产生"
              items={snapshot.auto_feedback}
              empty="尚无自动门禁或闭环事件"
            />
            <FeedbackList
              title="研究者 / 团队调整"
              items={snapshot.human_feedback}
              empty="本运行尚未记录人工反馈"
            />
          </section>

          <section>
            <h3 className="text-sm font-semibold text-bp-text mb-2">失败与处理</h3>
            <div className="overflow-x-auto rounded-bp border border-bp-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-bp-panel text-bp-muted text-left">
                    <th className="px-3 py-2 font-medium">情况</th>
                    <th className="px-3 py-2 font-medium">处理</th>
                    <th className="px-3 py-2 font-medium">本项目</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.failures.map((row) => (
                    <tr key={row.situation} className="border-t border-bp-border">
                      <td className="px-3 py-2 text-bp-text align-top">
                        {row.situation}
                        <span className="block text-bp-muted mt-0.5">{row.detected}</span>
                      </td>
                      <td className="px-3 py-2 text-bp-text leading-relaxed align-top">{row.handling}</td>
                      <td className="px-3 py-2 align-top">
                        {row.occurred ? '已发生' : '未发生'}
                        {row.evidence && (
                          <span className="block text-bp-muted mt-0.5">{row.evidence}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {snapshot.events.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-bp-text mb-2">闭环事件（本项目已发生）</h3>
              <p className="text-xs text-bp-muted mb-2">
                下列均为运行中实际写入的事件，不是「未触发」。上方「反馈回流」里的未触发，指该条回流路径没有走到。
              </p>
              <ul className="space-y-2">
                {snapshot.events.slice(-8).reverse().map((evt, idx) => {
                  const detail = eventDetail(evt);
                  return (
                    <li
                      key={`${evt.type}-${evt.at ?? idx}`}
                      className="text-sm text-bp-text rounded-bp border border-bp-border px-3 py-2"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span>{eventTitle(evt)}</span>
                        <span className="shrink-0 text-xs px-1.5 py-0.5 rounded-bp bg-bp-cyan-tint text-bp-cyan">
                          已发生
                        </span>
                      </span>
                      {detail && (
                        <span className="block text-xs text-bp-muted mt-0.5">{detail}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
        </div>
      )}
    </SideDrawer>
  );
}
