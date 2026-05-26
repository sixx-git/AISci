import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import { projectApi } from '@/lib/api';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';

export function CreateProject() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setLoading(true);
    try {
      const response = await projectApi.create(formData);
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
      {/* Back Button */}
      <Link to="/" className="inline-flex items-center text-[#94A3B8] hover:text-[#F8FAFC] mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4 mr-2" />
        返回项目列表
      </Link>

      <PageHeader
        title="创建新项目"
        subtitle="输入项目基本信息开始您的 AI 科研之旅"
      />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              项目名称 <span className="text-red-400">*</span>
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
            <label className="block text-sm font-medium text-gray-300 mb-2">
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

          <div className="flex items-center justify-end gap-4 pt-4 border-t border-dark-700">
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

      {/* Tips */}
      <Card className="mt-6">
        <h3 className="font-semibold text-white mb-3">💡 快速开始提示</h3>
        <ul className="space-y-2 text-gray-400 text-sm">
          <li>• 清晰的项目名称有助于后续管理</li>
          <li>• 详细描述可以帮助 AI 更好地理解研究方向</li>
          <li>• 创建后可以上传相关文献和数据</li>
        </ul>
      </Card>
    </div>
  );
}
