/** Pipeline 阶段 → 项目工作台 Tab */
export const PIPELINE_STAGE_TAB: Record<string, string> = {
  problem_understanding: 'questions',
  literature_mining: 'literature',
  knowledge_gap: 'workflow',
  hypothesis_generation: 'hypotheses',
  hypothesis_review: 'hypotheses',
  iterative_experiment: 'experiments',
  report_generation: 'reports',
  data_acquisition: 'experiments',
};

export function getPipelineStageTab(stageId: string): string | undefined {
  // 历史 stage 键 → 迭代实验 Tab
  if (stageId === 'experiment_design' || stageId === 'small_validation') {
    return 'experiments';
  }
  return PIPELINE_STAGE_TAB[stageId];
}
