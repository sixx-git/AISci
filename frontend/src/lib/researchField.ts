import { researchQuestionKey } from '@/lib/storageKeys';
import { normalizePipelineStageKey } from '@/lib/pipelineProgressNodes';

type ProjectResearchSource = {
  research_domain?: string | null;
  research_field?: string | null;
  project_mode?: string | null;
};

type StageWithOutput = {
  stage?: string;
  output_data?: unknown;
};

export function getStoredResearchDomain(projectId: string): string {
  try {
    const raw = localStorage.getItem(researchQuestionKey(projectId));
    if (!raw) return '';
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return String(parsed.researchDomain || parsed.research_domain || '').trim();
  } catch {
    return '';
  }
}

function researchDomainFromStageOutput(output: unknown): string {
  if (!output || typeof output !== 'object') return '';
  const data = output as Record<string, unknown>;
  return String(data.research_domain || data.researchDomain || '').trim();
}

/** 解析项目研究领域：后端 research_domain → 本地草稿 → Pipeline 问题理解阶段 */
export function resolveResearchField(
  project: ProjectResearchSource | null | undefined,
  projectId?: string,
  stageExecutions?: StageWithOutput[],
): string {
  const fromProject =
    project?.research_domain?.trim()
    || project?.research_field?.trim();
  if (fromProject) return fromProject;

  if (projectId) {
    const stored = getStoredResearchDomain(projectId);
    if (stored) return stored;
  }

  for (const exec of stageExecutions || []) {
    if (normalizePipelineStageKey(exec.stage) !== 'problem_understanding') continue;
    const domain = researchDomainFromStageOutput(exec.output_data);
    if (domain) return domain;
  }

  return '未填写';
}
