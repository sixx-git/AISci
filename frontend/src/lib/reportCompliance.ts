import type { ComplianceCheck } from '@/types';

const PLACEHOLDER_MARKERS = [
  '缺少真实引用',
  '需先导入',
  '暂无真实文献',
  '证据链不足',
  '禁止虚构',
  '[待',
  '需补充文献库',
];

export function isPlaceholderReference(ref: string): boolean {
  const text = ref.trim().toLowerCase();
  if (text.length < 8) return true;
  return PLACEHOLDER_MARKERS.some((m) => text.includes(m.toLowerCase()));
}

export function parseReportReferences(raw: string | undefined | null): string[] {
  if (!raw?.trim()) return [];
  const text = raw.trim();
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.map(String).map((s) => s.trim()).filter(Boolean);
      }
    } catch {
      /* fall through */
    }
  }
  return text.split('\n').map((s) => s.trim()).filter(Boolean);
}

export function countRealReferences(raw: string | undefined | null): number {
  return parseReportReferences(raw).filter((r) => !isPlaceholderReference(r)).length;
}

/** 从 extra_metadata 提取合规检查结果（兼容嵌套与扁平结构） */
export function extractComplianceCheck(
  extraMeta: Record<string, unknown> | undefined | null,
): ComplianceCheck | undefined {
  if (!extraMeta || typeof extraMeta !== 'object') return undefined;

  const nested = extraMeta.compliance_check;
  if (nested && typeof nested === 'object' && Array.isArray((nested as ComplianceCheck).items)) {
    return nested as ComplianceCheck;
  }

  if (Array.isArray(extraMeta.items)) {
    return extraMeta as unknown as ComplianceCheck;
  }

  return undefined;
}

/** 当后端指标为 0 但正文 References 有内容时，做展示层兜底（不修改 items 状态） */
export function reconcileComplianceForDisplay(
  compliance: ComplianceCheck | undefined,
  referencesRaw: string | undefined | null,
): ComplianceCheck | undefined {
  if (!compliance) return compliance;
  const realRefCount = countRealReferences(referencesRaw);
  if (realRefCount === 0) return compliance;
  if ((compliance.references_verified ?? 0) > 0) return compliance;

  return {
    ...compliance,
    references_verified: Math.max(compliance.references_verified ?? 0, realRefCount),
    has_references: true,
    evidence_fact_count: Math.max(compliance.evidence_fact_count ?? 0, realRefCount > 0 ? 1 : 0),
  };
}
