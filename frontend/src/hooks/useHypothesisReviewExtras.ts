import { useEffect, useState } from 'react';
import { pipelineService } from '@/services/pipelineService';
import {
  extractHypothesisReviewExtras,
  type HypothesisReviewExtras,
} from '@/lib/pipelineReviewExtras';

const EMPTY: HypothesisReviewExtras = {
  proCon: null,
  ensemble: null,
  evolution: null,
  adversarialMode: null,
  stageStatus: null,
};

async function resolveRunId(
  projectId: string,
  latestRunId?: string | null,
): Promise<string | null> {
  if (latestRunId) return latestRunId;
  try {
    const res = await pipelineService.getRuns(projectId);
    if (res.code === 200 && res.data?.length) {
      const completed = res.data.find((r) => r.status === 'completed');
      const paused = res.data.find(
        (r) => r.status === 'human_review_required' || r.status === 'running',
      );
      return paused?.run_id ?? completed?.run_id ?? res.data[0].run_id ?? null;
    }
  } catch {
    return null;
  }
  return null;
}

/** 从最新 Pipeline run 加载假设评估阶段的红蓝对抗 / 集成评审 / 演化候选。 */
export function useHypothesisReviewExtras(
  projectId?: string,
  latestRunId?: string | null,
  revalidateKey?: number,
): HypothesisReviewExtras & { loading: boolean; runId: string | null } {
  const [extras, setExtras] = useState<HypothesisReviewExtras>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [runId, setRunId] = useState<string | null>(latestRunId ?? null);

  useEffect(() => {
    if (!projectId) {
      setExtras(EMPTY);
      setRunId(null);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const resolved = await resolveRunId(projectId, latestRunId);
        if (!resolved || cancelled) {
          if (!cancelled) {
            setExtras(EMPTY);
            setRunId(null);
          }
          return;
        }
        if (!cancelled) setRunId(resolved);
        const detail = await pipelineService.getRunDetail(resolved);
        if (cancelled) return;
        if (detail.code === 200 && detail.data?.stages) {
          setExtras(extractHypothesisReviewExtras(detail.data.stages));
        } else {
          setExtras(EMPTY);
        }
      } catch {
        if (!cancelled) {
          setExtras(EMPTY);
          setRunId(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, latestRunId, revalidateKey]);

  return { ...extras, loading, runId };
}
