import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import iterativeExperimentService from '@/services/iterativeExperimentService';
import hypothesisService from '@/services/hypothesisService';
import { humanLoopService } from '@/services/humanLoopService';
import { pipelineService } from '@/services/pipelineService';
import { selectedHypothesisKey, activeRunKey, activeRunStatusKey } from '@/lib/storageKeys';
import { getErrorMessage } from '@/lib/errors';
import { navigateToProjectTab } from '@/lib/projectNavigation';
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
  projectMode = 'general',
  hypothesisId,
}: IterativeExperimentPageProps) {
  const navigate = useNavigate();
  const [view, setView] = useState<View>('list');
  const [experiments, setExperiments] = useState<IterativeExperiment[]>([]);
  const [reportIds, setReportIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [primaryHypothesisText, setPrimaryHypothesisText] = useState('');
  const [busy, setBusy] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
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

  const handleGenerateReport = useCallback(async () => {
    if (reportIds.length === 0) {
      setError('请先勾选至少一个用于报告的实验');
      return;
    }
    setGeneratingReport(true);
    setError(null);
    try {
      const runsRes = await pipelineService.getRuns(projectId);
      const runId = runsRes.code === 200 && runsRes.data?.length
        ? runsRes.data[0].run_id
        : null;
      if (!runId) {
        throw new Error('未找到可用的 Pipeline 运行记录，请先在工作流中完成可行性评估');
      }
      const res = await humanLoopService.rerunFromStage({
        project_id: projectId,
        run_id: runId,
        stage: 'report_generation',
        use_human_modified_output: true,
        rerun_mode: 'single_stage',
        human_feedback: `基于迭代实验页勾选实验生成报告：${reportIds.join(', ')}`,
      });
      if (res.code !== 200 || !res.data?.run_id) {
        throw new Error(res.message || '提交报告生成失败');
      }
      const pollRunId = res.data.run_id;
      try {
        localStorage.setItem(activeRunKey(projectId), pollRunId);
        localStorage.setItem(activeRunStatusKey(projectId), 'running');
      } catch { /* ignore */ }
      navigateToProjectTab(navigate, projectId, 'reports');
    } catch (err: unknown) {
      setError(getErrorMessage(err, '生成报告失败'));
    } finally {
      setGeneratingReport(false);
    }
  }, [projectId, reportIds, navigate]);

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
        projectId={projectId}
        projectMode={projectMode}
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
        onExperimentUpdated={(exp) => {
          setExperiments((prev) => prev.map((e) => (e.id === exp.id ? exp : e)));
          void reload();
        }}
        onRecommend={(feedback) => {
          void withBusy(async () => {
            await iterativeExperimentService.recommendDatasets(projectId, selected.id, feedback);
          });
        }}
        onUploadFile={async (file) => {
          setBusy(true);
          setError(null);
          try {
            const out = await iterativeExperimentService.uploadDataset(
              projectId,
              selected.id,
              file,
            );
            await reload();
            return out.data_config;
          } catch (err: unknown) {
            const msg = getErrorMessage(err, '上传失败');
            setError(msg);
            throw new Error(msg);
          } finally {
            setBusy(false);
          }
        }}
        onAutoDetect={async (directoryPath) => {
          setBusy(true);
          setError(null);
          try {
            const out = await iterativeExperimentService.autoDetectProfile(
              projectId,
              selected.id,
              directoryPath,
            );
            return { preview: out.preview, data_config: out.data_config };
          } catch (err: unknown) {
            const msg = getErrorMessage(err, '自动识别失败');
            setError(msg);
            throw new Error(msg);
          } finally {
            setBusy(false);
          }
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
        generatingReport={generatingReport}
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
        onGenerateReport={() => {
          void handleGenerateReport();
        }}
      />
    </div>
  );
}
