import { REPORT_SECTION_OPTIONS, type ReportSectionKey } from '@/config/reportSections';

/** 与 latex 模板 / build_latex_document 对齐的跳转配置 */
export interface LatexSectionJump {
  key: ReportSectionKey;
  label: string;
  /** 在 .tex 中定位用的正则（取首次匹配） */
  texPattern: RegExp;
  indent?: boolean;
}

const JUMP_BY_KEY: Record<ReportSectionKey, Omit<LatexSectionJump, 'key' | 'label'> & { label?: string }> = {
  paper_title: {
    texPattern: /\\title\s*\{/m,
  },
  paper_abstract: {
    texPattern: /\\begin\s*\{\s*abstract\s*\}/m,
  },
  problem_statement: {
    texPattern: /\\section\s*\{\s*待研究问题\s*\}/m,
  },
  rationale: {
    texPattern: /\\section\s*\{\s*解决思路\s*\}/m,
  },
  technical_details: {
    texPattern: /\\section\s*\{\s*必要的技术手段\s*\}/m,
  },
  datasets: {
    texPattern: /\\section\s*\{\s*数据集\s*\}/m,
  },
  source: {
    texPattern: /\\subsection\s*\{\s*历史数据\s*\}/m,
    indent: true,
  },
  target: {
    texPattern: /\\subsection\s*\{\s*目标数据\s*\}/m,
    indent: true,
  },
  methods: {
    texPattern: /\\section\s*\{\s*方法论\s*\}/m,
  },
  experiments: {
    // 模板章节名为「实验设计」
    label: '实验设计',
    texPattern: /\\section\s*\{\s*实验设计\s*\}/m,
  },
  results: {
    texPattern: /\\section\s*\{\s*实验结果\s*\}/m,
  },
  references: {
    texPattern: /\\begin\s*\{\s*thebibliography\s*\}/m,
  },
};

export const LATEX_SECTION_JUMPS: LatexSectionJump[] = REPORT_SECTION_OPTIONS.map((opt) => {
  const jump = JUMP_BY_KEY[opt.key];
  return {
    key: opt.key,
    label: jump.label || opt.label,
    texPattern: jump.texPattern,
    indent: jump.indent,
  };
});

export function findTexOffset(tex: string, pattern: RegExp): number {
  const m = pattern.exec(tex);
  return m ? m.index : -1;
}

export function offsetToLineCol(text: string, offset: number): { line: number; col: number } {
  const safe = Math.max(0, Math.min(offset, text.length));
  const before = text.slice(0, safe);
  const lines = before.split('\n');
  return { line: lines.length, col: (lines[lines.length - 1] || '').length + 1 };
}

/** 将 textarea 光标滚到指定字符偏移 */
export function jumpTextareaToOffset(ta: HTMLTextAreaElement, offset: number): void {
  const safe = Math.max(0, Math.min(offset, ta.value.length));
  ta.focus();
  ta.setSelectionRange(safe, safe);
  const { line } = offsetToLineCol(ta.value, safe);
  const style = window.getComputedStyle(ta);
  const lineHeight = Number.parseFloat(style.lineHeight) || 20;
  const paddingTop = Number.parseFloat(style.paddingTop) || 0;
  ta.scrollTop = Math.max(0, (line - 3) * lineHeight - paddingTop);
}
