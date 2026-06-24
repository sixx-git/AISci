import { useState, useEffect, useCallback } from 'react';
import { FolderOpen, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
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
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const res = await datasetService.getDataCatalog(projectId, refresh);
      if (res.code === 200 && res.data) {
        setCatalog(res.data);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load(false);
  }, [load]);

  return (
    <Card className="p-4 border-indigo-500/20 bg-indigo-500/5">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-indigo-300 flex items-center gap-1.5">
          <FolderOpen className="w-4 h-4" />
          数据目录 · {catalog?.asset_count ?? 0} 项资产
        </h4>
        <Button
          variant="secondary"
          size="sm"
          icon={loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          onClick={() => load(true)}
          disabled={loading}
        >
          刷新
        </Button>
      </div>

      {catalog?.generated_at && (
        <p className="text-[10px] text-bp-muted mb-3">生成于 {catalog.generated_at.slice(0, 19)}</p>
      )}

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {(catalog?.assets || []).map((asset) => (
          <div
            key={asset.asset_id}
            className="p-3 rounded border border-bp-border bg-bp-base/40 text-xs"
          >
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="font-medium text-bp-text">{asset.asset_id}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-bp-panel text-indigo-300">
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
              <p className="text-[10px] text-cyan-500/80 mt-0.5">
                来源: {String(asset.provenance.source)}
              </p>
            )}
          </div>
        ))}
      </div>

      {!loading && (catalog?.assets || []).length === 0 && (
        <p className="text-xs text-bp-muted text-center py-6">暂无数据资产，请上传数据集或运行 Data Finder</p>
      )}
    </Card>
  );
}
