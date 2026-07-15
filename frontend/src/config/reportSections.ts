/** 报告章节 — 与 latex_template/scientific_plan_template.tex 对齐 */
export const REPORT_SECTION_OPTIONS = [
  { key: 'paper_title', label: '论文标题' },
  { key: 'paper_abstract', label: '摘要' },
  { key: 'problem_statement', label: '待研究问题' },
  { key: 'rationale', label: '解决思路' },
  { key: 'technical_details', label: '必要的技术手段' },
  { key: 'datasets', label: '数据集' },
  { key: 'source', label: '历史数据' },
  { key: 'target', label: '目标数据' },
  { key: 'methods', label: '方法论' },
  { key: 'experiments', label: '迭代实验' },
  { key: 'results', label: '实验结果' },
  { key: 'references', label: '参考文献' },
] as const;

export type ReportSectionKey = (typeof REPORT_SECTION_OPTIONS)[number]['key'];
