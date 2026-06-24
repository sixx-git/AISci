import { CheckCircle, XCircle, AlertTriangle, ListTree } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ReportSection } from '@/types';

interface ReportTableOfContentsProps {
  sections: ReportSection[];
  className?: string;
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

/** 报告章节目录 — 对齐设计稿 N7Jsj 左栏 TOC */
export function ReportTableOfContents({ sections, className }: ReportTableOfContentsProps) {
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
              onClick={() => scrollToSection(section.label)}
              className="w-full flex items-start gap-2 px-2 py-1.5 rounded-bp text-left text-[11px] text-bp-muted hover:text-bp-text hover:bg-bp-panel/60 transition-colors"
              title={section.note}
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
