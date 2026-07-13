export interface LiteratureImportStats {
  searchedCount: number | null;
  importedCount: number | null;
  selectedCount: number | null;
  factsCount: number | null;
}

function readCount(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
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

  if (searchedCount == null && importedCount == null && factsCount == null) {
    return null;
  }

  return { searchedCount, importedCount, selectedCount, factsCount };
}

export function formatLiteratureStatsSummary(stats: LiteratureImportStats): string {
  const searched = stats.searchedCount ?? '—';
  const imported = stats.importedCount ?? '—';
  const parts = [`检索 ${searched} 篇 / 入库 ${imported} 篇`];
  if (stats.factsCount != null) {
    parts.push(`${stats.factsCount} 条事实`);
  }
  return parts.join(' · ');
}
