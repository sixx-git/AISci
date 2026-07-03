import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Zap, FileText, Loader2, CheckCircle2, AlertTriangle, ArrowRight, Circle,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { PipelineProgress } from '@/components/PipelineProgress';
import { RequiredDatasetUploadPanel } from '@/components/RequiredDatasetUploadPanel';
import { DataUploadGateFloating } from '@/components/DataUploadGateFloating';
import { buildProjectTabUrl } from '@/lib/projectNavigation';
import { quickReportService, type QuickReportStatus } from '@/services/quickReportService';
import { pipelineService } from '@/services/pipelineService';

type Phase = 'form' | 'running' | 'awaiting_upload' | 'completed' | 'failed';

const STAGE_CN: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  data_acquisition: '数据采集',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '假设评估',
  experiment_design: '实验设计',
  small_validation: '小样验证',
  report_generation: '报告生成',
};

export function QuickReportPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>('form');
  const [questionName, setQuestionName] = useState('');
  const [fileDescription, setFileDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [projectId, setProjectId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<QuickReportStatus | null>(null);
  const [progressNodes, setProgressNodes] = useState<Array<{
    id: string;
    label: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    icon: typeof Circle;
  }>>([]);
  const [resuming, setResuming] = useState(false);
  const [gateDismissed, setGateDismissed] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refreshProgress = useCallback(async (rid: string) => {
    const pipeRes = await pipelineService.getStatus(rid);
    if (pipeRes.code === 200 && pipeRes.data?.stages) {
      setProgressNodes(
        pipeRes.data.stages.map((s) => ({
          id: s.stage,
          label: STAGE_CN[s.stage] || s.stage,
          status: (s.status === 'completed'
            ? 'completed'
            : s.status === 'failed'
              ? 'error'
              : s.status === 'running'
                ? 'running'
                : 'pending') as 'pending' | 'running' | 'completed' | 'error',
          icon: Circle,
        })),
      );
    }
  }, []);

  const pollStatus = useCallback(async (rid: string, _pid: string) => {
    try {
      const [qrRes] = await Promise.all([
        quickReportService.getStatus(rid),
        refreshProgress(rid),
      ]);

      if (qrRes.code !== 200 || !qrRes.data) return;
      const st = qrRes.data;
      setStatus(st);

      if (st.awaiting_data_upload) {
        setPhase('awaiting_upload');
        setGateDismissed(false);
        stopPolling();
        return;
      }

      if (st.status === 'completed') {
        setPhase('completed');
        stopPolling();
        return;
      }

      if (st.status === 'failed' || st.status === 'cancelled') {
        setPhase('failed');
        setError('Pipeline 执行失败，请前往项目工作流查看详情');
        stopPolling();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '状态轮询失败');
    }
  }, [refreshProgress, stopPolling]);

  const startPolling = useCallback((rid: string, pid: string) => {
    stopPolling();
    pollStatus(rid, pid);
    pollRef.current = setInterval(() => pollStatus(rid, pid), 4000);
  }, [pollStatus, stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleStart = async (e: FormEvent) => {
    e.preventDefault();
    if (!questionName.trim() || !fileDescription.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      const res = await quickReportService.start(questionName.trim(), fileDescription.trim());
      if (res.code !== 200 || !res.data) {
        setError(res.message || '启动失败');
        return;
      }
      setProjectId(res.data.project_id);
      setRunId(res.data.run_id);
      setPhase('running');
      startPolling(res.data.run_id, res.data.project_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '启动失败';
      if (/timeout|ECONNREFUSED|Network Error|502|503/i.test(msg)) {
        setError(
          `${msg}。请确认后端已启动（backend 目录运行 uvicorn），刷新页面后在首页查看是否已有运行中的项目。`,
        );
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleResume = async (force = false) => {
    if (!runId || !projectId) return;
    setResuming(true);
    setError(null);
    try {
      const res = await quickReportService.resume(runId, force);
      if (res.code !== 200) {
        setError(res.message || '继续失败');
        return;
      }
      setPhase('running');
      startPolling(runId, projectId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '继续失败');
    } finally {
      setResuming(false);
    }
  };

  const goToDatasetPage = useCallback(() => {
    if (!projectId || !runId) return;
    navigate(buildProjectTabUrl(projectId, 'datasets', {
      subtab: 'required-datasets',
      run_id: runId,
    }));
  }, [navigate, projectId, runId]);

  const handleUploadResumed = useCallback(() => {
    if (!runId || !projectId) return;
    setPhase('running');
    setGateDismissed(true);
    startPolling(runId, projectId);
  }, [runId, projectId, startPolling]);

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="一键生成报告"
        subtitle="输入研究问题与数据描述，自动生成研究报告"
      />

      {phase === 'form' && (
        <Card>
          <form onSubmit={handleStart} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-bp-text mb-1.5">
                研究问题名称 <span className="text-danger-400">*</span>
              </label>
              <input
                type="text"
                value={questionName}
                onChange={(e) => setQuestionName(e.target.value)}
                placeholder="例如：非小细胞肺癌免疫治疗疗效预测"
                className="input-field w-full py-2.5"
                maxLength={200}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-bp-text mb-1.5">
                数据 / 文件描述 <span className="text-danger-400">*</span>
              </label>
              <textarea
                value={fileDescription}
                onChange={(e) => setFileDescription(e.target.value)}
                placeholder="描述您已有的数据、期望使用的公开数据集、文件格式或研究场景…"
                className="input-field w-full py-2.5 min-h-[120px] resize-y"
                maxLength={2000}
                required
              />
              <p className="text-xs text-bp-muted mt-1">
                系统将据此自动检索文献与数据；无需事先上传 PDF，但若外部库仅提供下载链接，运行中会提示您补传。
              </p>
            </div>

            {error && (
              <p className="text-sm text-danger-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
              </p>
            )}

            <div className="flex flex-wrap gap-3 pt-2">
              <Button
                type="submit"
                icon={<Zap className="w-4 h-4" />}
                disabled={submitting || !questionName.trim() || !fileDescription.trim()}
              >
                {submitting ? '正在启动…' : '开始生成报告'}
              </Button>
              <Link to="/projects/new" className="text-sm text-bp-muted hover:text-bp-cyan self-center">
                需要完整项目配置？创建新项目 →
              </Link>
            </div>
          </form>
        </Card>
      )}

      {(phase === 'running' || phase === 'awaiting_upload' || phase === 'completed' || phase === 'failed') && (
        <div className="space-y-4">
          <Card title="生成进度" subtitle={runId ? `run: ${runId.slice(0, 8)}…` : undefined}>
            {progressNodes.length > 0 && (
              <PipelineProgress nodes={progressNodes} />
            )}
            {phase === 'running' && (
              <div className="flex items-center gap-2 mt-4 text-sm text-bp-cyan">
                <Loader2 className="w-4 h-4 animate-spin" />
                全自动执行中，请稍候…
              </div>
            )}
          </Card>

          {phase === 'awaiting_upload' && projectId && runId && !gateDismissed && (
            <DataUploadGateFloating
              pendingCount={status?.pending_upload_count ?? 0}
              uploadedCount={status?.uploaded_count ?? 0}
              onGoToDatasets={goToDatasetPage}
              onDismiss={() => setGateDismissed(true)}
            />
          )}

          {phase === 'awaiting_upload' && projectId && (
            <RequiredDatasetUploadPanel
              projectId={projectId}
              runId={runId}
              autoResumeOnUpload
              onResumed={handleUploadResumed}
            />
          )}

          {phase === 'awaiting_upload' && projectId && (
            <Card className="border-bp-border/60">
              <p className="text-sm text-bp-muted mb-3">
                也可在
                <button
                  type="button"
                  className="text-bp-cyan hover:underline mx-1"
                  onClick={goToDatasetPage}
                >
                  项目数据集页面
                </button>
                完成上传；上传至少 1 个数据集后将自动继续后续流程。
              </p>
              {error && (
                <p className="text-sm text-danger-300 mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> {error}
                </p>
              )}
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  icon={<ArrowRight className="w-4 h-4" />}
                  onClick={goToDatasetPage}
                >
                  打开数据集页面
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => handleResume(true)}
                  disabled={resuming}
                >
                  跳过未上传项（强制继续）
                </Button>
              </div>
            </Card>
          )}

          {phase === 'completed' && projectId && (
            <Card className="border-bp-green/30 bg-bp-green/5">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-8 h-8 text-bp-green shrink-0" />
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-bp-text mb-1">报告已生成</h3>
                  <p className="text-sm text-bp-muted mb-4">
                    全流程已完成。您可在项目内查看假设、实验细节与完整研究报告。
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      icon={<FileText className="w-4 h-4" />}
                      onClick={() => navigate(`/projects/${projectId}?tab=reports`)}
                    >
                      查看报告
                    </Button>
                    <Button
                      variant="secondary"
                      icon={<ArrowRight className="w-4 h-4" />}
                      onClick={() => navigate(`/projects/${projectId}?tab=overview`)}
                    >
                      进入项目
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {phase === 'failed' && projectId && (
            <Card className="border-danger-500/30 bg-danger-500/5">
              <p className="text-sm text-danger-300 mb-3">{error || '执行失败'}</p>
              <Button
                variant="secondary"
                onClick={() => navigate(`/projects/${projectId}?tab=workflow`)}
              >
                前往工作流排查
              </Button>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
