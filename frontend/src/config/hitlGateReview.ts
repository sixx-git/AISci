import { getPipelineStageTab } from '@/config/pipelineStageNavigation';

export interface HitlGateReviewTarget {
  title: string;
  description: string;
  tab: string;
  ctaLabel: string;
  continueHint: string;
  /** 假设页继续条标题 */
  continueTitle: string;
  /** 假设页继续条说明：将运行哪些下游智能体 */
  continueDescription: string;
  /** 假设页继续按钮文案 */
  continueButtonLabel: string;
}

const STAGE_REVIEW_COPY: Record<string, HitlGateReviewTarget> = {
  hypothesis_generation: {
    title: '假设已生成',
    description:
      'Pipeline 已在此暂停。请前往「候选假设」审阅生成的假设，选定主假设后，可继续运行下游智能体。',
    tab: 'hypotheses',
    ctaLabel: '前往审阅假设',
    continueHint: '审阅并选定主假设后，将运行可行性评估及后续智能体。',
    continueTitle: '假设已生成',
    continueDescription:
      '审阅并选定主假设后，将依次运行：可行性评估 → 迭代实验 → 报告生成。',
    continueButtonLabel: '运行可行性评估及后续智能体',
  },
  hypothesis_review: {
    title: '假设评估已完成',
    description:
      '请查看假设评估与对抗性审稿结果，确认无误后可继续迭代实验及下游流程。',
    tab: 'hypotheses',
    ctaLabel: '前往查看假设',
    continueHint: '确认评估结果后，将运行迭代实验及后续智能体。',
    continueTitle: '假设评估已完成',
    continueDescription:
      '确认评估结果后，将依次运行：迭代实验 → 报告生成。',
    continueButtonLabel: '运行迭代实验及后续智能体',
  },
  iterative_experiment: {
    title: '迭代实验已完成',
    description:
      '请前往「迭代实验」审阅脚本、迭代结果与报告实验勾选。缺数据时需先绑定数据后再继续。',
    tab: 'experiments',
    ctaLabel: '前往审阅迭代实验',
    continueHint: '确认实验就绪后，将运行报告生成。',
    continueTitle: '迭代实验已完成',
    continueDescription: '确认迭代结果后，将运行报告生成智能体。',
    continueButtonLabel: '运行报告生成智能体',
  },
  // legacy HITL 文案
  experiment_design: {
    title: '实验设计已完成（旧）',
    description: '该阶段已合并为「迭代实验」。请前往迭代实验页继续。',
    tab: 'experiments',
    ctaLabel: '前往迭代实验',
    continueHint: '将运行报告生成（若仍从旧阶段恢复）。',
    continueTitle: '实验设计已完成（旧）',
    continueDescription: '确认后继续报告生成。',
    continueButtonLabel: '运行报告生成智能体',
  },
  small_validation: {
    title: '小样验证已完成（旧）',
    description: '该阶段已合并为「迭代实验」。请前往迭代实验页继续。',
    tab: 'experiments',
    ctaLabel: '前往迭代实验',
    continueHint: '审阅完成后，将运行报告生成智能体。',
    continueTitle: '小样验证已完成（旧）',
    continueDescription: '确认后将运行报告生成智能体。',
    continueButtonLabel: '运行报告生成智能体',
  },
  report_generation: {
    title: '报告已生成',
    description: '请前往「研究报告」审阅最终报告，确认后完成本次 Pipeline。',
    tab: 'reports',
    ctaLabel: '前往审阅报告',
    continueHint: '审阅完成后，将完成本次 Pipeline。',
    continueTitle: '报告已生成',
    continueDescription: '确认报告内容后，将完成本次 Pipeline。',
    continueButtonLabel: '确认并完成 Pipeline',
  },
};

export function getHitlGateReviewTarget(stage?: string | null): HitlGateReviewTarget {
  if (stage && STAGE_REVIEW_COPY[stage]) {
    return STAGE_REVIEW_COPY[stage];
  }
  const tab = (stage && getPipelineStageTab(stage)) || 'workflow';
  const label = stage || '当前阶段';
  return {
    title: '等待人工确认',
    description: `阶段「${label}」已完成，请审阅相关内容后确认继续。`,
    tab,
    ctaLabel: '前往审阅',
    continueHint: '审阅完成后，在对应页面继续运行下游智能体。',
    continueTitle: '等待确认',
    continueDescription: '审阅完成后，将继续运行下游智能体。',
    continueButtonLabel: '继续运行下游智能体',
  };
}

export function isHypothesisGateStage(stage?: string | null): boolean {
  return stage === 'hypothesis_generation' || stage === 'hypothesis_review';
}
