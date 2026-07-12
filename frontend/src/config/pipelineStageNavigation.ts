/** Pipeline 阶段 → 项目工作台 Tab */
export const PIPELINE_STAGE_TAB: Record<string, string> = {
  problem_understanding: 'questions',
  literature_mining: 'literature',
  knowledge_gap: 'workflow',
  hypothesis_generation: 'hypotheses',
  hypothesis_review: 'hypotheses',
  experiment_design: 'experiments',
  small_validation: 'experiments',
  report_generation: 'reports',
  data_acquisition: 'datasets',
};

export function getPipelineStageTab(stageId: string): string | undefined {
  return PIPELINE_STAGE_TAB[stageId];
}
