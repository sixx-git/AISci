import { useMemo } from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MarkdownPreviewProps {
  content: string;
  className?: string;
}

/** 简陋但实用的 Markdown → JSX 渲染器（无需第三方依赖） */
export function MarkdownPreview({ content, className }: MarkdownPreviewProps) {
  const rendered = useMemo(() => renderMarkdown(content), [content]);

  return (
    <div className={cn('prose prose-invert prose-sm max-w-none', className)}>
      {rendered}
    </div>
  );
}

// -------------- 简易 Markdown 解析 --------------

type Block = { type: 'h1' | 'h2' | 'h3' | 'paragraph' | 'table' | 'list'; content: string; tableHeaders?: string[]; tableRows?: string[][] };

function renderMarkdown(md: string) {
  const blocks = parseBlocks(md);
  return blocks.map((b, i) => renderBlock(b, i));
}

function parseBlocks(md: string): Block[] {
  const lines = md.split('\n');
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // headings
    if (/^###\s/.test(line)) {
      blocks.push({ type: 'h3', content: line.replace(/^###\s*/, '') });
      i++;
      continue;
    }
    if (/^##\s/.test(line)) {
      blocks.push({ type: 'h2', content: line.replace(/^##\s*/, '') });
      i++;
      continue;
    }
    if (/^#\s/.test(line)) {
      blocks.push({ type: 'h1', content: line.replace(/^#\s*/, '') });
      i++;
      continue;
    }

    // table: starts with | and next line is a separator
    if (line.startsWith('|') && i + 1 < lines.length && /^\|[\s\-:|]+/.test(lines[i + 1])) {
      const headers = line.split('|').map(s => s.trim()).filter(Boolean);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].startsWith('|')) {
        rows.push(lines[i].split('|').map(s => s.trim()).filter(Boolean));
        i++;
      }
      blocks.push({ type: 'table', content: '', tableHeaders: headers, tableRows: rows });
      continue;
    }

    // list items (unordered for now)
    if (/^[\-\*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[\-\*]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[\-\*]\s*/, ''));
        i++;
      }
      blocks.push({ type: 'list', content: items.join('\n') });
      continue;
    }

    // numbered list
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s*/, ''));
        i++;
      }
      blocks.push({ type: 'list', content: items.join('\n') });
      continue;
    }

    // paragraph (skip empty lines)
    if (line.trim() === '') {
      i++;
      continue;
    }

    // blockquote / warning
    if (line.startsWith('>')) {
      const qLines: string[] = [];
      while (i < lines.length && lines[i].startsWith('>')) {
        qLines.push(lines[i].replace(/^>\s?/, ''));
        i++;
      }
      blocks.push({ type: 'paragraph', content: '___BLOCKQUOTE___' + qLines.join('\n') });
      continue;
    }

    // horizontal rule
    if (/^---+$/.test(line.trim())) {
      blocks.push({ type: 'paragraph', content: '___HR___' });
      i++;
      continue;
    }

    // ordinary paragraph
    blocks.push({ type: 'paragraph', content: line });
    i++;
  }

  return blocks;
}

function renderBlock(block: Block, key: number) {
  switch (block.type) {
    case 'h1':
      return <h1 key={key} className="text-2xl font-bold text-white mt-8 mb-4 pb-2 border-b border-gray-800">{inlineMarkup(block.content)}</h1>;
    case 'h2':
      return <h2 key={key} className="text-lg font-semibold text-white mt-6 mb-3">{inlineMarkup(block.content)}</h2>;
    case 'h3':
      return <h3 key={key} className="text-base font-semibold text-gray-200 mt-4 mb-2">{inlineMarkup(block.content)}</h3>;

    case 'table':
      return (
        <div key={key} className="overflow-x-auto mb-4">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                {block.tableHeaders?.map((h, hi) => (
                  <th key={hi} className="py-2 px-3 text-gray-400 font-medium text-xs">{inlineMarkup(h)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.tableRows?.map((row, ri) => (
                <tr key={ri} className="border-b border-gray-800/50 last:border-0">
                  {row.map((cell, ci) => (
                    <td key={ci} className="py-2 px-3 text-gray-300 text-xs">{inlineMarkup(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    case 'list': {
      const items = block.content.split('\n');
      return (
        <ul key={key} className="list-disc list-inside space-y-1 mb-4 text-sm text-gray-300">
          {items.map((item, idx) => (
            <li key={idx}>{inlineMarkup(item)}</li>
          ))}
        </ul>
      );
    }

    case 'paragraph': {
      if (block.content === '___HR___') {
        return <hr key={key} className="my-6 border-gray-800" />;
      }
      if (block.content.startsWith('___BLOCKQUOTE___')) {
        const text = block.content.slice('___BLOCKQUOTE___'.length);
        const isWarning = text.includes('⚠️');
        return (
          <div key={key} className={cn(
            'my-4 p-3 rounded-lg border text-sm',
            isWarning
              ? 'bg-amber-500/5 border-amber-500/20 text-amber-300/90'
              : 'bg-gray-900/70 border-gray-700 text-gray-400 italic',
          )}>
            {isWarning && <AlertTriangle className="w-4 h-4 text-amber-400 inline-block mr-1.5 -mt-0.5" />}
            {inlineMarkup(text)}
          </div>
        );
      }
      return <p key={key} className="text-sm text-gray-300 leading-relaxed mb-4">{inlineMarkup(block.content)}</p>;
    }

    default:
      return null;
  }
}

/** 行内格式：粗体、斜体 */
function inlineMarkup(text: string): React.ReactNode {
  // split on **bold** or *italic*  (simple approach)
  const parts = text.split(/(\*\*.*?\*\*|\*[^*].*?\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i} className="text-white font-semibold">{p.slice(2, -2)}</strong>;
    }
    if (p.startsWith('*') && p.endsWith('*') && !p.startsWith('**')) {
      return <em key={i} className="italic text-gray-400">{p.slice(1, -1)}</em>;
    }
    return p;
  });
}