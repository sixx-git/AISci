/** Pipeline 阶段 → 项目工作台 Tab */
export const PIPELINE_STAGE_TAB: Record<string, string> = {
  problem_understanding: 'questions',
  literature_mining: 'literature',
  knowledge_gap: 'workflow',
  hypothesis_generation: 'hypotheses',
  hypothesis_review: 'hypotheses',
  iterative_experiment: 'experiments',
  experiment_design: 'experiments', // legacy
  small_validation: 'experiments', // legacy
  report_generation: 'reports',
  data_acquisition: 'experiments',
};

export function getPipelineStageTab(stageId: string): string | undefined {
  return PIPELINE_STAGE_TAB[stageId];
}
