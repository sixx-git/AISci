import { useState, useCallback, useEffect } from 'react';
import { Terminal } from 'lucide-react';
import { Card } from './Card';
import { RunLogTable } from './RunLogTable';
import { RunLogDetail } from './RunLogDetail';
import { RunLogStageStream } from './RunLogStageStream';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { pipelineService } from '@/services';
import type { RunLog, PipelineRunSummary, PipelineStageExecutionSummary } from '@/types';

interface RunLogsPageProps {
  projectId?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
}

// 阶段英文 → 中文映射
const STAGE_CN: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '假设评估',
  experiment_design: '实验设计',
  small_validation: '小样验证',
  report_generation: '报告生成',
};

// 状态映射
const STATUS_MAP: Record<string, RunLog['status']> = {
  completed: 'success',
  running: 'running',
  failed: 'failed',
  pending: 'pending',
  human_review_required: 'pending',
};

// 从 PipelineStageExecution 映射到 RunLog
function mapStageToRunLog(
  stage: PipelineStageExecutionSummary,
  run: PipelineRunSummary,
): RunLog {
  const startStr = stage.started_at && new Date(stage.started_at).toLocaleString('zh-CN');
  const durationStr = stage.duration_ms
    ? `${(stage.duration_ms / 1000).toFixed(0)}s`
    : '-';

  const inputSummary = stage.input_data
    ? JSON.stringify(stage.input_data).slice(0, 200)
    : run.research_question?.slice(0, 200) || '-';

  const outputSnapshot = stage.output_data
    ? JSON.stringify(stage.output_data, null, 2).slice(0, 500)
    : '-';

  const modelParams = stage.model_parameters as Record<string, unknown> | undefined;
  const stageCn = STAGE_CN[stage.stage] || '实验执行';

  return {
    id: stage.id,
    projectName: `Pipeline #${run.run_id?.slice(0, 8) || 'unknown'}`,
    runTime: startStr || run.started_at || '-',
    stage: stageCn as RunLog['stage'],
    model: stage.model_used || 'unknown',
    promptVersion: (modelParams?.prompt_version as string) || '-',
    duration: durationStr,
    status: STATUS_MAP[stage.status] || 'pending',
    inputSummary,
    outputSnapshot,
    errorMessage: stage.error_message || undefined,
    modelParams: modelParams
      ? Object.entries(modelParams).reduce(
          (acc, [k, v]) => ({ ...acc, [k]: String(v) }),
          {} as Record<string, string>,
        )
      : undefined,
    timestampStart: stage.started_at || undefined,
    timestampEnd: stage.completed_at || undefined,
    temperature: modelParams?.temperature as string | undefined,
    tokenCount: stage.token_count || undefined,
    runId: run.run_id,
  };
}

export function RunLogsPage({
  projectId,
  compact: _compact = false,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: RunLogsPageProps) {
  const [logs, setLogs] = useState<RunLog[]>([]);
  const [selectedLog, setSelectedLog] = useState<RunLog | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  // 加载运行日志
  useEffect(() => {
    if (!projectId) {
      setIsLoading(false);
      return;
    }

    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const res = await pipelineService.getRuns(projectId);

        if (res.code !== 200 || !res.data || res.data.length === 0) {
          setLogs([]);
          return;
        }

        const runs: PipelineRunSummary[] = res.data;

        // 并发加载每个 run 的详情（获取 stages）
        const detailResults = await Promise.allSettled(
          runs.map((r) => pipelineService.getRunDetail(r.run_id)),
        );

        const allLogs: RunLog[] = [];
        detailResults.forEach((result) => {
          if (result.status === 'fulfilled' && result.value.code === 200 && result.value.data) {
            const detail = result.value.data;
            const run = runs.find((r) => r.run_id === detail.run_id)!;
            detail.stages?.forEach((stage) => {
              allLogs.push(mapStageToRunLog(stage, run));
            });
          }
        });

        setLogs(allLogs);
        if (allLogs.length > 0) {
          setSelectedLog(allLogs[0]);
        }
      } catch (err) {
        console.error('加载运行日志失败:', err);
        setErrorMsg(err instanceof Error ? err.message : '加载失败');
      } finally {
        setIsLoading(false);
      }
    })();
  }, [projectId, _revalidateKey, _latestRunId, reloadTick]);

  const handleSelect = useCallback((log: RunLog) => {
    setSelectedLog(log);
  }, []);

  const pageHeader = (
    <div className="mb-6">
      <h1 className="text-3xl font-bold text-bp-text mb-1">运行日志</h1>
      <p className="text-bp-muted text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
    </div>
  );

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto">
        {pageHeader}
        <Card>
          <LoadingState message="正在加载运行日志..." />
        </Card>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="max-w-7xl mx-auto">
        {pageHeader}
        <Card>
          <ErrorState
            message={errorMsg}
            onRetry={() => setReloadTick((t) => t + 1)}
          />
        </Card>
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="max-w-7xl mx-auto">
        {pageHeader}
        <Card>
          <EmptyState
            icon={<Terminal className="w-8 h-8" />}
            title="暂无运行日志"
            description="运行一次 Pipeline 后这里会显示日志"
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {pageHeader}

      {/* 三栏布局：左列表 · 中详情 · 右阶段流 */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
        <div className="xl:col-span-5">
          <RunLogTable
            logs={logs}
            selectedId={selectedLog?.id || null}
            onSelect={handleSelect}
          />
        </div>

        <div className="xl:col-span-4">
          <Card className="min-h-[520px]">
            <RunLogDetail log={selectedLog} />
          </Card>
        </div>

        <div className="xl:col-span-3">
          <RunLogStageStream
            logs={logs}
            selectedLog={selectedLog}
            onSelect={handleSelect}
          />
        </div>
      </div>
    </div>
  );
}