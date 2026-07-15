import type { IterativeExperimentPhase } from '@/types/iterativeExperiment';

export const PHASE_LABEL: Record<IterativeExperimentPhase, string> = {
  created: '已创建',
  data_recommended: '已推荐数据集',
  data_uploaded: '已上传数据',
  script_designed: '脚本已设计',
  running: '迭代中',
  needs_human_review: '待人工审阅',
  completed: '已完成',
  failed: '失败',
};

export const PHASE_EMOJI: Record<IterativeExperimentPhase, string> = {
  created: '📋',
  data_recommended: '📂',
  data_uploaded: '📁',
  script_designed: '📝',
  running: '🔄',
  needs_human_review: '👤',
  completed: '✅',
  failed: '❌',
};
