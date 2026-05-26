import { useState, useCallback } from 'react';
import { Terminal } from 'lucide-react';
import { Card } from './Card';
import { RunLogTable } from './RunLogTable';
import { RunLogDetail } from './RunLogDetail';
import { MOCK_RUN_LOGS } from '@/data/mockData';
import type { RunLog } from '@/data/mockData';

interface RunLogsPageProps {
  projectId?: string;
  compact?: boolean;
}

export function RunLogsPage({ projectId: _projectId, compact: _compact = false }: RunLogsPageProps) {
  const [selectedLog, setSelectedLog] = useState<RunLog>(MOCK_RUN_LOGS[0]);

  const handleSelect = useCallback((log: RunLog) => {
    setSelectedLog(log);
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-1">运行日志</h1>
        <p className="text-gray-400 text-sm">记录每次智能体运行的输入、输出、模型参数和执行状态</p>
      </div>

      {/* 表格区域 */}
      <RunLogTable
        logs={MOCK_RUN_LOGS}
        selectedId={selectedLog.id}
        onSelect={handleSelect}
      />

      {/* 详情面板 */}
      <div className="mt-6">
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="w-4 h-4 text-primary-400" />
            <div>
              <h3 className="text-sm font-semibold text-white">运行详情</h3>
              <p className="text-xs text-gray-500">输入摘要 · 输出快照 · 模型参数 · 错误信息</p>
            </div>
          </div>
          <RunLogDetail
            log={selectedLog}
            onClose={() => {}}
          />
        </Card>
      </div>
    </div>
  );
}