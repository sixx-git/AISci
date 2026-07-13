export type UploadRequirement = 'required' | 'optional' | 'skip_ok';

export interface ValidationDatasetRequirement {
  name?: string;
  description?: string;
  modality?: string;
  required_columns?: string[];
  upload_requirement?: UploadRequirement;
  upload_requirement_label?: string;
  download_url?: string;
  source_platform?: string;
  license?: string;
  role?: string;
}

export interface ValidationDataGuidance {
  summary?: string;
  adequacy_status?: string;
  mismatch_reasons?: string[];
  what_hypothesis_needs?: string[];
  what_uploaded_can_do?: string[];
  required_columns?: string[];
  dataset_requirements?: ValidationDatasetRequirement[];
  must_upload_count?: number;
  optional_upload_count?: number;
  skip_ok_count?: number;
  downloads_available_count?: number;
  next_steps?: string[];
  search_query_used?: string;
  discovery_notes?: string[];
}

export function extractValidationDataGuidance(data: unknown): ValidationDataGuidance | null {
  if (!data || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;
  const guidance = d.validation_data_guidance;
  if (!guidance || typeof guidance !== 'object') return null;
  const g = guidance as ValidationDataGuidance;
  if (!g.dataset_requirements?.length && !g.summary && !g.mismatch_reasons?.length) {
    return null;
  }
  return g;
}

export function formatValidationBlockedSummary(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;
  if (d.validation_status === 'blocked' || d.validation_blocked === true) {
    const guidance = extractValidationDataGuidance(data);
    if (guidance?.summary) {
      const must = guidance.must_upload_count ?? 0;
      const dl = guidance.downloads_available_count ?? 0;
      return `数据不匹配：${guidance.summary}${must > 0 ? ` · 需上传 ${must} 项` : ''}${dl > 0 ? ` · ${dl} 个下载地址` : ''}`;
    }
    if (typeof d.validation_blocked_reason === 'string' && d.validation_blocked_reason) {
      return `验证阻塞：${d.validation_blocked_reason}`;
    }
  }
  return null;
}
