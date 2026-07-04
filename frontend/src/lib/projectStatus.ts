import type { StatusType } from '@/components/StatusBadge';

/** 将后端/各处的原始状态归一化为 StatusBadge 标准类型 */
export function normalizeStatusKey(raw?: string | null): StatusType {
  const key = (raw || '').toLowerCase().trim();
  switch (key) {
    case 'running':
    case 'in_progress':
      return 'running';
    case 'completed':
    case 'success':
      return 'completed';
    case 'failed':
    case 'error':
    case 'cancelled':
      return 'failed';
    case 'human_review':
    case 'human_review_required':
      return 'awaiting_data_upload';
    case 'archived':
      return 'archived';
    case 'draft':
      return 'draft';
    case 'pending':
    case '':
      return 'pending';
    default:
      return 'pending';
  }
}

/** 项目展示状态：优先采用最近一次 Pipeline 运行状态，否则回退到项目状态 */
export function resolveProjectDisplayStatus(
  projectStatus?: string | null,
  latestPipelineStatus?: string | null,
): StatusType {
  if (latestPipelineStatus) {
    return normalizeStatusKey(latestPipelineStatus);
  }
  const normalized = normalizeStatusKey(projectStatus);
  // 未运行过 Pipeline 的 draft 在 UI 上视为「未开始」，不展示「草稿」
  if (normalized === 'draft') {
    return 'pending';
  }
  return normalized;
}

/** 状态徽章文案：区分 Pipeline 等待中与尚未启动 */
export function statusBadgeLabel(
  status: StatusType,
  rawPipelineStatus?: string | null,
  hasPipelineRun = Boolean(rawPipelineStatus),
): string | undefined {
  const raw = (rawPipelineStatus || '').toLowerCase();
  if (status === 'pending' && raw === 'pending') return '等待中';
  if (status === 'pending' && !hasPipelineRun) return '未开始';
  if (status === 'failed' && raw === 'cancelled') return '已取消';
  if (status === 'awaiting_data_upload') return '待上传数据';
  return undefined;
}

/** 统一中文状态文案（概览 / 列表） */
export function statusTypeToChinese(status: StatusType): string {
  switch (status) {
    case 'completed':
      return '已完成';
    case 'running':
      return '运行中';
    case 'failed':
      return '失败';
    case 'awaiting_data_upload':
    case 'human_review':
      return '待上传数据';
    case 'draft':
      return '草稿';
    case 'archived':
      return '已归档';
    case 'pending':
    default:
      return '未开始';
  }
}

/** 最近一次 Pipeline 运行的展示文案 */
export function formatLatestRunStatusLabel(
  run?: { status?: string; failed_stage?: string | null } | null,
  stageLabels?: Record<string, string>,
): string {
  if (!run?.status) return '无记录';
  const normalized = normalizeStatusKey(run.status);
  if (normalized === 'failed') {
    const stageKey = (run.failed_stage || '').trim();
    const stageLabel = stageKey
      ? (stageLabels?.[stageKey] || stageKey)
      : '';
    return stageLabel ? `失败（${stageLabel}）` : '失败';
  }
  const custom = statusBadgeLabel(normalized, run.status, true);
  return custom ?? statusTypeToChinese(normalized);
}

/** 项目展示状态中文（优先 Pipeline 运行状态） */
export function formatProjectDisplayStatusLabel(
  projectStatus?: string | null,
  latestPipelineStatus?: string | null,
): string {
  const display = resolveProjectDisplayStatus(projectStatus, latestPipelineStatus);
  const custom = statusBadgeLabel(
    display,
    latestPipelineStatus,
    Boolean(latestPipelineStatus),
  );
  return custom ?? statusTypeToChinese(display);
}
