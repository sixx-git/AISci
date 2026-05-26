import { useState, useCallback } from 'react';
import { FileText, Clock } from 'lucide-react';
import { Card } from './Card';
import { MarkdownPreview } from './MarkdownPreview';
import { ReportChecklist } from './ReportChecklist';
import { ExportActions } from './ExportActions';
import type { ExportType } from './ExportActions';
import type { ReportData } from '@/data/mockData';
import { MOCK_REPORT } from '@/data/mockData';

interface ReportPageProps {
  projectId: string;
  compact?: boolean;
}

export function ReportPage({ projectId: _projectId, compact: _compact = false }: ReportPageProps) {
  const [report] = useState<ReportData>(MOCK_REPORT);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 2500);
  }, []);

  const handleExport = useCallback((action: ExportType) => {
    const messages: Record<ExportType, string> = {
      generate: '正在调用 LLM 生成研究报告…（模拟）',
      markdown: 'Markdown 文件导出中…（模拟）',
      pdf: 'PDF 报告导出中…（模拟）',
      copy: '报告内容已复制到剪贴板（模拟）',
    };
    showAlert(messages[action]);
  }, [showAlert]);

  return (
    <div className="max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-1">研究报告</h1>
        <p className="text-gray-400 text-sm">自动生成符合比赛规范的科学假设与研究计划</p>
      </div>

      {/* 顶部信息栏 + 操作按钮 */}
      <div className="mb-6">
        <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-white">{report.title}</p>
              <div className="flex items-center gap-1 mt-0.5 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                <span>生成于 {report.generatedAt}</span>
              </div>
            </div>
          </div>
          <ExportActions onAction={handleExport} className="w-full sm:w-auto" />
        </Card>
      </div>

      {/* 主体：左侧预览 + 右侧检查 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧：Markdown 预览 */}
        <div className="lg:col-span-3">
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-4 h-4 text-primary-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">报告预览</h3>
                <p className="text-xs text-gray-500">Markdown 格式 · 科学假设与研究计划</p>
              </div>
            </div>
            <div className="bg-gray-950/80 rounded-lg border border-gray-800 p-6 overflow-auto max-h-[calc(100vh-320px)]">
              <MarkdownPreview content={report.markdownContent} />
            </div>
          </Card>
        </div>

        {/* 右侧：完整性检查 + 统计 */}
        <div className="lg:col-span-1">
          <div className="sticky top-6 space-y-4">
            <ReportChecklist sections={report.sections} />
          </div>
        </div>
      </div>

      {/* Toast */}
      {alertMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-sm text-white shadow-lg animate-fade-in z-50">
          {alertMsg}
        </div>
      )}
    </div>
  );
}