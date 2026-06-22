import type { BackendHypothesis, BackendEvidence } from '@/services/hypothesisService';
import type { DetailedHypothesis, EvidenceItem } from '@/types';

export function mapBackendHypothesisToDetailed(h: BackendHypothesis): DetailedHypothesis {
  return {
    id: h.id,
    title: h.hypothesis || '未命名假设',
    content: h.hypothesis || '',
    reasoning: h.rationale || '',
    evidenceCount: (h.supporting_fact_ids || []).length + (h.data_evidence_ids || []).length,
    novelty: 80,
    verifiability: h.testability === 'high' ? 88 : h.testability === 'low' ? 55 : 75,
    dataAvailability: h.required_data === 'high' ? 85 : h.required_data === 'low' ? 55 : 70,
    overallScore: Math.round((h.confidence || 0.5) * 100),
    riskWarning: h.risk || '',
    isPrimary: h.priority === 1,
    status: (h.status === 'testing' || h.status === 'accepted' || h.status === 'confirmed')
      ? 'confirmed' : 'draft',
    alignment_score: h.alignment_score ?? undefined,
    off_topic: h.off_topic ?? undefined,
    off_topic_reason: h.off_topic_reason ?? undefined,
    matched_keywords: h.matched_keywords ?? undefined,
    missing_keywords: h.missing_keywords ?? undefined,
    domain_conflict_keywords: h.domain_conflict_keywords ?? undefined,
    evidenceLevel: h.evidence_level || 'medium',
    question_alignment: h.question_alignment ?? undefined,
    dataset_field_refs: h.dataset_field_refs ?? undefined,
    data_evidence_ids: h.data_evidence_ids ?? undefined,
    validation_target: h.validation_target ?? undefined,
    expected_measurable_effect: h.expected_measurable_effect ?? undefined,
    supporting_fact_ids: h.supporting_fact_ids ?? undefined,
  };
}

export function mapBackendEvidenceToItem(e: BackendEvidence): EvidenceItem {
  let stance: EvidenceItem['stance'];
  let reliability_score: number | undefined;
  try {
    if (e.extra_metadata) {
      const meta = JSON.parse(e.extra_metadata);
      stance = meta.stance;
      reliability_score = meta.reliability_score;
    }
  } catch {
    /* ignore */
  }
  return {
    id: e.id,
    project_id: e.project_id,
    hypothesis_id: e.hypothesis_id,
    document_id: e.document_id,
    chunk_id: e.chunk_id,
    fact_text: e.fact_text,
    quote_text: e.quote_text,
    page_number: e.page_number,
    relevance_score: e.relevance_score,
    source_title: e.source_title,
    created_at: e.created_at,
    stance,
    reliability_score,
  };
}
