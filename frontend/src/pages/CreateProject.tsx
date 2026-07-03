import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Plus, Cpu, Network } from 'lucide-react';
import { projectService } from '@/services';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { BackToProjectsLink } from '@/components/workspace/BackToProjectsLink';
import { cn } from '@/lib/utils';
import type { ProjectMode } from '@/types';

const MODE_OPTIONS: { value: ProjectMode; label: string; desc: string; icon: typeof Cpu }[] = [
  {
    value: 'general',
    label: '通用 AISci 模式',
    desc: '文献挖掘 → 假设生成 → 实验设计 → 小样验证 → 报告，适用于通用科研场景',
    icon: Cpu,
  },
  {
    value: 'federated_learning',
    label: '联邦学习科研模式',
    desc: '针对 Non-IID、异构模型、VFL、通信成本与隐私预算的联邦学习研究流程',
    icon: Network,
  },
];

const FL_TEMPLATE = {
  research_domain: '联邦学习 / 分布式机器学习',
  research_question:
    '在非独立同分布（Non-IID）数据和异构客户端模型结构条件下，如何通过知识蒸馏或个性化联邦机制提升联邦学习系统的模型精度、收敛速度和通信效率？',
  research_goal:
    '在 Non-IID 与异构客户端条件下，设计并验证知识蒸馏、个性化联邦或 VFL 机制，提升全局/本地精度、收敛速度与通信效率。',
  research_background:
    '联邦学习在 Non-IID 客户端、异构模型与通信约束下常出现 client drift、收敛慢与通信开销高。',
  data_source: '历史联邦实验 CSV、公开 FL benchmark、组内标注报告',
  constraints: 'Non-IID 划分、通信带宽、privacy_budget、客户端参与率',
  expected_output: '联邦 baseline 对比报告、通信-精度权衡分析、隐私机制建议',
};

export function CreateProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [projectMode, setProjectMode] = useState<ProjectMode>('general');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        name: formData.name,
        description: formData.description,
        project_mode: projectMode,
      };
      if (projectMode === 'federated_learning') {
        Object.assign(payload, {
          research_domain: FL_TEMPLATE.research_domain,
          research_question: FL_TEMPLATE.research_question,
          research_goal: FL_TEMPLATE.research_goal,
          research_background: FL_TEMPLATE.research_background,
          data_source: FL_TEMPLATE.data_source,
          constraints: FL_TEMPLATE.constraints,
          expected_output: FL_TEMPLATE.expected_output,
          keywords: 'FedAvg, FedProx, SCAFFOLD, FedMD, FedDF, SplitNN, VFL, Non-IID',
        });
      }
      const response = await projectService.createProject(payload);
      if (response.code === 200) {
        navigate(`/projects/${response.data.id}`);
      }
    } catch (error) {
      console.error('创建项目失败:', error);
      alert('创建项目失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <BackToProjectsLink className="mb-6" />

      <PageHeader
        title="创建新项目"
        subtitle="选择项目模式并输入基本信息，系统将切换对应的研究模板与 Pipeline 逻辑"
      />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-bp-text mb-3">
              项目模式 <span className="text-danger-400">*</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {MODE_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const selected = projectMode === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setProjectMode(opt.value)}
                    className={cn(
                      'text-left p-4 rounded-bp border transition-all',
                      selected
                        ? 'border-bp-cyan bg-bp-cyan-tint ring-1 ring-bp-cyan/30'
                        : 'border-bp-border bg-bp-panel/50 hover:bg-bp-surface hover-accent-left',
                    )}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={cn('w-4 h-4', selected ? 'text-bp-cyan' : 'text-bp-muted')} />
                      <span className={cn('text-sm font-semibold', selected ? 'text-bp-text' : 'text-bp-muted')}>
                        {opt.label}
                      </span>
                    </div>
                    <p className="text-xs text-bp-muted leading-relaxed">{opt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-bp-text mb-2">
              项目名称 <span className="text-danger-400">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder={
                projectMode === 'federated_learning'
                  ? '例如：Non-IID 下联邦蒸馏通信效率优化'
                  : '例如：基于深度学习的药物发现研究'
              }
              className="input-field"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-bp-text mb-2">
              项目描述
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="简单描述这个项目的研究目标和内容..."
              rows={5}
              className="input-field resize-none"
            />
          </div>

          {projectMode === 'federated_learning' && (
            <div className="p-3 rounded-bp border border-bp-cyan/20 bg-bp-cyan-tint text-xs text-bp-cyan">
              创建后将预填联邦学习研究问题模板（FedAvg/FedProx/SCAFFOLD、Non-IID、client drift 等关键词）。
              请上传含 method、global_accuracy、f1_score 等列的 CSV 以启用联邦数据识别。
            </div>
          )}

          <div className="flex items-center justify-end gap-4 pt-4 border-t border-bp-cyan-dim">
            <Link to="/">
              <Button variant="secondary" type="button">
                取消
              </Button>
            </Link>
            <Button
              type="submit"
              isLoading={loading}
              icon={<Plus className="w-4 h-4" />}
              disabled={!formData.name.trim()}
            >
              创建项目
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
