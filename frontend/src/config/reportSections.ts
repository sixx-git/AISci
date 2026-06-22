/** 挑战杯 12 章节 — 报告局部修订 */
export const REPORT_SECTION_OPTIONS = [
  { key: 'paper_title', label: '1. Paper Title' },
  { key: 'paper_abstract', label: '2. Paper Abstract' },
  { key: 'problem_statement', label: '3. Problem Statement' },
  { key: 'rationale', label: '4. Rationale' },
  { key: 'technical_details', label: '5. Technical Details' },
  { key: 'datasets', label: '6. Datasets' },
  { key: 'source', label: '7. Source' },
  { key: 'target', label: '8. Target' },
  { key: 'methods', label: '9. Methods' },
  { key: 'experiments', label: '10. Experiments' },
  { key: 'results', label: '11. Results' },
  { key: 'references', label: '12. References' },
] as const;

export type ReportSectionKey = (typeof REPORT_SECTION_OPTIONS)[number]['key'];
