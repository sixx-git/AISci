import { SideDrawer } from '@/components/overview/SideDrawer';
import { LoadingState } from '@/components/workspace/LoadingState';
import type { ContextSnapshot, SnapshotItem } from '@/lib/overviewSubmission';

interface ContextEngineeringDrawerProps {
  open: boolean;
  loading?: boolean;
  snapshot: ContextSnapshot | null;
  onClose: () => void;
}

const CHANNELS: Array<{
  key: keyof ContextSnapshot['channels'];
  title: string;
  hint: string;
}> = [
  { key: 'question', title: '科学问题', hint: '进入各阶段提示词的研究问题原文' },
  { key: 'opposing_evidence', title: '反对证据', hint: '反证检索、矛盾点与评审弱点' },
  { key: 'constraints', title: '关键约束', hint: '项目约束、边界与知识缺口' },
  { key: 'history', title: '历史结果', hint: '阶段执行与门禁质量趋势' },
  { key: 'feedback', title: '反馈信息', hint: '人工在回路意见，注入后续轮次' },
];

function ItemList({ items, empty, limit = 8 }: { items: SnapshotItem[]; empty: string; limit?: number }) {
  if (items.length === 0) {
    return <p className="text-xs text-bp-muted">{empty}</p>;
  }
  const shown = items.slice(0, limit);
  return (
    <ul className="space-y-2">
      {shown.map((item, idx) => (
        <li
          key={`${item.id || item.title}-${idx}`}
          className="text-sm text-bp-text leading-relaxed"
        >
          <span>{item.title}</span>
          {(item.source || item.detail) && (
            <span className="block text-xs text-bp-muted mt-0.5">
              {[item.source, item.detail].filter(Boolean).join(' · ')}
            </span>
          )}
        </li>
      ))}
      {items.length > shown.length && (
        <li className="text-xs text-bp-muted">另有 {items.length - shown.length} 条，已写入下载 JSON</li>
      )}
    </ul>
  );
}

export function ContextEngineeringDrawer({
  open,
  loading = false,
  snapshot,
  onClose,
}: ContextEngineeringDrawerProps) {
  return (
    <SideDrawer
      open={open}
      title="上下文工程"
      subtitle="对照提交模板 P7：科学问题、已有证据、反对证据、关键约束、历史结果与反馈如何进入 Qwen"
      onClose={onClose}
    >
      {loading && <LoadingState compact message="正在加载本项目上下文…" />}
      {!loading && !snapshot && (
        <p className="text-sm text-bp-muted">未能加载运行详情，请稍后重试。</p>
      )}
      {!loading && snapshot && (
        <div className="space-y-6">
          <section>
            <h3 className="text-sm font-semibold text-bp-text mb-2">Qwen 在本项目中的实际作用</h3>
            <div className="overflow-x-auto rounded-bp border border-bp-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-bp-panel text-bp-muted text-left">
                    <th className="px-3 py-2 font-medium w-40">内容</th>
                    <th className="px-3 py-2 font-medium">本项目实际做法</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.qwen.map((row) => (
                    <tr key={row.label} className="border-t border-bp-border">
                      <td className="px-3 py-2 text-bp-muted align-top">{row.label}</td>
                      <td className="px-3 py-2 text-bp-text leading-relaxed">{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-bp-text mb-2">文献库存盘点</h3>
            <p className="text-xs text-bp-muted mb-3 leading-relaxed">
              白名单分两层展示。强置信核心事实可供假设引用。检索 chunk、证据原文、论文与引用映射因版权限制无法直接下载或切片使用，故由大模型据此生成辅助性非核心事实一并列出。引用门禁仍只允许核心层的 fact_id。
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {([
                ['核心白名单', snapshot.literature.core_facts],
                ['辅助白名单', snapshot.literature.auxiliary_facts],
                ['证据原文', snapshot.literature.evidence_quotes],
                ['来源论文', snapshot.literature.source_papers],
                ['引用映射', snapshot.literature.citation_map],
                ['检索候选', snapshot.literature.search_candidates],
                ['本轮入库', snapshot.literature.imported],
                ['不确定点', snapshot.literature.uncertain_points],
              ] as Array<[string, number]>).map(([label, value]) => (
                <div key={label} className="rounded-bp border border-bp-border bg-bp-panel/40 px-3 py-2 text-center">
                  <div className="text-lg font-semibold text-bp-cyan">{value}</div>
                  <div className="text-[11px] text-bp-muted mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-bp-text">一次生成进入模型的上下文结构</h3>
            <div className="rounded-bp border border-bp-border bg-bp-panel/40 p-3 space-y-4">
              <div className="flex items-baseline justify-between gap-2">
                <h4 className="text-sm font-medium text-bp-text">已有证据（白名单事实）</h4>
                <span className="text-xs text-bp-muted">
                  核心 {snapshot.whitelist_core.length} · 辅助 {snapshot.whitelist_auxiliary.length}
                </span>
              </div>
              <p className="text-xs text-bp-muted">
                核心层通过校验、可被假设引用。辅助层不直接使用受版权保护的原文或切片，而是由大模型基于检索材料生成的非核心事实。
              </p>
              <div>
                <h5 className="text-xs font-medium text-bp-cyan mb-2">强置信核心白名单事实</h5>
                <ItemList
                  items={snapshot.whitelist_core}
                  empty="尚无通过校验的核心事实"
                />
              </div>
              <div>
                <h5 className="text-xs font-medium text-bp-cyan mb-2">辅助性非核心白名单事实</h5>
                <ItemList
                  items={snapshot.whitelist_auxiliary}
                  empty="尚无大模型生成的辅助性非核心事实"
                  limit={10}
                />
              </div>
            </div>
            {CHANNELS.map((ch) => (
              <div key={ch.key} className="rounded-bp border border-bp-border bg-bp-panel/40 p-3">
                <div className="flex items-baseline justify-between gap-2 mb-2">
                  <h4 className="text-sm font-medium text-bp-text">{ch.title}</h4>
                  <span className="text-xs text-bp-muted">{snapshot.channels[ch.key].length} 条</span>
                </div>
                <p className="text-xs text-bp-muted mb-2">{ch.hint}</p>
                <ItemList items={snapshot.channels[ch.key]} empty="本通道暂无记录" />
              </div>
            ))}
          </section>
        </div>
      )}
    </SideDrawer>
  );
}
