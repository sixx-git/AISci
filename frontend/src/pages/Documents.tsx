import { FolderOpen } from 'lucide-react';
import { Card } from '@/components/Card';

export function Documents() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">文档管理</h1>
        <p className="text-gray-400">管理所有科研文献和资料</p>
      </div>

      <Card className="text-center py-16">
        <FolderOpen className="w-16 h-16 text-gray-600 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-300 mb-2">文档管理</h3>
        <p className="text-gray-500">在项目工作台中管理项目文档</p>
      </Card>
    </div>
  );
}
