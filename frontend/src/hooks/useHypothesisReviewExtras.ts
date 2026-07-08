import { useEffect, useState } from 'react';
import { pipelineService } from '@/services/pipelineService';
import {
  extractHypothesisReviewExtras,
  type HypothesisReviewExtras,
} from '@/lib/pipelineReviewExtras';

const EMPTY: HypothesisReviewExtras = {
  proCon: null,
  ensemble: null,
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
      return completed?.run_id ?? res.data[0].run_id ?? null;
    }
  } catch {
    return null;
  }
  return null;
}

/** 从最新 Pipeline run 加载假设评估阶段的红蓝对抗 / 集成评审数据。 */
export function useHypothesisReviewExtras(
  projectId?: string,
  latestRunId?: string | null,
  revalidateKey?: number,
): HypothesisReviewExtras & { loading: boolean } {
  const [extras, setExtras] = useState<HypothesisReviewExtras>(EMPTY);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setExtras(EMPTY);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const runId = await resolveRunId(projectId, latestRunId);
        if (!runId || cancelled) {
          if (!cancelled) setExtras(EMPTY);
          return;
        }
        const detail = await pipelineService.getRunDetail(runId);
        if (cancelled) return;
        if (detail.code === 200 && detail.data?.stages) {
          setExtras(extractHypothesisReviewExtras(detail.data.stages));
        } else {
          setExtras(EMPTY);
        }
      } catch {
        if (!cancelled) setExtras(EMPTY);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, latestRunId, revalidateKey]);

  return { ...extras, loading };
}
