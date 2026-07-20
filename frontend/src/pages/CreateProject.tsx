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

export function CreateProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [projectMode, setProjectMode] = useState<ProjectMode>('general');
  const [flSetting, setFlSetting] = useState<'hfl' | 'vfl'>('hfl');
  const [flDomains, setFlDomains] = useState<string[]>([]);
  const [flExperimentProfile, setFlExperimentProfile] = useState<
    'standard_non_iid' | 'quick_iid'
  >('standard_non_iid');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });

  const FL_APP_DOMAINS = [
    { id: 'finance_risk', label: '金融风控' },
    { id: 'smart_care', label: '医疗健康 / 智慧康养' },
    { id: 'edge_mobile', label: '智能终端与边缘' },
    { id: 'iot_industrial', label: '物联网 / 工业互联网' },
    { id: 'smart_transport', label: '智慧交通' },
  ] as const;

  const FL_CROSS_DOMAINS = [
    { id: 'privacy_crypto', label: '差分隐私 / 安全多方计算' },
    { id: 'fl_cv', label: '计算机视觉' },
    { id: 'fl_nlp', label: '自然语言处理' },
    { id: 'fl_multilingual', label: '多语言 / 跨语言' },
    { id: 'llm_ft', label: '大模型联邦微调' },
    { id: 'fl_lora_hetero', label: '客户端 LoRA 异构' },
    { id: 'fl_blockchain', label: '区块链' },
    { id: 'fl_rl', label: '联邦强化学习' },
    { id: 'fl_continual', label: '持续 / 增量学习' },
  ] as const;

  const toggleFlDomain = (id: string) => {
    setFlDomains((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    );
  };

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
        payload.fl_setting = flSetting;
        payload.fl_experiment_profile = flExperimentProfile;
        // 空数组表示不过滤（挂载全部领域）
        if (flDomains.length > 0) {
          payload.fl_domains = flDomains;
        }
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
        subtitle="选择研究模式后，系统将按对应资源与提示词展开流程（阶段不变）"
      />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <p className="text-sm font-medium text-bp-text mb-2">项目模式</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setProjectMode('general')}
                className={cn(
                  'text-left p-4 rounded-bp border transition-colors',
                  projectMode === 'general'
                    ? 'border-bp-cyan/40 bg-bp-cyan-tint'
                    : 'border-bp-border bg-bp-surface hover:border-bp-cyan/20',
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Cpu className="w-4 h-4 text-bp-cyan" />
                  <span className="text-sm font-semibold text-bp-text">通用 AISci</span>
                </div>
                <p className="text-xs text-bp-muted leading-relaxed">
                  文献 → 假设 → 迭代实验 → 报告
                </p>
              </button>
              <button
                type="button"
                onClick={() => setProjectMode('federated_learning')}
                className={cn(
                  'text-left p-4 rounded-bp border transition-colors',
                  projectMode === 'federated_learning'
                    ? 'border-bp-cyan/40 bg-bp-cyan-tint'
                    : 'border-bp-border bg-bp-surface hover:border-bp-cyan/20',
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Network className="w-4 h-4 text-bp-cyan" />
                  <span className="text-sm font-semibold text-bp-text">联邦学习（资源包）</span>
                </div>
                <p className="text-xs text-bp-muted leading-relaxed">
                  挂载预解析文献 / 数据集元数据 / 本地 pilot 脚本；非多机部署
                </p>
              </button>
            </div>
          </div>

          {projectMode === 'federated_learning' && (
            <div className="p-4 rounded-bp border border-bp-border bg-bp-surface/60 space-y-3">
              <p className="text-sm font-medium text-bp-text">联邦子场景</p>
              <div className="flex gap-3">
                <label className="flex items-center gap-2 text-sm text-bp-text cursor-pointer">
                  <input
                    type="radio"
                    name="fl_setting"
                    checked={flSetting === 'hfl'}
                    onChange={() => setFlSetting('hfl')}
                  />
                  横向联邦（HFL / FedAvg）
                </label>
                <label className="flex items-center gap-2 text-sm text-bp-text cursor-pointer">
                  <input
                    type="radio"
                    name="fl_setting"
                    checked={flSetting === 'vfl'}
                    onChange={() => setFlSetting('vfl')}
                  />
                  垂直联邦（VFL / 对齐）
                </label>
              </div>
              <p className="text-xs text-bp-muted">
                将自动写入 FL Starter Pack 种子文献，并开放 pack_d 提示词预设。
              </p>
              <div className="pt-2 space-y-2">
                <p className="text-sm font-medium text-bp-text">实验范式档位</p>
                <div className="flex flex-col gap-2">
                  <label className="flex items-start gap-2 text-sm text-bp-text cursor-pointer">
                    <input
                      type="radio"
                      name="fl_experiment_profile"
                      className="mt-1"
                      checked={flExperimentProfile === 'standard_non_iid'}
                      onChange={() => setFlExperimentProfile('standard_non_iid')}
                    />
                    <span>
                      <span className="font-medium">标准 Non-IID（推荐）</span>
                      <span className="block text-xs text-bp-muted">
                        Dirichlet α=0.1 + Local / Centralized / FedAvg / FedProx 对比
                      </span>
                    </span>
                  </label>
                  <label className="flex items-start gap-2 text-sm text-bp-text cursor-pointer">
                    <input
                      type="radio"
                      name="fl_experiment_profile"
                      className="mt-1"
                      checked={flExperimentProfile === 'quick_iid'}
                      onChange={() => setFlExperimentProfile('quick_iid')}
                    />
                    <span>
                      <span className="font-medium">快速验证</span>
                      <span className="block text-xs text-bp-muted">
                        IID + Local / Centralized / FedAvg
                      </span>
                    </span>
                  </label>
                </div>
              </div>
              <div className="pt-2 space-y-3">
                <div>
                  <p className="text-sm font-medium text-bp-text">领域种子（可选）</p>
                  <p className="text-xs text-bp-muted mt-1">
                    经典 HFL/VFL 方法种子始终保留。不勾选则挂载全部经典应用与交叉融合领域；勾选后仅保留所选领域。
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-bp-muted">经典应用</p>
                  <div className="flex flex-wrap gap-3">
                    {FL_APP_DOMAINS.map((d) => (
                      <label
                        key={d.id}
                        className="flex items-center gap-2 text-sm text-bp-text cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={flDomains.includes(d.id)}
                          onChange={() => toggleFlDomain(d.id)}
                        />
                        {d.label}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-bp-muted">交叉融合</p>
                  <div className="flex flex-wrap gap-3">
                    {FL_CROSS_DOMAINS.map((d) => (
                      <label
                        key={d.id}
                        className="flex items-center gap-2 text-sm text-bp-text cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={flDomains.includes(d.id)}
                          onChange={() => toggleFlDomain(d.id)}
                        />
                        {d.label}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

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
                  ? '例如：Non-IID 下 FedProx 收敛性研究'
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
              placeholder="可选：补充背景、数据约束或目标指标"
              className="input-field min-h-[100px]"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Link to="/" className="text-sm text-bp-muted hover:text-bp-text">
              取消
            </Link>
            <Button type="submit" disabled={loading || !formData.name.trim()}>
              <Plus className="w-4 h-4" />
              {loading ? '创建中…' : '创建项目'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
