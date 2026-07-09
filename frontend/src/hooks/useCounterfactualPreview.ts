import { useEffect, useState } from 'react';
import { pipelineService } from '@/services/pipelineService';
import type { CounterfactualPreviewData } from '@/types';

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

function extractCounterfactualPreview(outputData: unknown): CounterfactualPreviewData | null {
  if (!outputData || typeof outputData !== 'object') return null;
  const raw = (outputData as Record<string, unknown>).counterfactual_preview;
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;
  if (data.skipped) return null;
  const scenarios = Array.isArray(data.scenarios) ? data.scenarios : [];
  if (!scenarios.length && !data.summary) return null;
  return data as CounterfactualPreviewData;
}

/** 从最新 Pipeline run 的 output_data 加载反事实预演结果。 */
export function useCounterfactualPreview(
  projectId?: string,
  latestRunId?: string | null,
  revalidateKey?: number,
): { preview: CounterfactualPreviewData | null; loading: boolean } {
  const [preview, setPreview] = useState<CounterfactualPreviewData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setPreview(null);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      try {
        const runId = await resolveRunId(projectId, latestRunId);
        if (!runId || cancelled) {
          if (!cancelled) setPreview(null);
          return;
        }
        const detail = await pipelineService.getRunDetail(runId);
        if (cancelled) return;
        if (detail.code === 200) {
          const fromOutput = extractCounterfactualPreview(detail.data?.output_data);
          if (fromOutput) {
            setPreview(fromOutput);
            return;
          }
          const checkpoint = detail.data?.extra_metadata?.pipeline_checkpoint as
            | { results?: Record<string, unknown> }
            | undefined;
          setPreview(extractCounterfactualPreview(checkpoint?.results));
        } else {
          setPreview(null);
        }
      } catch {
        if (!cancelled) setPreview(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, latestRunId, revalidateKey]);

  return { preview, loading };
}
