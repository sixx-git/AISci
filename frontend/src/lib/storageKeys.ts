/** 项目级 localStorage key，避免散落字符串 */

export function researchQuestionKey(projectId: string): string {
  return `aisci_research_question_${projectId}`;
}

export function selectedHypothesisKey(projectId: string): string {
  return `aisci_selected_hypothesis_${projectId}`;
}

export function activeRunKey(projectId: string): string {
  return `aisci_active_run_${projectId}`;
}

export function activeRunStatusKey(projectId: string): string {
  return `aisci_active_run_status_${projectId}`;
}

/** 工作流 Loop 配置（迭代模式 / 红蓝对抗等），按项目隔离 */
export function loopConfigKey(projectId: string): string {
  return `aisci_loop_config_${projectId}`;
}

/** 迭代实验（shaxiang 对齐）按项目隔离的 localStorage mock */
export function iterativeExperimentsKey(projectId: string): string {
  return `aisci_iterative_experiments_${projectId}`;
}
