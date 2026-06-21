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
    row_count?: number;
    columns?: string[];
  } | null;
  warnings?: string[];
  updated_at?: string;
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

  getDownloadUrl(projectId: string): string {
    return `/api/v1/data-finder/results?project_id=${projectId}`;
  },
};

export default dataFinderService;
