import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Plus, Cpu } from 'lucide-react';
import { projectService } from '@/services';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { BackToProjectsLink } from '@/components/workspace/BackToProjectsLink';
import type { ProjectMode } from '@/types';

export function CreateProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const projectMode: ProjectMode = 'general';
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
        subtitle="输入基本信息，系统将基于通用 AISci 流程展开研究"
      />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="p-4 rounded-bp border border-bp-cyan/20 bg-bp-cyan-tint">
            <div className="flex items-center gap-2 mb-2">
              <Cpu className="w-4 h-4 text-bp-cyan" />
              <span className="text-sm font-semibold text-bp-text">通用 AISci 模式</span>
            </div>
            <p className="text-xs text-bp-muted leading-relaxed">
              文献挖掘 → 假设生成 → 迭代实验 → 报告，适用于通用科研场景
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-bp-text mb-2">
              项目名称 <span className="text-danger-400">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="例如：基于深度学习的药物发现研究"
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
