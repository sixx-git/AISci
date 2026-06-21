import { FileText, Download, Copy, FileDown } from 'lucide-react';
import { Card } from './Card';

export type ExportType = 'generate' | 'markdown' | 'latex' | 'pdf' | 'copy';

interface ExportActionsProps {
  onAction: (action: ExportType) => void;
  className?: string;
}

const actions: { type: ExportType; icon: typeof FileText; label: string }[] = [
  { type: 'generate', icon: FileText,   label: '生成报告' },
  { type: 'markdown', icon: Download,   label: '导出 Markdown' },
  { type: 'latex',    icon: FileDown,   label: '导出 LaTeX' },
  { type: 'pdf',      icon: FileDown,   label: '导出 PDF' },
  { type: 'copy',     icon: Copy,       label: '复制内容' },
];

export function ExportActions({ onAction, className }: ExportActionsProps) {
  return (
    <Card className={className}>
      <h3 className="text-sm font-semibold text-white mb-3">报告操作</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {actions.map((act) => {
          const Icon = act.icon;
          return (
            <button
              key={act.type}
              onClick={() => onAction(act.type)}
              className={`
                flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium
                border border-gray-700 hover:border-gray-600
                transition-colors duration-150
                ${act.type === 'generate'
                  ? 'bg-primary-500/10 text-primary-400 border-primary-500/30 hover:bg-primary-500/20'
                  : 'bg-gray-900/70 text-gray-300 hover:bg-gray-800'}
              `}
            >
              <Icon className="w-3.5 h-3.5" />
              {act.label}
            </button>
          );
        })}
      </div>
    </Card>
  );
}