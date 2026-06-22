import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export interface DataFinderRequirements {
  data_need?: string;
  target_variables?: string[];
  expected_metrics?: string[];
  domain_keywords?: string[];
  dataset_keywords?: string[];
  preferred_sources?: string[];
  output_format?: string;
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

export interface DataFinderResult {
  project_id: string;
  project_mode?: string;
  data_requirements?: DataFinderRequirements;
  paper_extractions?: PaperExtraction[];
  external_candidates?: Array<Record<string, unknown>>;
  figures?: Array<Record<string, unknown>>;
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
}

export interface CoverageReport {
  completeness_score?: number;
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

  getDownloadUrl(projectId: string): string {
    return `/api/v1/data-finder/results?project_id=${projectId}`;
  },
};

export default dataFinderService;
