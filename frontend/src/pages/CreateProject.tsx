import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Plus, Cpu, Network, Radio } from 'lucide-react';
import { projectService } from '@/services';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { BackToProjectsLink } from '@/components/workspace/BackToProjectsLink';
import { cn } from '@/lib/utils';
import type { ProjectMode } from '@/types';

type SixGTopicId = 'emergency_comm' | 'edge_computing' | 'isac' | 'custom';
type SixGExecution = 'quick' | 'full';

const SIXG_TOPICS: Array<{ id: SixGTopicId; label: string; detail: string }> = [
  { id: 'emergency_comm', label: '空天地融合应急通信', detail: '沿用已实现的容量与续航预检，并可进入完整科研分析。' },
  { id: 'edge_computing', label: '边缘智能与算网协同', detail: '复用文献、假设和报告。算力与时延检查待专业验证。' },
  { id: 'isac', label: '通感一体化研究', detail: '复用文献、假设和报告。不生成虚假波形或感知仿真。' },
  { id: 'custom', label: '用户自定义6G任务', detail: '自由输入问题，由 Qwen 解析后交你核对。推测数字不是实测。' },
];

export function CreateProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [projectMode, setProjectMode] = useState<ProjectMode>('general');
  const [sixgTopic, setSixgTopic] = useState<SixGTopicId>('emergency_comm');
  const [sixgExecution, setSixgExecution] = useState<SixGExecution>('quick');
  const [formData, setFormData] = useState({
    name: '',
    research_question: '',
    description: '',
  });

  const selectSixG = (topic: SixGTopicId = sixgTopic) => {
    setProjectMode('emergency_6g');
    setSixgTopic(topic);
    if (topic === 'emergency_comm') {
      setFormData((prev) => ({
        ...prev,
        name: prev.name || '近海岛屿台风应急通信保障',
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    if (projectMode === 'emergency_6g' && sixgTopic === 'custom' && !formData.research_question.trim()) {
      alert('自定义 6G 任务需要填写研究问题');
      return;
    }

    setLoading(true);
    try {
      const researchQuestion = formData.research_question.trim();
      const description = formData.description.trim();
      const payload: Record<string, unknown> = {
        name: formData.name,
        research_question: researchQuestion || description || undefined,
        description: description || undefined,
        project_mode: projectMode,
      };
      if (projectMode === 'federated_learning') {
        payload.fl_setting = 'hfl';
        payload.fl_experiment_profile = 'standard_non_iid';
        payload.fl_sim_backend = 'local_pack';
      }
      if (projectMode === 'emergency_6g') {
        payload.sixg_topic = sixgTopic;
        payload.sixg_execution = sixgExecution;
      }
      const response = await projectService.createProject(payload);
      if (response.code === 200) {
        const tab = projectMode === 'emergency_6g' ? '?tab=emergency' : '';
        navigate(`/projects/${response.data.id}${tab}`);
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
        subtitle="通用科研与联邦学习资源包保持可用；6G 专题可做快速预检或完整科研分析"
      />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <p className="text-sm font-medium text-bp-text mb-2">项目模式</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ModeButton
                active={projectMode === 'general'}
                icon={<Cpu className="w-4 h-4 text-bp-cyan" />}
                title="通用 AISci"
                detail="文献 → 假设 → 迭代实验 → 报告"
                onClick={() => setProjectMode('general')}
              />
              <ModeButton
                active={projectMode === 'federated_learning'}
                icon={<Network className="w-4 h-4 text-bp-cyan" />}
                title="联邦学习（资源包）"
                detail="挂载 FL Starter Pack，默认横向联邦与标准 Non-IID"
                onClick={() => setProjectMode('federated_learning')}
              />
              <ModeButton
                active={projectMode === 'emergency_6g'}
                icon={<Radio className="w-4 h-4 text-bp-cyan" />}
                title="6G专业应用"
                detail="预定义专题或自定义任务，复用原有科研流程"
                onClick={() => selectSixG()}
              />
            </div>
          </div>

          {projectMode === 'emergency_6g' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SIXG_TOPICS.map((topic) => (
                  <button
                    key={topic.id}
                    type="button"
                    onClick={() => selectSixG(topic.id)}
                    className={cn(
                      'text-left p-3 rounded-bp border',
                      sixgTopic === topic.id
                        ? 'border-bp-cyan/40 bg-bp-cyan-tint'
                        : 'border-bp-border bg-bp-surface',
                    )}
                  >
                    <span className="text-sm font-medium text-bp-text">{topic.label}</span>
                    <p className="text-xs text-bp-muted mt-1 leading-relaxed">{topic.detail}</p>
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-4 text-sm text-bp-text">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    checked={sixgExecution === 'quick'}
                    onChange={() => setSixgExecution('quick')}
                  />
                  快速方案预检
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    checked={sixgExecution === 'full'}
                    onChange={() => setSixgExecution('full')}
                  />
                  完整科研分析
                </label>
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
              placeholder="项目名称"
              className="input-field"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-bp-text mb-2">
              {projectMode === 'emergency_6g' ? '研究问题或任务描述' : '研究问题'}
            </label>
            <textarea
              value={formData.research_question}
              onChange={(e) => setFormData({ ...formData, research_question: e.target.value })}
              placeholder={
                sixgTopic === 'custom' && projectMode === 'emergency_6g'
                  ? '自定义 6G 任务必填。写出场景、目标和约束；未给出的设备参数不要指望系统补造。'
                  : '可留空。预定义专题会填入对应研究问题，你之后仍可修改。'
              }
              rows={3}
              className="input-field min-h-[80px]"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-bp-text mb-2">
              项目描述 <span className="text-bp-muted font-normal">（可选）</span>
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="可选：补充背景或约束"
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

function ModeButton({
  active,
  icon,
  title,
  detail,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  title: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'text-left p-4 rounded-bp border transition-colors',
        active ? 'border-bp-cyan/40 bg-bp-cyan-tint' : 'border-bp-border bg-bp-surface hover:border-bp-cyan/20',
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-sm font-semibold text-bp-text">{title}</span>
      </div>
      <p className="text-xs text-bp-muted leading-relaxed">{detail}</p>
    </button>
  );
}
