/** Pipeline 阶段 → 项目工作台 Tab */
export const PIPELINE_STAGE_TAB: Record<string, string> = {
  problem_understanding: 'questions',
  literature_mining: 'literature',
  data_acquisition: 'datasets',
  knowledge_gap: 'knowledge_graph',
  hypothesis_generation: 'hypotheses',
  hypothesis_review: 'hypotheses',
  experiment_design: 'experiments',
  small_validation: 'experiments',
  report_generation: 'reports',
};

export function getPipelineStageTab(stageId: string): string | undefined {
  return PIPELINE_STAGE_TAB[stageId];
}
