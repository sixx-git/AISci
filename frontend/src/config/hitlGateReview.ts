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
  /** continue 行为：resume=恢复 Pipeline；navigate=仅跳转对应 Tab */
  continueAction?: 'resume' | 'navigate';
}

const STAGE_REVIEW_COPY: Record<string, HitlGateReviewTarget> = {
  literature_mining: {
    title: '文献已检索，请补充 PDF',
    description:
      'Pipeline 已在文献挖掘后暂停。请前往「文献库」下载检索到的论文 PDF，上传并完成解析后，再继续后续智能体。',
    tab: 'literature',
    ctaLabel: '前往文献库',
    continueHint: '上传并解析 PDF 后，将重跑文献挖掘及之后全部智能体。',
    continueTitle: '文献 PDF 待补充',
    continueDescription:
      '请先下载/上传相关论文 PDF 并解析入库；确认后将重跑文献挖掘 → 知识缺口 → 假设生成 → 假设评审等后续阶段。',
    continueButtonLabel: '继续运行流水线',
    continueAction: 'resume',
  },
  hypothesis_generation: {
    title: '假设已生成',
    description:
      'Pipeline 已在此暂停。请前往「候选假设」审阅生成的假设，选定主假设后，可继续运行下游智能体。',
    tab: 'hypotheses',
    ctaLabel: '前往审阅假设',
    continueHint: '审阅并选定主假设后，将运行可行性评估。',
    continueTitle: '假设已生成',
    continueDescription: '审阅并选定主假设后，将运行可行性评估智能体。',
    continueButtonLabel: '运行可行性评估',
    continueAction: 'resume',
  },
  hypothesis_review: {
    title: '可行性评估已完成',
    description:
      'Pipeline 已自动终止。请前往「迭代实验」页进行实验设计与沙箱验证；完成后再勾选实验并生成报告。',
    tab: 'experiments',
    ctaLabel: '前往迭代实验',
    continueHint: '报告不会自动生成，请在「迭代实验」页勾选实验后点击「生成报告」。',
    continueTitle: '可行性评估已完成',
    continueDescription:
      '请前往「迭代实验」页完成实验设计与沙箱验证。报告需在该页手动生成，不会自动触发。',
    continueButtonLabel: '前往迭代实验',
    continueAction: 'navigate',
  },
  // 兼容：若旧 run / 配置仍卡在迭代实验门控
  iterative_experiment: {
    title: '迭代实验阶段已过门控',
    description:
      '实验细节审阅请在「迭代实验」页（shaxiang 流程）完成；确认后可继续报告生成。',
    tab: 'experiments',
    ctaLabel: '前往迭代实验',
    continueHint: '确认后将运行报告生成。',
    continueTitle: '迭代实验可继续',
    continueDescription: '确认后将运行报告生成智能体。',
    continueButtonLabel: '运行报告生成智能体',
    continueAction: 'resume',
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
    continueAction: 'resume',
  },
};

export function getHitlGateReviewTarget(stage?: string | null): HitlGateReviewTarget {
  // 历史 run：旧实验阶段统一视作迭代实验
  const normalized =
    stage === 'experiment_design' || stage === 'small_validation'
      ? 'iterative_experiment'
      : stage;
  if (normalized && STAGE_REVIEW_COPY[normalized]) {
    return STAGE_REVIEW_COPY[normalized];
  }
  const tab = (normalized && getPipelineStageTab(normalized)) || 'workflow';
  const label = normalized || '当前阶段';
  return {
    title: '等待人工确认',
    description: `阶段「${label}」已完成，请审阅相关内容后确认继续。`,
    tab,
    ctaLabel: '前往审阅',
    continueHint: '审阅完成后，在对应页面继续运行下游智能体。',
    continueTitle: '等待确认',
    continueDescription: '审阅完成后，将继续运行下游智能体。',
    continueButtonLabel: '继续运行下游智能体',
    continueAction: 'resume',
  };
}

export function isHypothesisGateStage(stage?: string | null): boolean {
  return stage === 'hypothesis_generation' || stage === 'hypothesis_review';
}
