import type { LucideIcon } from 'lucide-react';
import type { PipelineProgressNode } from '@/components/PipelineProgress';

export interface PipelineStageDefinition {
  id: string;
  label: string;
  icon: LucideIcon;
}

export function normalizePipelineStageKey(stage?: string | null): string {
  if (!stage) return '';
  return stage
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/^pipelinestage\./i, '')
    .trim();
}

function normalizeRunStatus(status?: string | null): string {
  if (!status) return 'pending';
  return status.toLowerCase().replace(/[\s-]+/g, '_').trim();
}

/** 将后端阶段状态映射为 PipelineProgress 节点状态 */
export function mapStageExecutionStatus(raw?: string | null): PipelineProgressNode['status'] {
  const key = normalizeRunStatus(raw);
  if (['running', 'processing', 'in_progress'].includes(key)) return 'running';
  if (['human_review_required', 'human_review', 'review', 'needs_review'].includes(key)) {
    return 'running';
  }
  if (['completed', 'success', 'done', 'finished'].includes(key)) return 'completed';
  if (['failed', 'error', 'fault', 'cancelled'].includes(key)) return 'error';
  return 'pending';
}

export function buildPipelineProgressNodes(
  stageDefs: PipelineStageDefinition[],
  stageExecutions: Array<{ stage?: string; status?: string }> | undefined,
  runStatus?: string | null,
  failedStage?: string | null,
): PipelineProgressNode[] {
  const statusByStage = new Map<string, string>();
  for (const exec of stageExecutions || []) {
    const key = normalizePipelineStageKey(exec.stage);
    if (key) statusByStage.set(key, exec.status || 'pending');
  }

  const normalizedRun = normalizeRunStatus(runStatus);
  const failedKey = normalizePipelineStageKey(failedStage);

  let runningIdx = -1;
  if (normalizedRun === 'running' && statusByStage.size > 0) {
    for (let i = 0; i < stageDefs.length; i += 1) {
      const st = mapStageExecutionStatus(statusByStage.get(stageDefs[i].id));
      if (st === 'running') {
        runningIdx = i;
        break;
      }
      if (st === 'pending') {
        runningIdx = i;
        break;
      }
    }
  }

  return stageDefs.map((def, idx) => {
    const raw = statusByStage.get(def.id);
    let status = mapStageExecutionStatus(raw);

    if (raw === undefined) {
      if (normalizedRun === 'completed') {
        status = 'completed';
      } else if (normalizedRun === 'failed') {
        if (def.id === failedKey) {
          status = 'error';
        } else if (failedKey) {
          const failedIdx = stageDefs.findIndex((s) => s.id === failedKey);
          status = failedIdx >= 0 && idx < failedIdx ? 'completed' : 'pending';
        } else {
          status = 'pending';
        }
      } else if (normalizedRun === 'running') {
        if (runningIdx >= 0) {
          if (idx < runningIdx) status = 'completed';
          else if (idx === runningIdx) status = 'running';
          else status = 'pending';
        } else if (idx === 0) {
          status = 'running';
        } else {
          status = 'pending';
        }
      } else {
        status = 'pending';
      }
    } else if (normalizedRun === 'failed' && def.id === failedKey) {
      status = 'error';
    }

    return {
      id: def.id,
      label: def.label,
      icon: def.icon,
      status,
    };
  });
}

/** 当前 Pipeline 阶段展示文案（与最新运行 / 阶段执行记录对齐） */
export function resolveCurrentPipelineStageLabel(
  latestRun: { status?: string; failed_stage?: string | null } | undefined,
  stageExecutions: Array<{ stage?: string; status?: string }> | undefined,
  stageLabels: Record<string, string>,
  options?: { isPipelineStarting?: boolean },
): string {
  if (options?.isPipelineStarting && !latestRun) return '启动中';
  if (!latestRun?.status) return '未开始';

  const runKey = normalizeRunStatus(latestRun.status);
  if (runKey === 'completed') return '已完成';
  if (runKey === 'failed') {
    const failedKey = normalizePipelineStageKey(latestRun.failed_stage);
    const failedLabel = failedKey
      ? (stageLabels[failedKey] || failedKey)
      : '';
    return failedLabel ? `失败于 ${failedLabel}` : '失败';
  }
  if (runKey !== 'running') {
    if (runKey === 'human_review_required' || runKey === 'human_review') return '待上传数据';
    return '未开始';
  }

  for (const exec of stageExecutions || []) {
    if (mapStageExecutionStatus(exec.status) === 'running') {
      const key = normalizePipelineStageKey(exec.stage);
      return stageLabels[key] || key || '运行中';
    }
  }

  for (const exec of stageExecutions || []) {
    const key = normalizePipelineStageKey(exec.stage);
    if (key && mapStageExecutionStatus(exec.status) === 'pending') {
      return stageLabels[key] || key;
    }
  }

  return '运行中';
}
