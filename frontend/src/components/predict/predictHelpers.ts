/** pingfenbiao impact_report 字段解析（对齐原站 INDEX_HTML 逻辑） */

export function resolveCompositeScore(
  rating: Record<string, unknown> | undefined,
  fallbackTotal?: unknown,
): number | null {
  if (!rating) {
    const n = Number(fallbackTotal);
    return Number.isFinite(n) ? n : null;
  }
  if (rating.composite_score != null && !Number.isNaN(Number(rating.composite_score))) {
    return Number(rating.composite_score);
  }
  const totalMax = Number(rating.total_max ?? rating.max_score ?? 0);
  if (rating.composite_score_raw != null && totalMax > 0) {
    return (Number(rating.composite_score_raw) / totalMax) * 100;
  }
  const n = Number(fallbackTotal ?? rating.total_score);
  return Number.isFinite(n) ? n : null;
}

export function resolveImpactScore(impact: Record<string, unknown> | undefined): {
  score: number | null;
  max: number;
} {
  if (!impact) return { score: null, max: 30 };
  const cal = (impact.calibrated_total as Record<string, unknown> | undefined) || {};
  if (cal.score != null) return { score: Number(cal.score), max: Number(cal.max ?? 30) };
  if (impact.total_score != null) return { score: Number(impact.total_score), max: Number(impact.max_score ?? 30) };
  if (impact.impact_score != null) return { score: Number(impact.impact_score), max: 30 };
  return { score: null, max: 30 };
}

export interface DimScore {
  name: string;
  score: number;
  max: number;
  rationale?: string;
}

export function getDimensions(impact: Record<string, unknown> | undefined): DimScore[] {
  if (!impact) return [];
  const dims: DimScore[] = [];
  const push = (key: string, alt: string, name: string) => {
    const block = (impact[key] || impact[alt]) as Record<string, unknown> | undefined;
    if (!block || block.score == null) return;
    dims.push({
      name,
      score: Number(block.score),
      max: Number(block.max ?? 10),
      rationale: String(block.rationale || block.reason || ''),
    });
  };
  push('d1_text_quality', 'academic_reach', 'D1 文本质量');
  push('d2_reputation', 'venue_quality', 'D2 声誉');
  push('d3_future_potential', 'author_influence', 'D3 未来潜力');
  push('d4_bias_fairness', 'network_position', 'D4 偏差公平');
  return dims;
}

/** 对齐原站 .rb-S / .rb-A 等实心彩底白字徽章 */
export function ratingBadgeClass(rating: string): string {
  const r = (rating || 'N').toUpperCase();
  if (r === 'S') return 'bg-[#4caf50] text-white border-transparent';
  if (r === 'A') return 'bg-[#2196f3] text-white border-transparent';
  if (r === 'A-') return 'bg-[#00bcd4] text-white border-transparent';
  if (r === 'B') return 'bg-[#ff9800] text-white border-transparent';
  if (r === 'C') return 'bg-[#f44336] text-white border-transparent';
  if (r === 'D') return 'bg-[#9e9e9e] text-white border-transparent';
  return 'bg-[#666] text-white border-transparent';
}

export function dimBarColor(index: number): string {
  const colors = ['#2196f3', '#00bcd4', '#4caf50', '#ff9800'];
  return colors[index % colors.length];
}

export function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

export function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

export function str(v: unknown, fallback = ''): string {
  if (v == null) return fallback;
  return String(v);
}
