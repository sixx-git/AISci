// ============================================================
// Mock 数据已移除。此文件保留空导出以兼容现有 import 语句。
// 所有页面已迁移到真实后端 API。
// ============================================================

import type {
  ProjectOverview,
  StatItem,
  PipelineNodeData,
  Hypothesis,
  DetailedHypothesis,
  ExperimentDesign,
  DetailedExperimentDesign,
  LiteratureItem,
  EvidenceItem,
  AgentNodeData,
  LiteratureStats,
  ReportData,
  ReportSection,
  RunLog,
  ResearchResult,
} from '@/types';

export function computeLiteratureStats(_items: LiteratureItem[]): LiteratureStats {
  return {
    uploaded: 0,
    parsed: 0,
    snippets: 0,
    facts: 0,
  };
}

export const MOCK_PROJECTS: Record<string, ProjectOverview> = {};
export { MOCK_PROJECTS as MOCK_PROJECT_OVERVIEW };

export const DEFAULT_STATS: StatItem[] = [];

export const MOCK_STATS: Record<string, StatItem[]> = {};

export const DEFAULT_PIPELINE_NODES: PipelineNodeData[] = [];

export const MOCK_PIPELINE_NODES: Record<string, PipelineNodeData[]> = {};

export const MOCK_HYPOTHESES: Hypothesis[] = [];

export const MOCK_DETAILED_HYPOTHESES: DetailedHypothesis[] = [];

export const MOCK_EVIDENCE_CHAINS: Record<string, EvidenceItem[]> = {};

export const MOCK_LITERATURE: LiteratureItem[] = [];

export const MOCK_AGENT_NODES: AgentNodeData[] = [];

export const MOCK_EXPERIMENTS: ExperimentDesign[] = [];

export const MOCK_DETAILED_EXPERIMENT: DetailedExperimentDesign | null = null;

export const MOCK_REPORT: ReportData | null = null;

export const MOCK_REPORT_SECTIONS: ReportSection[] = [];

export const MOCK_RUN_LOGS: RunLog[] = [];

export const MOCK_RESEARCH_RESULTS: ResearchResult | null = null;