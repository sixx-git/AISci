import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Upload, Image, Mic, FileText, Loader2, AlertTriangle, Eye, ToggleLeft, ToggleRight, RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import multimodalService, { type MultimodalAsset } from '@/services/multimodalService';

interface MultimodalEvidencePanelProps {
  projectId: string;
  researchQuestion?: string;
}

const MODALITY_ICON: Record<string, typeof FileText> = {
  image: Image,
  audio: Mic,
  text: FileText,
};

export function MultimodalEvidencePanel({ projectId, researchQuestion = '' }: MultimodalEvidencePanelProps) {
  const [assets, setAssets] = useState<MultimodalAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await multimodalService.list(projectId);
      setAssets((res.data as MultimodalAsset[]) || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length || !projectId) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await multimodalService.upload(projectId, file, researchQuestion);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传解析失败');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleToggle = async (assetId: string) => {
    await multimodalService.toggleHypothesis(assetId);
    await load();
  };

  const handleReparse = async (assetId: string) => {
    await multimodalService.reparse(assetId, researchQuestion);
    await load();
  };

  const imagePreviewUrl = (asset: MultimodalAsset) => {
    if (asset.modality !== 'image') return null;
    const base = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    return `${base}/multimodal/${asset.id}/file`;
  };

  return (
    <Card title="多模态证据" subtitle="上传图表/录音/文本，解析为 Evidence Facts">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".png,.jpg,.jpeg,.webp,.gif,.tiff,.wav,.mp3,.m4a,.txt,.md,.json"
          multiple
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
        <Button
          size="sm"
          variant="primary"
          icon={uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
        >
          {uploading ? '解析中…' : '上传并解析'}
        </Button>
        <Button size="sm" variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={load}>
          刷新
        </Button>
      </div>

      {error && (
        <p className="text-xs text-red-400 mb-3 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {error}
        </p>
      )}

      {loading && assets.length === 0 && (
        <p className="text-sm text-bp-muted flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> 加载中…
        </p>
      )}

      {!loading && assets.length === 0 && (
        <p className="text-sm text-bp-muted">
          暂无多模态资产。可上传论文图表、实验截图或会议录音（音频需后续接入转写模型）。
        </p>
      )}

      <div className="space-y-3">
        {assets.map((asset) => {
          const Icon = MODALITY_ICON[asset.modality] || FileText;
          const facts = asset.evidence_facts || [];
          const warnings = (asset.metadata?.warnings as string[]) || [];
          const preview = imagePreviewUrl(asset);

          return (
            <div
              key={asset.id}
              className="p-3 rounded-lg border border-bp-border bg-bp-base/40"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Icon className="w-4 h-4 text-bp-cyan shrink-0" />
                  <span className="text-sm text-bp-text truncate">{asset.file_name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-bp-panel text-bp-muted">
                    {asset.modality}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    asset.parse_status === 'completed' ? 'bg-green-500/10 text-green-400'
                      : asset.parse_status === 'warning' ? 'bg-yellow-500/10 text-yellow-400'
                        : 'bg-bp-panel text-bp-muted'
                  }`}>
                    {asset.parse_status}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleToggle(asset.id)}
                  className="text-bp-muted hover:text-bp-cyan"
                  title={asset.use_for_hypothesis ? '用于假设生成' : '不参与假设生成'}
                >
                  {asset.use_for_hypothesis ? (
                    <ToggleRight className="w-5 h-5 text-green-400" />
                  ) : (
                    <ToggleLeft className="w-5 h-5" />
                  )}
                </button>
              </div>

              {asset.extracted_summary && (
                <p className="text-xs text-bp-muted mb-2 line-clamp-3">{asset.extracted_summary}</p>
              )}

              {preview && (
                <div className="mb-2 flex items-center gap-2">
                  <Eye className="w-3 h-3 text-bp-muted" />
                  <img
                    src={preview}
                    alt={asset.file_name}
                    className="max-h-32 rounded border border-bp-border object-contain"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                </div>
              )}

              {asset.modality === 'audio' && asset.extracted_text === '' && (
                <p className="text-[11px] text-yellow-400/90 mb-2">
                  转写未执行 — 当前未接入 Qwen-Audio/Whisper，不会编造 transcript。
                </p>
              )}

              {warnings.length > 0 && (
                <ul className="text-[10px] text-yellow-500/90 mb-2 list-disc list-inside">
                  {warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}

              {facts.length > 0 && (
                <div className="mt-2 pt-2 border-t border-bp-border/80">
                  <p className="text-[11px] text-bp-muted mb-1">Evidence Facts ({facts.length})</p>
                  <ul className="space-y-1">
                    {facts.slice(0, 4).map((f) => (
                      <li key={f.fact_id} className="text-[11px] text-bp-text">
                        <span className="font-mono text-bp-cyan/80">{f.fact_id}</span>
                        {' '}{f.fact_text?.slice(0, 120)}
                        {f.fact_text && f.fact_text.length > 120 ? '…' : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className="text-[10px] text-bp-muted hover:text-bp-text"
                  onClick={() => handleReparse(asset.id)}
                >
                  重新解析
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
