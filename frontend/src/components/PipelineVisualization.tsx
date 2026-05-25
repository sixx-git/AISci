import React, { useState } from 'react';
import { 
  Brain, 
  BookOpen, 
  Layout, 
  Sparkles, 
  BarChart, 
  FlaskConical, 
  CheckCircle, 
  FileText,
  ChevronRight,
  XCircle,
  Loader2,
  Clock
} from 'lucide-react';
import { cn } from '../lib/utils';

export interface PipelineStage {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'success' | 'error';
  icon: React.FC<any>;
  output?: any;
  duration?: string;
}

const PIPELINE_STAGES: PipelineStage[] = [
  { id: 'problem', name: '问题理解', icon: Brain, status: 'pending' },
  { id: 'literature', name: '文献挖掘', icon: BookOpen, status: 'pending' },
  { id: 'gaps', name: '知识缺口', icon: Layout, status: 'pending' },
  { id: 'hypothesis', name: '假设生成', icon: Sparkles, status: 'pending' },
  { id: 'evaluation', name: '假设评估', icon: BarChart, status: 'pending' },
  { id: 'experiment', name: '实验设计', icon: FlaskConical, status: 'pending' },
  { id: 'validation', name: '小样验证', icon: CheckCircle, status: 'pending' },
  { id: 'report', name: '报告生成', icon: FileText, status: 'pending' },
];

interface PipelineVisualizationProps {
  stages?: PipelineStage[];
  onStageClick?: (stage: PipelineStage) => void;
}

function getStageIcon(status: PipelineStage['status']) {
  switch (status) {
    case 'pending':
      return <Clock className="w-5 h-5 text-gray-500" />;
    case 'running':
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    case 'success':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case 'error':
      return <XCircle className="w-5 h-5 text-red-400" />;
    default:
      return <Clock className="w-5 h-5 text-gray-500" />;
  }
}

function getStatusColor(status: PipelineStage['status']) {
  switch (status) {
    case 'pending':
      return 'bg-gray-800 border-gray-700 text-gray-400';
    case 'running':
      return 'bg-blue-900/30 border-blue-500/50 text-blue-300';
    case 'success':
      return 'bg-green-900/30 border-green-500/50 text-green-300';
    case 'error':
      return 'bg-red-900/30 border-red-500/50 text-red-300';
    default:
      return 'bg-gray-800 border-gray-700 text-gray-400';
  }
}

function getLineColor(prevStatus: PipelineStage['status'], nextStatus: PipelineStage['status']) {
  if (prevStatus === 'success' && (nextStatus === 'pending' || nextStatus === 'success')) {
    return 'bg-green-500/50';
  }
  if (prevStatus === 'success' && nextStatus === 'running') {
    return 'bg-gradient-to-r from-green-500/50 to-blue-500/50';
  }
  return 'bg-gray-700';
}

function getStatusText(status: PipelineStage['status']) {
  switch (status) {
    case 'pending':
      return '未开始';
    case 'running':
      return '运行中';
    case 'success':
      return '成功';
    case 'error':
      return '失败';
    default:
      return '未开始';
  }
}

export function PipelineVisualization({ 
  stages = PIPELINE_STAGES, 
  onStageClick 
}: PipelineVisualizationProps) {
  const [selectedStage, setSelectedStage] = useState<PipelineStage | null>(null);

  const handleStageClick = (stage: PipelineStage) => {
    setSelectedStage(stage);
    onStageClick?.(stage);
  };

  return (
    <div className="space-y-6">
      {/* Horizontal Pipeline View */}
      <div className="relative overflow-x-auto">
        <div className="flex items-center justify-between min-w-max py-2 pb-4">
          {stages.map((stage, index) => {
            const Icon = stage.icon;
            const isLast = index === stages.length - 1;
            
            return (
              <React.Fragment key={stage.id}>
                {/* Stage Node */}
                <div className="flex flex-col items-center min-w-[100px]">
                  <button
                    onClick={() => handleStageClick(stage)}
                    className={cn(
                      'w-14 h-14 rounded-xl border-2 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg',
                      getStatusColor(stage.status)
                    )}
                  >
                    {stage.status === 'running' ? (
                      <Loader2 className="w-7 h-7 animate-spin" />
                    ) : (
                      <Icon className="w-7 h-7" />
                    )}
                  </button>
                  
                  <div className="mt-2 text-center">
                    <p className="text-sm font-medium text-gray-200">
                      {stage.name}
                    </p>
                    <p className="text-xs mt-1 text-gray-500">
                      {getStatusText(stage.status)}
                    </p>
                    {stage.duration && stage.status === 'success' && (
                      <p className="text-xs text-green-500 mt-1">
                        {stage.duration}
                      </p>
                    )}
                  </div>
                </div>

                {/* Connector */}
                {!isLast && (
                  <div className="flex-1 flex items-center">
                    <div className={cn(
                      'h-1 flex-1 mx-2 rounded-full transition-all duration-500',
                      getLineColor(stage.status, stages[index + 1].status)
                    )} />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Selected Stage Detail */}
      {selectedStage && (
        <div className="border border-gray-700 rounded-xl bg-gray-800/50 p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {getStageIcon(selectedStage.status)}
              <div>
                <h3 className="text-lg font-semibold text-gray-100">
                  {selectedStage.name}
                </h3>
                <p className="text-sm text-gray-500">
                  阶段详情
                </p>
              </div>
            </div>
            <span className={cn(
              'px-3 py-1 rounded-full text-xs font-medium',
              selectedStage.status === 'success' ? 'bg-green-900/50 text-green-300' :
              selectedStage.status === 'error' ? 'bg-red-900/50 text-red-300' :
              selectedStage.status === 'running' ? 'bg-blue-900/50 text-blue-300' :
              'bg-gray-700 text-gray-400'
            )}>
              {getStatusText(selectedStage.status)}
            </span>
          </div>

          <div className="bg-gray-900/80 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-300">
                输出结果 (JSON)
              </span>
            </div>
            <pre className="text-xs text-gray-400 overflow-x-auto font-mono leading-relaxed">
              {JSON.stringify(selectedStage.output || { message: '暂无输出' }, null, 2)}
            </pre>
          </div>

          <button
            onClick={() => setSelectedStage(null)}
            className="mt-4 w-full py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            关闭详情
          </button>
        </div>
      )}

      {/* Vertical Timeline View (for mobile) */}
      <div className="md:hidden space-y-4">
        <h4 className="text-sm font-medium text-gray-400 mb-2">执行详情</h4>
        {stages.map((stage, _index) => {
          const Icon = stage.icon;
          return (
            <div 
              key={stage.id}
              className={cn(
                'flex items-center gap-4 p-3 rounded-lg border transition-all duration-300 cursor-pointer',
                stage.status === 'running' ? 'bg-blue-900/20 border-blue-500/30' :
                stage.status === 'success' ? 'bg-green-900/20 border-green-500/30' :
                stage.status === 'error' ? 'bg-red-900/20 border-red-500/30' :
                'bg-gray-800/50 border-gray-700 hover:border-gray-600'
              )}
              onClick={() => handleStageClick(stage)}
            >
              <div className={cn(
                'w-10 h-10 rounded-full flex items-center justify-center border-2',
                getStatusColor(stage.status)
              )}>
                {stage.status === 'running' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Icon className="w-5 h-5" />
                )}
              </div>
              
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-200">{stage.name}</p>
                  {getStageIcon(stage.status)}
                </div>
                <p className="text-sm text-gray-500">{getStatusText(stage.status)}</p>
                {stage.duration && stage.status === 'success' && (
                  <p className="text-xs text-green-500 mt-1">{stage.duration}</p>
                )}
              </div>
              
              <ChevronRight className="w-4 h-4 text-gray-600" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default PipelineVisualization;
