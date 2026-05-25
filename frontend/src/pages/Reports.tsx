import { ClipboardList } from 'lucide-react';
import { Card } from '@/components/Card';

export function Reports() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">报告中心</h1>
        <p className="text-gray-400">查看和管理 AI Scientist 生成的研究报告</p>
      </div>

      <Card className="text-center py-16">
        <ClipboardList className="w-16 h-16 text-gray-600 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-300 mb-2">报告中心</h3>
        <p className="text-gray-500">报告管理功能即将上线</p>
      </Card>
    </div>
  );
}