import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface DataSpec {
  research_question?: string;
  scenario?: 'general' | 'ml_benchmark' | 'federated_learning';
  entities_of_interest?: string[];
  target_variables?: string[];
  column_synonyms?: Record<string, string[]>;
  dataset_keywords?: string[];
  domain_keywords?: string[];
  preferred_sources?: string[];
  merge_strategy_hint?: string;
  output_format?: string;
}

export interface ExtractionManifest {
  figure_id?: string;
  identification?: {
    method?: string;
    caption?: string;
    page?: number;
    chart_type?: string;
    image_path?: string;
  };
  extraction?: {
    tier?: string;
    method?: string;
    confidence?: number;
    limitations?: string[];
    rows_preview?: Array<Record<string, unknown>>;
  };
  validation?: {
    status?: string;
    checks?: string[];
    needs_manual_review?: boolean;
    included_in_merged_csv?: boolean;
  };
}

export interface DataAssetIndex {
  asset_id?: string;
  source_type?: string;
  source_title?: string;
  extraction_tier?: string;
  extraction_method?: string;
  confidence?: number;
  csv_path?: string;
}

export interface DataFinderRequirements {
  data_need?: string;
  target_variables?: string[];
  expected_metrics?: string[];
  domain_keywords?: string[];
  dataset_keywords?: string[];
  preferred_sources?: string[];
  output_format?: string;
  data_spec?: DataSpec;
  scenario?: string;
  entities_of_interest?: string[];
  merge_strategy_hint?: string;
}

export interface PaperExtraction {
  paper_id: string;
  source_title: string;
  data_links: string[];
  code_links: string[];
  supplementary_links: string[];
  tables_detected: Array<{ table_number?: string; caption?: string }>;
  figures_detected: Array<{ figure_number?: string; caption?: string }>;
  confidence: number;
}

export interface ExtractedTable {
  table_id: string;
  paper_id: string;
  source_title: string;
  page: number;
  caption: string;
  csv_path: string;
  columns: string[];
  quality_score: number;
  needs_review: boolean;
  extraction_method?: string;
}

export interface SchemaAlignment {
  table_id: string;
  original_columns: string[];
  standard_columns: string[];
  mapping: Record<string, string>;
  unmatched_columns: string[];
  scenario?: string;
  join_keys?: string[];
  merge_strategy?: string;
}

export interface ProvenanceRecord {
  source_type: string;
  source_title: string;
  paper_id: string;
  page?: number | null;
  table_or_figure: string;
  url?: string;
  extraction_method: string;
  confidence: number;
}

export interface DataAcquisitionStep {
  skipped?: boolean;
  tables?: number;
  rows?: number;
  imported?: number;
  candidates?: number;
  warnings?: string[];
  duration_ms?: number;
  error_code?: string | null;
}

export interface ReleaseGateReport {
  passed?: boolean;
  ready_for_report?: boolean;
  failed_ids?: string[];
  checks?: Array<{ id: string; label?: string; passed?: boolean }>;
}

export interface DataAcquisitionMeta {
  mode?: string;
  steps?: string[];
  stats?: {
    external_candidates?: number;
    tables?: number;
    merged_rows?: number;
    gap_rounds?: number;
    release_gate_passed?: boolean;
    total_duration_ms?: number;
  };
  step_details?: Record<string, DataAcquisitionStep>;
}

export interface ExternalCandidateItem {
  candidate_id?: string;
  source_platform?: string;
  dataset_name?: string;
  url?: string;
  description?: string;
  availability?: string;
  import_supported?: boolean;
  imported?: boolean;
  user_upload_status?: string;
  user_upload_filename?: string;
  user_upload_error?: string;
  linked_table_id?: string;
}

export interface DataFinderResult {
  project_id: string;
  project_mode?: string;
  data_spec?: DataSpec;
  data_requirements?: DataFinderRequirements;
  paper_extractions?: PaperExtraction[];
  external_candidates?: ExternalCandidateItem[];
  figures?: Array<Record<string, unknown> & {
    extraction_manifest?: ExtractionManifest;
    image_path?: string;
  }>;
  assets_index?: DataAssetIndex[];
  extracted_tables?: ExtractedTable[];
  alignments?: SchemaAlignment[];
  provenance?: ProvenanceRecord[];
  merged?: {
    merge_id?: string;
    merged_csv_path?: string;
    cleaned_csv_path?: string;
    row_count?: number;
    columns?: string[];
    cleaning_report?: Record<string, unknown>;
  } | null;
  coverage_report?: CoverageReport;
  analysis_bundle?: AnalysisBundleMeta;
  entity_alignment?: {
    match_rate?: number;
    skipped?: boolean;
    alignment_warnings?: string[];
  };
  warnings?: string[];
  updated_at?: string;
  data_acquisition?: DataAcquisitionMeta;
  gap_enrichment?: {
    skipped?: boolean;
    round?: number;
    score_before?: number;
    score_after?: number;
    data_spec_score_before?: number;
    data_spec_score_after?: number;
    queries?: string[];
  };
  literature_discovery?: {
    imported?: number;
    query?: string;
    fallback_source?: string;
    pdf_downloaded?: number;
    skipped?: boolean;
  };
  text_facts?: Array<{
    fact_id?: string;
    paper_id?: string;
    section?: string;
    sentence?: string;
    matched_targets?: string[];
    extraction_tier?: string;
  }>;
  release_gate?: ReleaseGateReport;
}

export interface DataSpecCoverage {
  data_spec_score?: number;
  entities_requested?: string[];
  entities_hit?: string[];
  entities_miss?: string[];
  targets_requested?: string[];
  targets_hit?: string[];
  targets_miss?: string[];
  figures_with_manifest?: number;
  figures_confirmed?: number;
  gaps?: string[];
  checklist?: Array<{ field?: string; label?: string; hit?: boolean }>;
}

export interface SourceAvailabilityReport {
  total?: number;
  importable_count?: number;
  imported_count?: number;
  catalog_only_count?: number;
  metadata_only_count?: number;
  search_and_import_count?: number;
  by_availability?: Record<string, number>;
  candidates_summary?: Array<{
    dataset_name?: string;
    source_platform?: string;
    availability?: string;
    import_supported?: boolean;
    imported?: boolean;
  }>;
}

export interface CoverageReport {
  completeness_score?: number;
  data_spec_coverage?: DataSpecCoverage;
  threshold?: number;
  data_spec_threshold?: number;
  gap_enrichment_recommended?: boolean;
  project_mode?: string;
  documents_count?: number;
  papers_screened?: number;
  tables_extracted?: number;
  rows_merged?: number;
  external_candidates_count?: number;
  domain_checklist?: Array<{ id: string; label: string; hit: boolean }>;
  gaps?: string[];
  has_cleaned_csv?: boolean;
  external_import_succeeded?: number;
  source_availability?: SourceAvailabilityReport;
  gap_queries?: string[];
  cleaning_summary?: Record<string, unknown>;
}

export interface AnalysisBundleMeta {
  bundle_path?: string;
  bundle_zip_path?: string;
  ready?: boolean;
  files?: string[];
  generated_at?: string;
  reason?: string;
}

const dataFinderService = {
  async gapEnrich(
    projectId: string,
    options?: {
      auto_import?: boolean;
      coverage_gap_threshold?: number;
      data_spec_gap_threshold?: number;
      max_gap_rounds?: number;
    },
  ): Promise<ApiResponse<{ history: unknown[]; results: DataFinderResult | null }>> {
    const { data } = await api.post('/data-finder/gap-enrich', {
      project_id: projectId,
      auto_import: options?.auto_import ?? true,
      coverage_gap_threshold: options?.coverage_gap_threshold,
      data_spec_gap_threshold: options?.data_spec_gap_threshold,
      max_gap_rounds: options?.max_gap_rounds,
    });
    return data;
  },

  async acquire(payload: {
    project_id: string;
    research_question?: string;
    selected_hypothesis?: string;
    project_mode?: string;
  }): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/acquire', payload);
    return data;
  },

  async buildLibrary(payload: {
    project_id: string;
    research_question?: string;
    selected_hypothesis?: string;
    project_mode?: string;
    auto_import?: boolean;
    enable_gap_search?: boolean;
    coverage_gap_threshold?: number;
    data_spec_gap_threshold?: number;
    max_gap_rounds?: number;
  }): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/build-library', payload);
    return data;
  },

  async search(payload: {
    project_id: string;
    research_question?: string;
    selected_hypothesis?: string;
    project_mode?: string;
  }): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/search', payload);
    return data;
  },

  async extractTables(projectId: string, paperIds?: string[]): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/extract-tables', {
      project_id: projectId,
      paper_ids: paperIds,
    });
    return data;
  },

  async alignSchema(projectId: string, tableIds?: string[]): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/align-schema', {
      project_id: projectId,
      table_ids: tableIds,
    });
    return data;
  },

  async merge(projectId: string): Promise<ApiResponse<DataFinderResult>> {
    const { data } = await api.post('/data-finder/merge', { project_id: projectId });
    return data;
  },

  async getResults(projectId: string): Promise<ApiResponse<DataFinderResult | null>> {
    const { data } = await api.get('/data-finder/results', { params: { project_id: projectId } });
    return data;
  },

  async importToDataset(projectId: string, mergeId?: string): Promise<ApiResponse<unknown>> {
    const { data } = await api.post('/data-finder/import-to-dataset', {
      project_id: projectId,
      merge_id: mergeId,
    });
    return data;
  },

  getBundleDownloadUrl(projectId: string): string {
    return `/api/v1/data-finder/bundle/download?project_id=${encodeURIComponent(projectId)}`;
  },

  async downloadBundle(projectId: string): Promise<Blob> {
    const { data } = await api.get('/data-finder/bundle/download', {
      params: { project_id: projectId },
      responseType: 'blob',
    });
    return data;
  },

  async getPaperExtractionStats(projectId: string): Promise<ApiResponse<{
    by_paper: Record<string, { tables: number; figures_confirmed: number; figures_pending: number }>;
    total_tables: number;
    total_figures: number;
    figures_pending_review: number;
  }>> {
    const { data } = await api.get('/data-finder/paper-extraction-stats', {
      params: { project_id: projectId },
    });
    return data;
  },

  async reviewFigure(
    projectId: string,
    figureId: string,
    action: 'confirm' | 'reject' | 'confirm_edited',
    editedRows?: Array<Record<string, unknown>>,
    reviewerNote?: string,
  ): Promise<ApiResponse<Record<string, unknown>>> {
    const { data } = await api.post('/data-finder/figures/review', {
      project_id: projectId,
      figure_id: figureId,
      action,
      edited_rows: editedRows,
      reviewer_note: reviewerNote || '',
    });
    return data;
  },

  async uploadExternalCandidate(
    projectId: string,
    candidateId: string,
    file: File,
  ): Promise<ApiResponse<DataFinderResult>> {
    const form = new FormData();
    form.append('project_id', projectId);
    form.append('candidate_id', candidateId);
    form.append('file', file);
    const { data } = await api.post('/data-finder/external-candidates/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  getDownloadUrl(projectId: string): string {
    return `/api/v1/data-finder/results?project_id=${projectId}`;
  },
};

export default dataFinderService;
