import api from '@/lib/api';
import type { ApiResponse } from '@/types';

export type EducationLevel = 'primary' | 'secondary' | 'undergraduate' | 'graduate' | 'researcher';
export type RetrievalMode = 'local' | 'global' | 'hybrid';

export interface KgNode {
  id: string;
  type: string;
  label: string;
  description?: string;
  source_ids?: string[];
  confidence?: number;
  metadata?: Record<string, unknown>;
}

export interface KgEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidence?: string;
  source_title?: string;
  paper_id?: string;
  page?: number | null;
  confidence?: number;
  human_verified?: boolean;
}

export interface KgCommunity {
  community_id: string;
  summary: string;
  dominant_type: string;
  node_count: number;
  top_entities?: string[];
  keywords?: string[];
}

export interface KgReasoningStep {
  step: number;
  type: string;
  content: string;
  inference?: string;
  source_title?: string;
  confidence?: number;
}

export interface KgQualityReport {
  node_count?: number;
  edge_count?: number;
  isolated_count?: number;
  isolated_nodes?: Array<{ id: string; label?: string; type?: string }>;
  low_confidence_count?: number;
  low_confidence_edges?: KgEdge[];
  duplicate_count?: number;
  missing_sources_count?: number;
  overall_score?: number;
}

export interface KnowledgeGraphData {
  project_id: string;
  project_mode?: string;
  domain_scenario?: string;
  schema?: {
    node_types?: string[];
    relation_types?: string[];
  };
  nodes: KgNode[];
  edges: KgEdge[];
  candidate_edges?: KgEdge[];
  communities?: KgCommunity[];
  evidence_graph?: { nodes: KgNode[]; edges: KgEdge[] };
  quality_report?: KgQualityReport;
  updated_at?: string;
}

export interface KgQueryResult {
  answer: string;
  raw_answer?: string;
  graph_paths: Array<string[] | string>;
  supporting_sources: string[];
  limitations: string[];
  intent?: string;
  retrieval_mode?: RetrievalMode;
  education_level?: EducationLevel;
  subgraph?: { nodes: KgNode[]; edges: KgEdge[] };
  reasoning_chain?: KgReasoningStep[];
  provenance?: {
    source_count?: number;
    citation_spans?: Array<{ text?: string; source_title?: string; confidence?: number | null }>;
  };
  global_context?: string;
  local_context?: string;
  global_hit?: { community_count?: number };
  local_hit?: { seed_count?: number; node_count?: number };
}

export interface KgScenarioCatalog {
  education_levels: Array<{ id: string; label: string }>;
  domain_scenarios: Record<string, {
    label: string;
    description: string;
    example_questions?: string[];
  }>;
  retrieval_modes: Record<string, string>;
}

const knowledgeGraphService = {
  async getScenarios(): Promise<ApiResponse<KgScenarioCatalog>> {
    const res = await api.get('/kg/scenarios');
    return res.data;
  },

  async build(payload: {
    project_id: string;
    research_question?: string;
    project_mode?: string;
  }): Promise<ApiResponse<KnowledgeGraphData>> {
    const res = await api.post('/kg/build', payload);
    return res.data;
  },

  async getGraph(projectId: string): Promise<ApiResponse<KnowledgeGraphData | null>> {
    const res = await api.get(`/kg/project/${projectId}`);
    return res.data;
  },

  async query(
    projectId: string,
    query: string,
    options?: { education_level?: EducationLevel; retrieval_mode?: RetrievalMode },
  ): Promise<ApiResponse<KgQueryResult>> {
    const res = await api.post('/kg/query', {
      project_id: projectId,
      query,
      education_level: options?.education_level ?? 'undergraduate',
      retrieval_mode: options?.retrieval_mode ?? 'hybrid',
    });
    return res.data;
  },

  async feedback(payload: {
    project_id: string;
    action: string;
    target_type?: string;
    target_id?: string;
    payload?: Record<string, unknown>;
  }): Promise<ApiResponse<{ graph: KnowledgeGraphData }>> {
    const res = await api.post('/kg/feedback', payload);
    return res.data;
  },

  async rebuild(payload: {
    project_id: string;
    research_question?: string;
    project_mode?: string;
  }): Promise<ApiResponse<KnowledgeGraphData>> {
    const res = await api.post('/kg/rebuild', payload);
    return res.data;
  },
};

export default knowledgeGraphService;
