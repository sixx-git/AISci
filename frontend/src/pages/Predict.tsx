import { useCallback, useEffect, useRef, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { PredictSidebar } from '@/components/predict/PredictSidebar';
import { PredictForms } from '@/components/predict/PredictForms';
import { JobStatusPanel } from '@/components/predict/JobStatusPanel';
import { ImpactDetailView } from '@/components/predict/ImpactDetailView';
import {
  predictService,
  type ImpactHistoryItem,
  type ImpactReport,
  type PredictJobStatus,
  type PredictTaskType,
} from '@/services/predictService';
import { getErrorMessage } from '@/lib/errors';

type ViewMode = 'form' | 'detail';

export function Predict() {
  const [history, setHistory] = useState<ImpactHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('form');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ImpactReport | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobStatus, setJobStatus] = useState<PredictJobStatus | null>(null);
  const [maxReportChars, setMaxReportChars] = useState(200000);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const items = await predictService.getHistory();
      setHistory(items);
      setServiceError(null);
    } catch (err) {
      setHistory([]);
      const msg = getErrorMessage(err, '无法连接预测服务');
      setServiceError(
        `${msg}。请确认：1) 后端 :8000 已启动；2) pingfenbiao :8765 已启动（scripts\\run_pingfenbiao.bat）。`,
      );
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    return () => stopPoll();
  }, [loadHistory, stopPoll]);

  const startPolling = useCallback(
    (jobId: string, mode: string) => {
      stopPoll();
      setBusy(true);
      setJobStatus({ job_id: jobId, job_mode: mode as PredictJobStatus['job_mode'], status: 'running', progress: 2 });

      const tick = async () => {
        try {
          const st = await predictService.getStatus(jobId);
          setJobStatus({ ...st, job_id: st.job_id || jobId });
          if (st.status === 'completed' || st.status === 'failed') {
            stopPoll();
            setBusy(false);
            if (st.status === 'completed' && (st.job_mode === 'impact' || mode === 'impact')) {
              await loadHistory();
              setSelectedId(jobId);
              setDetailLoading(true);
              try {
                const report = await predictService.getDetail(jobId);
                setDetail(report);
                setView('detail');
              } catch (err) {
                setServiceError(getErrorMessage(err, '加载预测详情失败'));
              } finally {
                setDetailLoading(false);
              }
            } else if (st.status === 'completed') {
              await loadHistory();
            }
          }
        } catch (err) {
          stopPoll();
          setBusy(false);
          setJobStatus((prev) => ({
            ...(prev || {}),
            job_id: jobId,
            status: 'failed',
            error: getErrorMessage(err, '轮询状态失败'),
          }));
        }
      };

      void tick();
      pollRef.current = setInterval(() => void tick(), 2000);
    },
    [loadHistory, stopPoll],
  );

  const openDetail = useCallback(async (jobId: string) => {
    setSelectedId(jobId);
    setDetailLoading(true);
    setView('detail');
    try {
      const report = await predictService.getDetail(jobId);
      setDetail(report);
      setServiceError(null);
    } catch (err) {
      setDetail(null);
      setServiceError(getErrorMessage(err, '加载预测详情失败'));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleNew = () => {
    stopPoll();
    setBusy(false);
    setSelectedId(null);
    setDetail(null);
    setJobStatus(null);
    setView('form');
  };

  const handleDelete = async (jobId: string) => {
    try {
      setServiceError(null);
      // 先乐观更新侧栏，避免接口慢/历史扫描滞后造成「删了还在」
      setHistory((prev) => prev.filter((it) => it.job_id !== jobId));
      if (selectedId === jobId) handleNew();
      await predictService.deleteImpact(jobId);
      await loadHistory();
    } catch (err) {
      setServiceError(getErrorMessage(err, '删除失败'));
      // 回滚：重新拉取真实历史
      await loadHistory();
    }
  };

  const handleGenerate = async (payload: {
    taskType: PredictTaskType;
    files: FileList;
    apiKey: string;
    saveDir: string;
  }) => {
    const form = new FormData();
    form.append('task_type', payload.taskType);
    form.append('query', '');
    if (payload.apiKey) form.append('api_key', payload.apiKey);
    if (payload.saveDir) form.append('save_dir', payload.saveDir);
    Array.from(payload.files).forEach((f) => form.append('files', f));
    try {
      setServiceError(null);
      const res = await predictService.generate(form);
      startPolling(res.job_id, 'generate');
    } catch (err) {
      setServiceError(getErrorMessage(err, '提交生成任务失败'));
    }
  };

  const handleScore = async (payload: {
    taskFile: File;
    reportFile: File;
    sourceFiles: FileList | null;
    apiKey: string;
    maxReportChars: number;
  }) => {
    const form = new FormData();
    form.append('task_file', payload.taskFile);
    form.append('report_file', payload.reportFile);
    form.append('max_report_chars', String(payload.maxReportChars));
    if (payload.apiKey) form.append('api_key', payload.apiKey);
    if (payload.sourceFiles) {
      Array.from(payload.sourceFiles).forEach((f) => form.append('source_files', f));
    }
    try {
      setServiceError(null);
      const res = await predictService.score(form);
      startPolling(res.job_id, 'score');
    } catch (err) {
      setServiceError(getErrorMessage(err, '提交打分任务失败'));
    }
  };

  const handleImpact = async (payload: {
    pdf: File;
    apiKey: string;
    maxReportChars: number;
    taskLit?: File | null;
    scoresLit?: File | null;
    taskData?: File | null;
    scoresData?: File | null;
    taskClaim?: File | null;
    scoresClaim?: File | null;
    saveDirLit?: string;
    saveDirData?: string;
    saveDirClaim?: string;
  }) => {
    const form = new FormData();
    form.append('files', payload.pdf);
    form.append('max_report_chars', String(payload.maxReportChars));
    if (payload.apiKey) form.append('api_key', payload.apiKey);
    if (payload.taskLit) form.append('task_lit', payload.taskLit);
    if (payload.scoresLit) form.append('scores_lit', payload.scoresLit);
    if (payload.taskData) form.append('task_data', payload.taskData);
    if (payload.scoresData) form.append('scores_data', payload.scoresData);
    if (payload.taskClaim) form.append('task_claim', payload.taskClaim);
    if (payload.scoresClaim) form.append('scores_claim', payload.scoresClaim);
    if (payload.saveDirLit) form.append('save_dir_lit', payload.saveDirLit);
    if (payload.saveDirData) form.append('save_dir_data', payload.saveDirData);
    if (payload.saveDirClaim) form.append('save_dir_claim', payload.saveDirClaim);
    try {
      setServiceError(null);
      const res = await predictService.impact(form);
      startPolling(res.job_id, 'impact');
    } catch (err) {
      setServiceError(getErrorMessage(err, '提交预测任务失败'));
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <PageHeader
        title="预测"
        subtitle="评分表生成 · 报告打分 · 科学影响力预测（pingfenbiao）"
        className="mb-5"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 lg:gap-0 items-stretch min-h-[640px] rounded-xl overflow-hidden border border-[#e5e5e5] shadow-sm bg-[#f5f5f5]">
        <div className="lg:col-span-3 lg:min-h-[640px]">
          <PredictSidebar
            items={history}
            loading={historyLoading}
            selectedId={selectedId}
            onSelect={(id) => void openDetail(id)}
            onDelete={(id) => void handleDelete(id)}
            onNew={handleNew}
            serviceError={serviceError}
          />
        </div>

        <div className="lg:col-span-9 bg-white min-h-[640px] text-[#1a1a1a]">
          <div className="px-8 py-9">
            {view === 'detail' ? (
              detailLoading ? (
                <p className="text-[0.85rem] text-[#888] py-16 text-center">正在加载预测详情…</p>
              ) : detail && selectedId ? (
                <ImpactDetailView
                  jobId={selectedId}
                  report={detail}
                  onBack={handleNew}
                />
              ) : (
                <p className="text-[0.85rem] text-[#888] py-16 text-center">暂无详情数据</p>
              )
            ) : (
              <>
                <PredictForms
                  busy={busy}
                  maxReportChars={maxReportChars}
                  onMaxReportCharsChange={setMaxReportChars}
                  onGenerate={(p) => void handleGenerate(p)}
                  onScore={(p) => void handleScore(p)}
                  onImpact={(p) => void handleImpact(p)}
                />
                <div className="max-w-[640px] mx-auto">
                  <JobStatusPanel status={jobStatus} busy={busy} />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
