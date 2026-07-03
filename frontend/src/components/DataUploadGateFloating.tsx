import { Upload, X, ArrowRight } from 'lucide-react';
import { Button } from '@/components/Button';

interface DataUploadGateFloatingProps {
  pendingCount: number;
  uploadedCount: number;
  onGoToDatasets: () => void;
  onDismiss?: () => void;
}

export function DataUploadGateFloating({
  pendingCount,
  uploadedCount,
  onGoToDatasets,
  onDismiss,
}: DataUploadGateFloatingProps) {
  return (
    <div className="fixed bottom-6 right-6 z-[100] max-w-md animate-in fade-in slide-in-from-bottom-4">
      <div className="rounded-bp border border-bp-yellow/40 bg-bp-panel shadow-2xl shadow-black/40 overflow-hidden">
        <div className="flex items-start gap-3 p-4 bg-bp-yellow/10">
          <div className="p-2 rounded-full bg-bp-yellow/20 shrink-0">
            <Upload className="w-5 h-5 text-bp-yellow" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-bp-text mb-1">需要上传数据集</h3>
            <p className="text-xs text-bp-muted leading-relaxed">
              多源数据挖掘已完成，发现 <strong className="text-bp-yellow">{pendingCount}</strong> 个需手动下载的数据集。
              请前往数据集页面上传至少 1 个文件后继续生成报告。
              {uploadedCount > 0 && (
                <span className="text-bp-green"> 已上传 {uploadedCount} 个。</span>
              )}
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              <Button
                size="sm"
                icon={<ArrowRight className="w-3.5 h-3.5" />}
                onClick={onGoToDatasets}
              >
                前往数据集页面
              </Button>
              {onDismiss && (
                <Button size="sm" variant="ghost" onClick={onDismiss}>
                  稍后处理
                </Button>
              )}
            </div>
          </div>
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="text-bp-muted hover:text-bp-text p-1 shrink-0"
              aria-label="关闭"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
