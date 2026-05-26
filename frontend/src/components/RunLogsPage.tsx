import { useState, useCallback, useEffect } from 'react';
import { Terminal, Loader2 } from 'lucide-react';
import { Card } from './Card';
import { RunLogTable } from './RunLogTable';
import { RunLogDetail } from './RunLogDetail';
import { pipelineService } from '@/services';
import env from '@/config/env';
import { MOCK_RUN_LOGS } from '@/data/mockData';
import type { RunLog, PipelineRunSummary, PipelineStageExecutionSummary } from '@/types';

interface RunLogsPageProps {
  projectId?: string;
  compact?: boolean;
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

export function RunLogsPage({ projectId, compact: _compact = false }: RunLogsPageProps) {
  const [logs, setLogs] = useState<RunLog[]>([]);
  const [selectedLog, setSelectedLog] = useState<RunLog | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 加载运行日志
  useEffect(() => {
    if (!projectId && !env.USE_MOCK) {
      setIsLoading(false);
      return;
    }

    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const res = await pipelineService.getRuns(projectId || '');

        if (res.code !== 200 || !res.data || res.data.length === 0) {
          if (env.USE_MOCK) {
            setLogs(MOCK_RUN_LOGS);
            setSelectedLog(MOCK_RUN_LOGS[0]);
          } else {
            setLogs([]);
          }
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
        if (env.USE_MOCK) {
          setLogs(MOCK_RUN_LOGS);
          setSelectedLog(MOCK_RUN_LOGS[0]);
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, [projectId]);

  const handleSelect = useCallback((log: RunLog) => {
    setSelectedLog(log);
  }, []);

  // 加载中
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">运行日志</h1>
          <p className="text-gray-400 text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
        </div>
        <Card className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
          <span className="text-gray-400">正在加载运行日志...</span>
        </Card>
      </div>
    );
  }

  // 错误
  if (errorMsg) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">运行日志</h1>
          <p className="text-gray-400 text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
        </div>
        <Card className="py-12 text-center">
          <Terminal className="w-12 h-12 text-red-400/50 mx-auto mb-4" />
          <p className="text-red-400 text-sm mb-1">加载失败</p>
          <p className="text-gray-500 text-xs">{errorMsg}</p>
        </Card>
      </div>
    );
  }

  // 无数据
  if (logs.length === 0) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-1">运行日志</h1>
          <p className="text-gray-400 text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
        </div>
        <Card className="py-12 text-center">
          <Terminal className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 text-sm">暂无运行日志</p>
          <p className="text-gray-600 text-xs mt-1">运行一次 Pipeline 后这里会显示日志</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-1">运行日志</h1>
        <p className="text-gray-400 text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
      </div>

      {/* 表格区域 */}
      <RunLogTable
        logs={logs}
        selectedId={selectedLog?.id || null}
        onSelect={handleSelect}
      />

      {/* 详情面板 */}
      <div className="mt-6">
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="w-4 h-4 text-primary-400" />
            <div>
              <h3 className="text-sm font-semibold text-white">运行详情</h3>
              <p className="text-xs text-gray-500">输入摘要 · 输出快照 · 模型参数 · 错误信息</p>
            </div>
          </div>
          <RunLogDetail
            log={selectedLog}
            onClose={() => {}}
          />
        </Card>
      </div>
    </div>
  );
}