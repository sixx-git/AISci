import React from 'react';
import { Settings2 } from 'lucide-react';
import { Card } from '../components/Card';

export function Settings() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">设置</h1>
        <p className="text-gray-400">配置 AI Scientist 选项</p>
      </div>

      <Card className="text-center py-16">
        <Settings2 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-300 mb-2">设置页面</h3>
        <p className="text-gray-500">配置选项即将上线</p>
      </Card>
    </div>
  );
}
