import { useState, useEffect, useCallback } from 'react';
import { FolderOpen, RefreshCw } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import datasetService from '@/services/datasetService';

interface DataCatalogPanelProps {
  projectId: string;
}

interface CatalogAsset {
  asset_id?: string;
  type?: string;
  filename?: string;
  path?: string;
  provenance?: Record<string, unknown>;
  schema?: Record<string, unknown>;
  quality_report?: Record<string, unknown>;
  used_by_stages?: string[];
}

interface DataCatalog {
  project_id?: string;
  generated_at?: string;
  asset_count?: number;
  assets?: CatalogAsset[];
  summary?: Record<string, unknown>;
}

export function DataCatalogPanel({ projectId }: DataCatalogPanelProps) {
  const [catalog, setCatalog] = useState<DataCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const res = await datasetService.getDataCatalog(projectId, refresh);
      if (res.code === 200 && res.data) {
        setCatalog(res.data);
      } else {
        setError(res.message || '加载数据目录失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载数据目录失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load(false);
  }, [load]);

  const assets = catalog?.assets || [];

  return (
    <Card className="p-4 border-bp-cyan/20 bg-bp-cyan-tint">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-bp-cyan flex items-center gap-1.5">
          <FolderOpen className="w-4 h-4" />
          数据目录 · {catalog?.asset_count ?? 0} 项资产
        </h4>
        <Button
          variant="secondary"
          size="sm"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={() => load(true)}
          disabled={loading}
        >
          刷新
        </Button>
      </div>

      {catalog?.generated_at && !loading && (
        <p className="text-[10px] text-bp-muted mb-3">生成于 {catalog.generated_at.slice(0, 19)}</p>
      )}

      {loading && assets.length === 0 && (
        <LoadingState message="加载数据目录…" compact />
      )}

      {!loading && error && (
        <ErrorState message={error} onRetry={() => load(true)} compact />
      )}

      {!loading && !error && assets.length === 0 && (
        <EmptyState
          className="!py-8"
          icon={<FolderOpen className="w-8 h-8" />}
          title="暂无数据资产"
          description="请上传数据集或运行 Data Finder 后刷新目录"
          action={{ label: '刷新目录', onClick: () => load(true) }}
        />
      )}

      {!error && assets.length > 0 && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {assets.map((asset) => (
            <div
              key={asset.asset_id}
              className="p-3 rounded-bp border border-bp-border bg-bp-base/40 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-medium text-bp-text">{asset.asset_id}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-bp bg-bp-panel text-bp-cyan">
                  {asset.type}
                </span>
              </div>
              {asset.filename && (
                <p className="text-[10px] text-bp-muted truncate">{asset.filename}</p>
              )}
              {(asset.used_by_stages || []).length > 0 && (
                <p className="text-[10px] text-bp-muted mt-1">
                  用于: {(asset.used_by_stages || []).join(', ')}
                </p>
              )}
              {asset.provenance?.source != null && (
                <p className="text-[10px] text-bp-cyan/80 mt-0.5">
                  来源: {String(asset.provenance.source)}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
