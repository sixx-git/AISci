import type {
  EnsembleReviewData,
  PipelineStageExecutionSummary,
  ProConAdversarialData,
} from '@/types';

type StageLike = Pick<PipelineStageExecutionSummary, 'stage' | 'output_data' | 'status'>;

export interface HypothesisReviewExtras {
  proCon: ProConAdversarialData | null;
  ensemble: EnsembleReviewData | null;
  adversarialMode: string | null;
  stageStatus: string | null;
}

function isHypothesisReviewStage(stage: string): boolean {
  const s = stage.toLowerCase();
  return s === 'hypothesis_review' || s.includes('hypothesis_review');
}

export function findHypothesisReviewStage(
  stages: StageLike[] | undefined,
): StageLike | undefined {
  if (!stages?.length) return undefined;
  return stages.find((st) => isHypothesisReviewStage(String(st.stage || '')));
}

/** 从 hypothesis_review 阶段 output 解析红蓝对抗与集成评审。 */
export function parseHypothesisReviewOutput(
  output: Record<string, unknown> | null | undefined,
): HypothesisReviewExtras {
  if (!output || typeof output !== 'object') {
    return { proCon: null, ensemble: null, adversarialMode: null, stageStatus: null };
  }

  const skillOutputs = output.skill_outputs as Record<string, unknown> | undefined;
  const proConRaw = skillOutputs?.pro_con_adversarial as ProConAdversarialData | undefined;
  const proCon =
    proConRaw?.mode && proConRaw.mode !== 'off' ? proConRaw : null;

  const ensembleRaw = (skillOutputs?.ensemble_review || output.ensemble_review) as
    | EnsembleReviewData
    | undefined;
  const ensemble = ensembleRaw
    ? {
        ...ensembleRaw,
        overall: ensembleRaw.overall ?? (output.ensemble_overall as number | undefined),
        decision: ensembleRaw.decision ?? (output.ensemble_decision as string | undefined),
      }
    : null;

  const adversarialMode =
    (output.adversarial_mode as string | undefined) ||
    proCon?.mode ||
    null;

  return { proCon, ensemble, adversarialMode, stageStatus: null };
}

export function extractHypothesisReviewExtras(
  stages: StageLike[] | undefined,
): HypothesisReviewExtras {
  const stage = findHypothesisReviewStage(stages);
  if (!stage?.output_data || typeof stage.output_data !== 'object') {
    return { proCon: null, ensemble: null, adversarialMode: null, stageStatus: null };
  }
  const parsed = parseHypothesisReviewOutput(stage.output_data as Record<string, unknown>);
  return { ...parsed, stageStatus: String(stage.status || '') || null };
}
