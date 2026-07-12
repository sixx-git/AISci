import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ExternalLink, Upload, Loader2, CheckCircle2, AlertCircle, Clock,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type ExternalCandidateItem } from '@/services/dataFinderService';

interface RequiredDatasetUploadPanelProps {
  projectId: string;
  onCandidatesChange?: (candidates: ExternalCandidateItem[]) => void;
}

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending_download: { text: '待下载', cls: 'text-bp-yellow' },
  pending_auto: { text: '待自动导入', cls: 'text-bp-cyan' },
  processing: { text: '处理中', cls: 'text-bp-cyan' },
  merged: { text: '已上传', cls: 'text-bp-green' },
  auto_imported: { text: '已自动导入', cls: 'text-bp-green' },
  failed: { text: '失败', cls: 'text-danger-400' },
};

function needsManualUpload(c: ExternalCandidateItem): boolean {
  const av = String(c.availability || '');
  return av === 'catalog_only' || av === 'metadata_only' || c.import_supported === false;
}

export function RequiredDatasetUploadPanel({
  projectId,
  onCandidatesChange,
}: RequiredDatasetUploadPanelProps) {
  const [candidates, setCandidates] = useState<ExternalCandidateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dataFinderService.getResults(projectId);
      if (res.code === 200 && res.data) {
        const list = (res.data.external_candidates || []) as ExternalCandidateItem[];
        const manual = list.filter(
          (c) => needsManualUpload(c)
            || c.user_upload_status === 'merged'
            || c.user_upload_status === 'failed'
            || c.user_upload_status === 'processing',
        );
        setCandidates(manual);
        setUploadedCount(manual.filter((c) => c.user_upload_status === 'merged').length);
        onCandidatesChange?.(manual);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [projectId, onCandidatesChange]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const handleUpload = async (candidateId: string, file: File) => {
    setBusyId(candidateId);
    setError(null);
    try {
      const res = await dataFinderService.uploadExternalCandidate(projectId, candidateId, file);
      if (res.code === 200) {
        await loadCandidates();
      } else {
        setError(res.message || '上传失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败');
      await loadCandidates();
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <Card className="p-6 flex items-center gap-2 text-sm text-bp-muted">
        <Loader2 className="w-4 h-4 animate-spin" /> 加载所需数据集列表…
      </Card>
    );
  }

  if (!candidates.length) {
    return (
      <Card className="p-6 text-sm text-bp-muted">
        当前研究领域未匹配到需手动下载的外部数据集。
      </Card>
    );
  }

  const pendingCount = candidates.filter((c) => c.user_upload_status === 'pending_download').length;

  return (
    <Card
      title="所需数据集"
      subtitle={`共 ${candidates.length} 项 · 已上传 ${uploadedCount} 项 · 待下载 ${pendingCount} 项`}
      className="border-bp-yellow/20"
    >
      <p className="text-sm text-bp-muted mb-4">
        系统根据<strong className="text-bp-text">研究领域</strong>推荐以下开放数据源。请下载后上传 CSV/TSV/JSON/FITS 等文件，化学/结构类研究可上传 SDF/MOL/SMILES，天文光谱立方可上传 .fits，或将多文件目录打包为 ZIP。
      </p>

      {error && (
        <p className="text-sm text-danger-300 mb-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-bp border border-bp-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-bp-panel/80 text-left text-xs text-bp-muted">
              <th className="px-3 py-2.5 font-medium min-w-[12rem]">数据集名称</th>
              <th className="px-3 py-2.5 font-medium whitespace-nowrap w-[1%]">来源</th>
              <th className="px-3 py-2.5 font-medium whitespace-nowrap w-[1%]">下载地址</th>
              <th className="px-3 py-2.5 font-medium whitespace-nowrap w-[1%]">状态</th>
              <th className="px-3 py-2.5 font-medium whitespace-nowrap w-[140px]">上传</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const cid = String(c.candidate_id || '');
              const statusKey = String(c.user_upload_status || 'pending_download');
              const status = STATUS_LABEL[statusKey] || STATUS_LABEL.pending_download;
              const url = String(c.url || '');
              const isBusy = busyId === cid;

              return (
                <tr key={cid || String(c.dataset_name)} className="border-t border-bp-border/60">
                  <td className="px-3 py-3 align-top min-w-0">
                    <div className="font-medium text-bp-text">{String(c.dataset_name || '未命名')}</div>
                    {c.description && (
                      <p className="text-xs text-bp-muted mt-1 line-clamp-2">{String(c.description)}</p>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top text-bp-muted whitespace-nowrap w-[1%]">
                    {String(c.source_platform || '—')}
                  </td>
                  <td className="px-3 py-3 align-top whitespace-nowrap w-[1%]">
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-bp-cyan hover:underline text-xs whitespace-nowrap"
                      >
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                        打开下载页
                      </a>
                    ) : (
                      <span className="text-bp-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top whitespace-nowrap w-[1%]">
                    <span className={`inline-flex items-center gap-1 text-xs whitespace-nowrap ${status.cls}`}>
                      {statusKey === 'processing' && <Loader2 className="w-3 h-3 animate-spin shrink-0" />}
                      {statusKey === 'merged' && <CheckCircle2 className="w-3 h-3 shrink-0" />}
                      {statusKey === 'pending_download' && <Clock className="w-3 h-3 shrink-0" />}
                      {statusKey === 'failed' && <AlertCircle className="w-3 h-3 shrink-0" />}
                      {status.text}
                    </span>
                    {c.user_upload_filename && (
                      <p className="text-xs text-bp-muted mt-1 max-w-[10rem] truncate" title={String(c.user_upload_filename)}>
                        {String(c.user_upload_filename)}
                      </p>
                    )}
                    {c.user_upload_error && statusKey === 'failed' && (
                      <p className="text-xs text-danger-400/90 mt-1 max-w-[12rem]" title={String(c.user_upload_error)}>
                        {String(c.user_upload_error)}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top whitespace-nowrap w-[140px]">
                    <input
                      ref={(el) => { fileRefs.current[cid] = el; }}
                      type="file"
                      accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.jsonl,.zip,.fits,.fit,.fts,.fits.gz,.sdf,.mol,.smi,.smiles,.sdf.gz,.mol.gz"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f && cid) handleUpload(cid, f);
                        e.target.value = '';
                      }}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                      disabled={!cid || isBusy || statusKey === 'processing'}
                      onClick={() => fileRefs.current[cid]?.click()}
                    >
                      {statusKey === 'merged' ? '重新上传' : '文件 / ZIP'}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
