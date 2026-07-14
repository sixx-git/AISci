import { useCallback, useEffect, useState } from 'react';
import iterativeExperimentService from '@/services/iterativeExperimentService';
import hypothesisService from '@/services/hypothesisService';
import { selectedHypothesisKey } from '@/lib/storageKeys';
import { getErrorMessage } from '@/lib/errors';
import type { DataConfig, IterativeExperiment, RunMode } from '@/types/iterativeExperiment';
import { ExperimentList } from './ExperimentList';
import { NewExperimentForm } from './NewExperimentForm';
import { ExperimentDetail } from './ExperimentDetail';

type View = 'list' | 'new' | 'detail';

interface IterativeExperimentPageProps {
  projectId: string;
  projectMode?: string;
  /** URL 带入的假设 ID，用于预填 */
  hypothesisId?: string | null;
}

export function IterativeExperimentPage({
  projectId,
  hypothesisId,
}: IterativeExperimentPageProps) {
  const [view, setView] = useState<View>('list');
  const [experiments, setExperiments] = useState<IterativeExperiment[]>([]);
  const [reportIds, setReportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [primaryHypothesisText, setPrimaryHypothesisText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newFormKey, setNewFormKey] = useState(0);
  const [draftHypothesis, setDraftHypothesis] = useState('');

  const reload = useCallback(async () => {
    const { experiments: items, reportExperimentIds } =
      await iterativeExperimentService.list(projectId);
    setExperiments(items);
    setReportIds(reportExperimentIds);
  }, [projectId]);

  useEffect(() => {
    void reload().catch((err: unknown) => {
      setError(getErrorMessage(err, '加载实验列表失败'));
    });
  }, [reload]);

  useEffect(() => {
    let cancelled = false;
    async function loadPrimary() {
      try {
        const res = await hypothesisService.getProjectHypotheses(projectId);
        if (cancelled || res.code !== 200 || !Array.isArray(res.data)) return;
        const preferredId =
          hypothesisId
          || localStorage.getItem(selectedHypothesisKey(projectId))
          || '';
        const primary =
          res.data.find((h) => h.id === preferredId)
          || res.data.find((h) => h.priority === 1)
          || res.data[0];
        if (primary?.hypothesis) setPrimaryHypothesisText(primary.hypothesis);
      } catch {
        /* ignore — UI 仍可用 */
      }
    }
    void loadPrimary();
    return () => { cancelled = true; };
  }, [projectId, hypothesisId]);

  const selected = selectedId
    ? experiments.find((e) => e.id === selectedId) || null
    : null;

  const withBusy = async (fn: () => void | Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await reload();
    } catch (err: unknown) {
      setError(getErrorMessage(err, '操作失败'));
    } finally {
      setBusy(false);
    }
  };

  if (view === 'new') {
    return (
      <NewExperimentForm
        key={newFormKey}
        initialHypothesis={draftHypothesis || primaryHypothesisText}
        busy={busy}
        onBack={() => setView('list')}
        onFillPrimaryHypothesis={() => {
          if (!primaryHypothesisText) {
            setError('未找到主假设，请先在「候选假设」页设定主假设');
            return;
          }
          setError(null);
          setDraftHypothesis(primaryHypothesisText);
          setNewFormKey((k) => k + 1);
        }}
        onCreate={(input) => {
          void withBusy(async () => {
            const exp = await iterativeExperimentService.create(projectId, input);
            setSelectedId(exp.id);
            setView('detail');
          });
        }}
      />
    );
  }

  if (view === 'detail' && selected) {
    return (
      <ExperimentDetail
        experiment={selected}
        busy={busy}
        error={error}
        onBack={() => {
          setSelectedId(null);
          setError(null);
          setView('list');
          void reload();
        }}
        onDelete={() => {
          void withBusy(async () => {
            await iterativeExperimentService.delete(projectId, selected.id);
            setSelectedId(null);
            setView('list');
          });
        }}
        onRecommend={(feedback) => {
          void withBusy(async () => {
            await iterativeExperimentService.recommendDatasets(projectId, selected.id, feedback);
          });
        }}
        onDesignScript={(dataConfig: DataConfig) => {
          void withBusy(async () => {
            await iterativeExperimentService.designScript(projectId, selected.id, dataConfig);
          });
        }}
        onSetRunMode={(mode: RunMode) => {
          void withBusy(async () => {
            await iterativeExperimentService.setRunMode(projectId, selected.id, mode);
          });
        }}
        onRunIteration={() => {
          void withBusy(async () => {
            await iterativeExperimentService.runIteration(projectId, selected.id);
          });
        }}
        onRunToCompletion={() => {
          void withBusy(async () => {
            await iterativeExperimentService.runToCompletion(projectId, selected.id);
          });
        }}
        onSubmitFeedback={(text) => {
          void withBusy(async () => {
            await iterativeExperimentService.submitFeedback(projectId, selected.id, text);
          });
        }}
        onRedesignFromFeedback={(text) => {
          void withBusy(async () => {
            await iterativeExperimentService.redesignFromFeedback(projectId, selected.id, text);
          });
        }}
      />
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="px-3 py-2 rounded-bp border border-danger-500/30 bg-danger-500/10 text-xs text-danger-300">
          {error}
        </div>
      )}
      <ExperimentList
        experiments={experiments}
        reportIds={reportIds}
        onNew={() => {
          setError(null);
          setDraftHypothesis(primaryHypothesisText);
          setNewFormKey((k) => k + 1);
          setView('new');
        }}
        onOpen={(id) => {
          setSelectedId(id);
          setError(null);
          setView('detail');
        }}
        onDelete={(id) => {
          void withBusy(async () => {
            await iterativeExperimentService.delete(projectId, id);
          });
        }}
        onToggleReport={(id) => {
          void withBusy(async () => {
            const ids = await iterativeExperimentService.toggleReport(projectId, id);
            setReportIds(ids);
          });
        }}
      />
    </div>
  );
}
