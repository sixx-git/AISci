import { useRef, useState } from 'react';
import {
  Database, ExternalLink, Upload, Loader2, CheckCircle2, AlertCircle, Clock,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type ExternalCandidateItem } from '@/services/dataFinderService';

interface ExternalCandidateTodoPanelProps {
  projectId: string;
  candidates?: ExternalCandidateItem[];
  onUpdated?: () => void;
}

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending_download: { text: '待下载', cls: 'text-bp-yellow border-bp-yellow/30 bg-bp-yellow/10' },
  pending_auto: { text: '待自动导入', cls: 'text-bp-cyan border-bp-cyan/30 bg-bp-cyan/10' },
  processing: { text: '处理中', cls: 'text-bp-cyan border-bp-cyan/30 bg-bp-cyan/10' },
  merged: { text: '已纳入合并', cls: 'text-bp-green border-bp-green/30 bg-bp-green/10' },
  auto_imported: { text: '已自动导入', cls: 'text-bp-green border-bp-green/30 bg-bp-green/10' },
  failed: { text: '处理失败', cls: 'text-danger-400 border-danger-500/30 bg-danger-500/10' },
};

function needsManualUpload(c: ExternalCandidateItem): boolean {
  const av = String(c.availability || '');
  return av === 'catalog_only' || av === 'metadata_only' || c.import_supported === false;
}

export function ExternalCandidateTodoPanel({
  projectId,
  candidates = [],
  onUpdated,
}: ExternalCandidateTodoPanelProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const manualList = candidates.filter(
    (c) => needsManualUpload(c) || c.user_upload_status === 'merged' || c.user_upload_status === 'failed',
  );

  if (!manualList.length) return null;

  const handleUpload = async (candidateId: string, file: File) => {
    setBusyId(candidateId);
    setError(null);
    try {
      const res = await dataFinderService.uploadExternalCandidate(projectId, candidateId, file);
      if (res.code === 200) {
        onUpdated?.();
      } else {
        setError(res.message || '上传失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败');
      onUpdated?.();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card className="p-4 border-bp-yellow/20 bg-bp-yellow/5">
      <h4 className="text-sm font-semibold text-bp-yellow mb-1 flex items-center gap-1.5">
        <Database className="w-4 h-4" />
        外部数据待办 · 下载后上传 ({manualList.length})
      </h4>
      <p className="text-xs text-bp-muted mb-3">
        根据研究问题推荐的数据源仅提供下载链接。请下载后上传表格文件、化学结构文件（SDF/MOL/SMILES，含 ChEMBL 的 .sdf.gz），或将整个数据集目录打包为 ZIP；系统会自动解析并纳入合并。
      </p>

      {error && (
        <p className="text-xs text-danger-400 mb-2 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5" /> {error}
        </p>
      )}

      <div className="space-y-3">
        {manualList.map((c) => {
          const cid = String(c.candidate_id || '');
          const statusKey = String(c.user_upload_status || 'pending_download');
          const status = STATUS_LABEL[statusKey] || STATUS_LABEL.pending_download;
          const url = String(c.url || '');
          const isBusy = busyId === cid;

          return (
            <div
              key={cid || String(c.dataset_name)}
              className="p-3 rounded-lg border border-bp-border bg-bp-base/40 text-xs"
            >
              <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-bp-text truncate">
                    {String(c.dataset_name || '未命名数据集')}
                  </div>
                  <div className="text-bp-muted truncate">{String(c.source_platform || '')}</div>
                </div>
                <span className={`shrink-0 text-xs px-2 py-0.5 rounded border flex items-center gap-1 ${status.cls}`}>
                  {statusKey === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                  {statusKey === 'merged' && <CheckCircle2 className="w-3 h-3" />}
                  {statusKey === 'failed' && <AlertCircle className="w-3 h-3" />}
                  {statusKey === 'pending_download' && <Clock className="w-3 h-3" />}
                  {status.text}
                </span>
              </div>

              {c.description && (
                <p className="text-xs text-bp-muted line-clamp-2 mb-2">{String(c.description)}</p>
              )}

              <div className="flex flex-wrap items-center gap-2">
                {url && (
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-cyan"
                  >
                    <ExternalLink className="w-3 h-3" /> 打开数据源
                  </a>
                )}
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
                  {statusKey === 'merged' ? '重新上传' : '上传文件 / ZIP'}
                </Button>
              </div>

              {c.user_upload_filename && (
                <p className="text-xs text-bp-muted mt-2">
                  文件: {String(c.user_upload_filename)}
                  {c.linked_table_id && (
                    <span className="text-bp-green/80 ml-2">→ {String(c.linked_table_id)}</span>
                  )}
                </p>
              )}
              {c.user_upload_error && statusKey === 'failed' && (
                <p className="text-xs text-danger-400/90 mt-1">{String(c.user_upload_error)}</p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
