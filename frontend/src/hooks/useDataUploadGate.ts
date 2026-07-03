import { useCallback, useEffect, useState } from 'react';
import { pipelineService } from '@/services/pipelineService';
import { quickReportService, type QuickReportStatus } from '@/services/quickReportService';

export interface DataUploadGateState {
  awaiting: boolean;
  runId: string | null;
  projectId: string | null;
  pendingCount: number;
  uploadedCount: number;
  canResume: boolean;
  status: QuickReportStatus | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useDataUploadGate(
  projectId: string | undefined,
  runId?: string | null,
): DataUploadGateState {
  const [gate, setGate] = useState<DataUploadGateState>({
    awaiting: false,
    runId: runId ?? null,
    projectId: projectId ?? null,
    pendingCount: 0,
    uploadedCount: 0,
    canResume: false,
    status: null,
    loading: Boolean(projectId),
    refresh: async () => {},
  });

  const refresh = useCallback(async () => {
    if (!projectId) {
      setGate((g) => ({ ...g, loading: false, awaiting: false }));
      return;
    }

    let effectiveRunId = runId ?? null;

    if (!effectiveRunId) {
      try {
        const runsRes = await pipelineService.getRuns(projectId);
        const latest = runsRes.data?.[0];
        if (latest?.run_id) effectiveRunId = latest.run_id;
      } catch {
        /* ignore */
      }
    }

    if (!effectiveRunId) {
      setGate((g) => ({
        ...g,
        loading: false,
        awaiting: false,
        runId: null,
        projectId,
      }));
      return;
    }

    try {
      const detailRes = await pipelineService.getRunDetail(effectiveRunId);
      const meta = detailRes.data?.extra_metadata as Record<string, unknown> | undefined;
      const duGate = meta?.data_upload_gate as Record<string, unknown> | undefined;
      const isQuickReport = Boolean(meta?.quick_report);

      if (!isQuickReport && !duGate?.paused) {
        setGate((g) => ({
          ...g,
          loading: false,
          awaiting: false,
          runId: effectiveRunId,
          projectId,
        }));
        return;
      }

      const qrRes = await quickReportService.getStatus(effectiveRunId);
      if (qrRes.code === 200 && qrRes.data) {
        const st = qrRes.data;
        setGate({
          awaiting: st.awaiting_data_upload,
          runId: effectiveRunId,
          projectId: st.project_id || projectId,
          pendingCount: st.pending_upload_count,
          uploadedCount: st.uploaded_count ?? 0,
          canResume: st.can_resume ?? false,
          status: st,
          loading: false,
          refresh,
        });
        return;
      }
    } catch {
      /* ignore */
    }

    setGate((g) => ({ ...g, loading: false, runId: effectiveRunId, projectId }));
  }, [projectId, runId]);

  useEffect(() => {
    setGate((g) => ({ ...g, loading: true, refresh }));
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return { ...gate, refresh };
}
