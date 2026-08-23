export interface LiteratureImportStats {
  searchedCount: number | null;
  importedCount: number | null;
  selectedCount: number | null;
  factsCount: number | null;
  coreFactsCount: number | null;
  auxiliaryFactsCount: number | null;
}

function readCount(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** RCS 软失败黄条：产品决策为界面删除（后端 warning 可保留审计）。 */
export function isRcsSoftFailWarning(warning: string): boolean {
  return /均未通过相关性截断|RCS/.test(warning);
}

/** 从文献挖掘阶段 output_data 提取「检索 / 入库」统计。 */
export function extractLiteratureStats(data: unknown): LiteratureImportStats | null {
  if (!data || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;

  const searchedCount =
    readCount(d.literature_search_count)
    ?? readCount(d.candidate_references_count)
    ?? (Array.isArray(d.retrieved_papers) ? d.retrieved_papers.length : null);

  const importedCount =
    readCount(d.literature_import_count)
    ?? readCount(d.imported_documents);

  const selectedCount = readCount(d.literature_selected_count);
  const factsCount = readCount(d.evidence_facts) ?? (Array.isArray(d.facts) ? d.facts.length : null);
  const coreFactsCount = readCount(d.core_facts_count);
  const auxiliaryFactsCount = readCount(d.auxiliary_facts_count);

  if (searchedCount == null && importedCount == null && factsCount == null) {
    return null;
  }

  return {
    searchedCount,
    importedCount,
    selectedCount,
    factsCount,
    coreFactsCount,
    auxiliaryFactsCount,
  };
}

export function formatLiteratureStatsSummary(stats: LiteratureImportStats): string {
  const searched = stats.searchedCount ?? '—';
  const imported = stats.importedCount ?? '—';
  const parts = [`检索 ${searched} 篇 / 入库 ${imported} 篇`];
  if (stats.factsCount != null) {
    const core = stats.coreFactsCount;
    const aux = stats.auxiliaryFactsCount;
    if (core != null && aux != null && (core > 0 || aux > 0)) {
      parts.push(`${stats.factsCount} 条事实（全文 ${core} · 摘要 ${aux}）`);
    } else {
      parts.push(`${stats.factsCount} 条事实`);
    }
  }
  return parts.join(' · ');
}
