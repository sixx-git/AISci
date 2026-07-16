/** Pipeline 阶段 → 项目工作台 Tab */
export const PIPELINE_STAGE_TAB: Record<string, string> = {
  problem_understanding: 'questions',
  literature_mining: 'literature',
  knowledge_gap: 'workflow',
  hypothesis_generation: 'hypotheses',
  hypothesis_review: 'hypotheses',
  iterative_experiment: 'experiments',
  report_generation: 'reports',
};

export function getPipelineStageTab(stageId: string): string | undefined {
  // 历史 stage 键 → 迭代实验 Tab
  if (stageId === 'experiment_design' || stageId === 'small_validation') {
    return 'experiments';
  }
  // 历史 data_acquisition → 工作流（不再映射到实验 Tab）
  if (stageId === 'data_acquisition') {
    return 'workflow';
  }
  return PIPELINE_STAGE_TAB[stageId];
}
