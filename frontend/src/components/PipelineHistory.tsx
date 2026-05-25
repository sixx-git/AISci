import { useState, useEffect } from 'react';
import { Clock, ChevronDown, ChevronUp, CheckCircle, AlertCircle } from 'lucide-react';
import type { PipelineRunSummary, PipelineRunDetail } from '@/types';
import { pipelineApi } from '@/lib/api';
import { StatusBadge } from '@/components/StatusBadge';
import { Card } from '@/components/Card';

const stageNameMap: Record<string, string> = {
  'problem_understanding': '问题理解',
  'literature_mining': '文献挖掘',
  'knowledge_gaps': '知识缺口',
  'knowledge_gap': '知识缺口',
  'hypothesis_generation': '假设生成',
  'hypothesis_review': '假设评估',
  'experiment_design': '实验设计',
  'small_validation': '小样验证',
  'report_generation': '报告生成',
};

interface PipelineHistoryProps {
  projectId: string;
  onSelectRun?: (run: PipelineRunDetail) => void;
}

export function PipelineHistory({ projectId, onSelectRun }: PipelineHistoryProps) {
  const [runs, setRuns] = useState<PipelineRunSummary[]>([]);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [selectedRunDetail, setSelectedRunDetail] = useState<PipelineRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    loadRuns();
  }, [projectId]);

  const loadRuns = async () => {
    setLoading(true);
    try {
      const response = await pipelineApi.getRuns(projectId);
      if (response.code === 200) {
        setRuns(response.data || []);
      }
    } catch (error) {
      console.error('加载运行历史失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleRun = async (runId: string) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      setSelectedRunDetail(null);
      return;
    }

    setLoadingDetail(true);
    try {
      const response = await pipelineApi.getRunDetail(runId);
      if (response.code === 200) {
        setSelectedRunDetail(response.data);
        setExpandedRunId(runId);
        if (onSelectRun) {
          onSelectRun(response.data);
        }
      }
    } catch (error) {
      console.error('加载运行详情失败:', error);
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes > 0) {
      return `${minutes}分${remainingSeconds}秒`;
    }
    return `${remainingSeconds}秒`;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <Card title="运行历史" subtitle="历史 Pipeline 运行记录">
        <div className="text-center py-8 text-gray-400">加载中...</div>
      </Card>
    );
  }

  return (
    <Card title="运行历史" subtitle="历史 Pipeline 运行记录">
      {runs.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Clock className="w-10 h-10 mx-auto mb-3 text-gray-600" />
          <p>暂无运行记录</p>
        </div>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <div key={run.id} className="border border-gray-700 rounded-lg overflow-hidden">
              <div 
                className="flex items-center justify-between p-4 bg-gray-900/30 cursor-pointer hover:bg-gray-800/50 transition-all"
                onClick={() => toggleRun(run.run_id)}
              >
                <div className="flex items-center gap-3">
                  {run.status === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : run.status === 'failed' ? (
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  ) : (
                    <Clock className="w-5 h-5 text-yellow-500" />
                  )}
                  <div>
                    <p className="text-sm text-white font-medium">{run.research_question}</p>
                    <p className="text-xs text-gray-400">
                      {formatDate(run.created_at)} · 耗时: {formatDuration(run.total_duration_ms)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={run.status as any} />
                  {expandedRunId === run.run_id ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </div>
              </div>

              {expandedRunId === run.run_id && (
                <div className="p-4 border-t border-gray-700">
                  {loadingDetail ? (
                    <div className="text-center py-4 text-gray-400">加载详情中...</div>
                  ) : selectedRunDetail && selectedRunDetail.stages.length > 0 ? (
                    <div className="space-y-3">
                      {selectedRunDetail.stages.map((stage) => (
                        <div key={stage.id} className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-lg">
                          <div className="w-2 h-2 rounded-full flex-shrink-0" 
                            style={{ backgroundColor: stage.status === 'completed' ? '#22c55e' : stage.status === 'failed' ? '#ef4444' : '#eab308' }} 
                          />
                          <div className="flex-1">
                            <div className="flex justify-between items-center">
                              <p className="text-sm text-white">{stageNameMap[stage.stage] || stage.stage}</p>
                              <StatusBadge status={stage.status as any} />
                            </div>
                            {stage.duration_ms && (
                              <p className="text-xs text-gray-400">耗时: {formatDuration(stage.duration_ms)}</p>
                            )}
                            {stage.error_message && (
                              <p className="text-xs text-red-400 mt-1">错误: {stage.error_message}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-4 text-gray-400">暂无阶段信息</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
