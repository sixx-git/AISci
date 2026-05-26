import { useState, useCallback } from 'react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import {
  FlaskConical, CheckCircle, XCircle, Database,
  BarChart3, ListChecks, Target, BookOpen,
  AlertTriangle, Lightbulb, FileText, Play,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  MOCK_DETAILED_EXPERIMENT,
} from '@/data/mockData';
import env from '@/config/env';
import type { DetailedExperimentDesign } from '@/types';

interface ExperimentDesignPageProps {
  projectId?: string;
  compact?: boolean;
}

const categoryLabel: Record<string, string> = {
  traditional: '传统方法',
  deep: '深度方法',
  sota: 'SOTA',
};

const categoryColor: Record<string, string> = {
  traditional: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  deep: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  sota: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

function VerifiabilityChecklist({ exp }: { exp: DetailedExperimentDesign }) {
  const items = [
    { label: '是否有数据集', ok: !!(exp.sourceDataset && exp.targetDataset) },
    { label: '是否有基线方法', ok: exp.baselines.length > 0 },
    { label: '是否有评估指标', ok: exp.metrics.length > 0 },
    { label: '是否有实验步骤', ok: exp.steps.length > 0 },
    { label: '是否有预期结果', ok: !!exp.expectedResults },
  ];

  const allOk = items.every((i) => i.ok);

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <ListChecks className="w-4 h-4 text-primary-400" />
        <h3 className="text-sm font-semibold text-white">可验证性检查</h3>
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-sm">
            {item.ok ? (
              <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <span className={item.ok ? 'text-gray-300' : 'text-red-300'}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
      <div className={cn(
        'mt-4 p-2.5 rounded-lg text-xs text-center font-medium',
        allOk ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
        'bg-red-500/10 text-red-400 border border-red-500/20',
      )}>
        {allOk ? '✓ 实验方案可验证' : '✗ 实验方案不完整'}
      </div>
    </Card>
  );
}

export function ExperimentDesignPage({ projectId: _projectId, compact: _compact = false }: ExperimentDesignPageProps) {
  const [exp] = useState<DetailedExperimentDesign>(MOCK_DETAILED_EXPERIMENT);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 2500);
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      {/* ========== 头部 ========== */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">实验设计</h1>
        <p className="text-gray-400">为选定科学假设生成可执行、可复现的验证方案
            {env.USE_MOCK && (
              <span className="ml-2 px-2 py-0.5 bg-amber-500/20 border border-amber-500/30 rounded text-amber-400 text-xs align-baseline">
                演示数据
              </span>
            )}
          </p>
      </div>

      {/* 短暂提示 */}
      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-sm text-primary-300 animate-pulse">
          {alertMsg}
        </div>
      )}

      {/* ========== 操作栏 ========== */}
      <div className="mb-6">
        <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            <div>
              <span className="text-xs text-gray-500">当前主假设</span>
              <p className="text-sm text-white font-medium mt-0.5">{exp.hypothesisTitle}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" size="sm" icon={<Sparkles className="w-4 h-4" />}
              onClick={() => showAlert('实验设计生成中…（模拟）')}>
              生成实验设计
            </Button>
            <Button variant="secondary" size="sm" icon={<Play className="w-4 h-4" />}
              onClick={() => showAlert('小样验证已启动（模拟 5s）')}>
              运行小样验证
            </Button>
            <Button variant="secondary" size="sm" icon={<FileText className="w-4 h-4" />}
              onClick={() => showAlert('跳转至研究报告页面（待对接）')}>
              进入研究报告
            </Button>
          </div>
        </Card>
      </div>

      {/* ========== 主布局 ========== */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧：结构化卡片 */}
        <div className="lg:col-span-3 space-y-5">

          {/* 实验目标 */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-4 h-4 text-blue-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">实验目标</h3>
                <p className="text-xs text-gray-500">Objective</p>
              </div>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{exp.objective}</p>
          </Card>

          {/* 实验方法 */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <FlaskConical className="w-4 h-4 text-purple-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">实验方法</h3>
                <p className="text-xs text-gray-500">Methods</p>
              </div>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{exp.methods}</p>
          </Card>

          {/* 数据集 */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-green-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">数据集</h3>
                <p className="text-xs text-gray-500">Datasets</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 bg-gray-900/70 rounded-lg border border-gray-800">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20 font-medium">
                    Source
                  </span>
                  <span className="text-sm font-medium text-white">{exp.sourceDataset}</span>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{exp.sourceDescription}</p>
              </div>
              <div className="p-3 bg-gray-900/70 rounded-lg border border-gray-800">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/20 font-medium">
                    Target
                  </span>
                  <span className="text-sm font-medium text-white">{exp.targetDataset}</span>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{exp.targetDescription}</p>
              </div>
            </div>
          </Card>

          {/* Baselines */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4 text-amber-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Baselines</h3>
                <p className="text-xs text-gray-500">{exp.baselines.length} 个基线方法</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="pb-2 text-xs text-gray-500 font-medium w-1/3">方法名称</th>
                    <th className="pb-2 text-xs text-gray-500 font-medium">描述</th>
                    <th className="pb-2 text-xs text-gray-500 font-medium w-24">类别</th>
                  </tr>
                </thead>
                <tbody>
                  {exp.baselines.map((bl) => (
                    <tr key={bl.name} className="border-b border-gray-800/50 last:border-0">
                      <td className="py-2.5 pr-3 text-gray-200 font-medium font-mono text-xs">{bl.name}</td>
                      <td className="py-2.5 pr-3 text-gray-400 text-xs">{bl.description}</td>
                      <td className="py-2.5">
                        <span className={cn('text-[11px] px-1.5 py-0.5 rounded border', categoryColor[bl.category])}>
                          {categoryLabel[bl.category]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Metrics */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-4 h-4 text-green-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Metrics</h3>
                <p className="text-xs text-gray-500">{exp.metrics.length} 项评估指标</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="pb-2 text-xs text-gray-500 font-medium w-1/4">指标名称</th>
                    <th className="pb-2 text-xs text-gray-500 font-medium">描述</th>
                    <th className="pb-2 text-xs text-gray-500 font-medium w-40">目标值</th>
                  </tr>
                </thead>
                <tbody>
                  {exp.metrics.map((m) => (
                    <tr key={m.name} className="border-b border-gray-800/50 last:border-0">
                      <td className="py-2.5 pr-3 text-gray-200 font-medium font-mono text-xs">{m.name}</td>
                      <td className="py-2.5 pr-3 text-gray-400 text-xs">{m.description}</td>
                      <td className="py-2.5">
                        <span className="text-xs font-mono text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
                          {m.target}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Experimental Steps */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <ListChecks className="w-4 h-4 text-blue-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Experimental Steps</h3>
                <p className="text-xs text-gray-500">{exp.steps.length} 个步骤</p>
              </div>
            </div>
            <div className="space-y-0">
              {exp.steps.map((s, idx) => (
                <div key={s.step} className="flex gap-3">
                  <div className="flex flex-col items-center shrink-0 w-8">
                    <div className="w-8 h-8 rounded-full bg-primary-500/20 border border-primary-500/30 flex items-center justify-center">
                      <span className="text-xs font-bold text-primary-400">{s.step}</span>
                    </div>
                    {idx < exp.steps.length - 1 && (
                      <div className="w-0.5 flex-1 min-h-[12px] bg-gray-700 rounded-full my-1" />
                    )}
                  </div>
                  <div className={cn(idx < exp.steps.length - 1 && 'pb-4')}>
                    <h4 className="text-sm font-semibold text-white mb-1">{s.title}</h4>
                    <p className="text-xs text-gray-400 leading-relaxed mb-2">{s.description}</p>
                    <div className="flex items-start gap-1.5">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                      <span className="text-xs text-green-400/80">{s.expected}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Expected Results */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4 text-green-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Expected Results</h3>
                <p className="text-xs text-gray-500">初步分析预期</p>
              </div>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{exp.expectedResults}</p>
          </Card>

          {/* Limitations */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Limitations</h3>
                <p className="text-xs text-gray-500">{exp.limitations.length} 项潜在限制</p>
              </div>
            </div>
            <div className="space-y-2">
              {exp.limitations.map((lim, idx) => (
                <div key={idx} className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/10">
                  <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                  <span className="text-xs text-amber-300/80 leading-relaxed">{lim}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* 右侧：可验证性检查 */}
        <div className="lg:col-span-1">
          <div className="sticky top-6 space-y-4">
            <VerifiabilityChecklist exp={exp} />

            <Card>
              <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-blue-400" />
                实验概览
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-400">基线方法</span>
                  <span className="text-white font-mono">{exp.baselines.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">评估指标</span>
                  <span className="text-white font-mono">{exp.metrics.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">实验步骤</span>
                  <span className="text-white font-mono">{exp.steps.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">潜在限制</span>
                  <span className="text-white font-mono">{exp.limitations.length}</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}