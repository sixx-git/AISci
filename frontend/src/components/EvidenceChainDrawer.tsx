import { X, FileText, BookOpen, Hash, Link2, Gauge } from 'lucide-react';
import type { EvidenceItem as EvidenceItemType } from '@/types';

interface EvidenceChainDrawerProps {
  open: boolean;
  onClose: () => void;
  hypothesisTitle: string;
  hypothesisContent?: string;
  evidenceCount: number;
  evidenceList: EvidenceItemType[];
}

export function EvidenceChainDrawer({
  open,
  onClose,
  hypothesisTitle,
  hypothesisContent,
  evidenceCount,
  evidenceList,
}: EvidenceChainDrawerProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* 遮罩 */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 抽屉面板 */}
      <div className="relative ml-auto w-full max-w-2xl h-full bg-gray-900 border-l border-gray-800 shadow-2xl overflow-y-auto animate-slide-in">
        {/* 关闭按钮 */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-6">
          {/* 头部：假设标题 */}
          <div className="mb-6 pt-2">
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
              <Link2 className="w-3.5 h-3.5" />
              证据链 · 可追踪展示
            </div>
            <h2 className="text-xl font-bold text-white mb-2">{hypothesisTitle}</h2>
            {hypothesisContent && (
              <p className="text-sm text-gray-400 leading-relaxed">{hypothesisContent}</p>
            )}
            <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                证据项 {evidenceCount}
              </span>
              {evidenceList.length > 0 && (
                <span className="flex items-center gap-1">
                  <Gauge className="w-3.5 h-3.5 text-blue-400" />
                  最高相关度 {Math.round(Math.max(...evidenceList.map(e => e.relevance_score)) * 100)}%
                </span>
              )}
            </div>
          </div>

          {/* 证据列表 */}
          <div className="space-y-4">
            {evidenceList.length === 0 ? (
              <div className="text-center py-16 text-gray-500">
                <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <p className="text-sm text-gray-400 mb-2">当前假设尚无可追踪证据</p>
                <p className="text-xs text-gray-500">请补充文献或数据集以建立证据链</p>
              </div>
            ) : (
              evidenceList.map((ev, idx) => (
                <div
                  key={ev.id || idx}
                  className="p-4 rounded-lg border border-gray-800 bg-gray-850 hover:border-gray-700 transition-colors"
                >
                  {/* 序号和相关度 */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono text-gray-600">#{idx + 1}</span>
                    <div className="flex items-center gap-1.5">
                      <Gauge className="w-3.5 h-3.5 text-blue-400" />
                      <span className="text-xs font-mono text-blue-400">
                        {Math.round(ev.relevance_score * 100)}%
                      </span>
                    </div>
                  </div>

                  {/* 事实陈述 */}
                  <div className="mb-3">
                    <p className="text-sm text-gray-200 leading-relaxed">{ev.fact_text}</p>
                  </div>

                  {/* 原文引用 */}
                  {ev.quote_text && (
                    <div className="mb-3 p-3 rounded bg-gray-800/50 border border-gray-700/50">
                      <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                        <BookOpen className="w-3 h-3" />
                        原文引用
                      </div>
                      <p className="text-xs text-gray-400 italic leading-relaxed">
                        "{ev.quote_text}"
                      </p>
                    </div>
                  )}

                  {/* 来源信息 */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    {ev.source_title && (
                      <span className="flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        {ev.source_title}
                      </span>
                    )}
                    {ev.page_number != null && (
                      <span className="flex items-center gap-1">
                        <Hash className="w-3 h-3" />
                        第 {ev.page_number} 页
                      </span>
                    )}
                    {ev.document_id && (
                      <span className="font-mono text-gray-600">
                        doc:{ev.document_id.slice(0, 12)}...
                      </span>
                    )}
                    {ev.chunk_id && (
                      <span className="font-mono text-gray-600">
                        chunk:{ev.chunk_id.slice(0, 8)}...
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}