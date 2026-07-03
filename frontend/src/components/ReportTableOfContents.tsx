import { CheckCircle, XCircle, AlertTriangle, ListTree } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ReportSection } from '@/types';

interface ReportTableOfContentsProps {
  sections: ReportSection[];
  className?: string;
  /** PDF 预览时无法按章节跳转，仅展示完成状态 */
  previewMode?: 'pdf' | 'markdown';
}

const statusConfig: Record<
  ReportSection['status'],
  { icon: typeof CheckCircle; className: string }
> = {
  completed: { icon: CheckCircle, className: 'text-bp-green' },
  missing: { icon: XCircle, className: 'text-danger-400' },
  human_review: { icon: AlertTriangle, className: 'text-bp-yellow' },
};

function scrollToSection(label: string) {
  const root = document.getElementById('report-markdown-preview');
  if (!root) return;
  const term = label.replace(/^\d+\.\s*/, '').trim().toLowerCase();
  for (const el of root.querySelectorAll('h1, h2, h3')) {
    if (el.textContent?.toLowerCase().includes(term)) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
  }
}

/** 报告章节目录 — 页面最左侧 TOC */
export function ReportTableOfContents({
  sections,
  className,
  previewMode = 'markdown',
}: ReportTableOfContentsProps) {
  return (
    <Card className={cn('p-3', className)}>
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-bp-border">
        <ListTree className="w-4 h-4 text-bp-cyan shrink-0" />
        <h3 className="text-xs font-semibold text-bp-text">章节目录</h3>
      </div>
      <nav
        aria-label="报告章节目录"
        className="space-y-0.5 max-h-[calc(100vh-360px)] overflow-y-auto scrollbar-thin scrollbar-thumb-bp-muted scrollbar-track-transparent"
      >
        {sections.map((section) => {
          const { icon: Icon, className: iconCls } = statusConfig[section.status];
          return (
            <button
              key={section.key}
              type="button"
              onClick={() => {
                if (previewMode === 'markdown') scrollToSection(section.label);
              }}
              className={cn(
                'w-full flex items-start gap-2 px-2 py-1.5 rounded-bp text-left text-xs text-bp-muted transition-colors',
                previewMode === 'markdown'
                  ? 'hover:text-bp-text hover:bg-bp-panel/60 cursor-pointer'
                  : 'cursor-default',
              )}
              title={
                previewMode === 'pdf'
                  ? `${section.note || section.label}（PDF 预览请滚动浏览）`
                  : section.note
              }
            >
              <Icon className={cn('w-3.5 h-3.5 shrink-0 mt-0.5', iconCls)} />
              <span className="leading-snug">{section.label}</span>
            </button>
          );
        })}
      </nav>
    </Card>
  );
}
