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
