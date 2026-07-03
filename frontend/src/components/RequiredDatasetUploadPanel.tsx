import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Database, ExternalLink, Upload, Loader2, CheckCircle2, AlertCircle, Clock, ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type ExternalCandidateItem } from '@/services/dataFinderService';
import { quickReportService } from '@/services/quickReportService';

interface RequiredDatasetUploadPanelProps {
  projectId: string;
  runId?: string | null;
  /** 上传成功后自动续跑 Pipeline */
  autoResumeOnUpload?: boolean;
  onResumed?: () => void;
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
  runId,
  autoResumeOnUpload = false,
  onResumed,
  onCandidatesChange,
}: RequiredDatasetUploadPanelProps) {
  const [candidates, setCandidates] = useState<ExternalCandidateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);
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

  const handleResume = useCallback(async () => {
    if (!runId) {
      setError('缺少运行 ID，无法继续 Pipeline');
      return;
    }
    setResuming(true);
    setError(null);
    try {
      const res = await quickReportService.resume(runId, false);
      if (res.code === 200) {
        onResumed?.();
      } else {
        setError(res.message || '继续失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '继续失败');
    } finally {
      setResuming(false);
    }
  }, [runId, onResumed]);

  const handleUpload = async (candidateId: string, file: File) => {
    setBusyId(candidateId);
    setError(null);
    try {
      const res = await dataFinderService.uploadExternalCandidate(projectId, candidateId, file);
      if (res.code === 200) {
        await loadCandidates();
        if (autoResumeOnUpload && runId) {
          const st = await quickReportService.getStatus(runId);
          if (st.code === 200 && st.data?.can_resume) {
            await handleResume();
          }
        }
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
        暂无需要手动下载的外部数据集。若 Pipeline 仍在等待，请稍后刷新。
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
        系统在多源数据挖掘阶段检索到以下数据集。请打开下载链接获取 CSV / 表格文件，在本页上传至少
        <strong className="text-bp-text"> 1 个</strong> 数据集后，即可继续假设生成与报告流程。
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
              <th className="px-3 py-2.5 font-medium">数据集名称</th>
              <th className="px-3 py-2.5 font-medium">来源</th>
              <th className="px-3 py-2.5 font-medium">下载地址</th>
              <th className="px-3 py-2.5 font-medium">状态</th>
              <th className="px-3 py-2.5 font-medium w-[140px]">上传</th>
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
                  <td className="px-3 py-3 align-top">
                    <div className="font-medium text-bp-text">{String(c.dataset_name || '未命名')}</div>
                    {c.description && (
                      <p className="text-xs text-bp-muted mt-1 line-clamp-2">{String(c.description)}</p>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top text-bp-muted whitespace-nowrap">
                    {String(c.source_platform || '—')}
                  </td>
                  <td className="px-3 py-3 align-top">
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-bp-cyan hover:underline text-xs break-all"
                      >
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                        打开下载页
                      </a>
                    ) : (
                      <span className="text-bp-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <span className={`inline-flex items-center gap-1 text-xs ${status.cls}`}>
                      {statusKey === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                      {statusKey === 'merged' && <CheckCircle2 className="w-3 h-3" />}
                      {statusKey === 'pending_download' && <Clock className="w-3 h-3" />}
                      {statusKey === 'failed' && <AlertCircle className="w-3 h-3" />}
                      {status.text}
                    </span>
                    {c.user_upload_filename && (
                      <p className="text-xs text-bp-muted mt-1">{String(c.user_upload_filename)}</p>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <input
                      ref={(el) => { fileRefs.current[cid] = el; }}
                      type="file"
                      accept=".csv,.tsv,.txt,.xlsx,.xls"
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
                      {statusKey === 'merged' ? '重新上传' : '选择文件'}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {runId && (
        <div className="flex flex-wrap items-center gap-3 mt-5 pt-4 border-t border-bp-border">
          <Button
            icon={resuming ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
            disabled={resuming || uploadedCount < 1}
            onClick={() => handleResume()}
          >
            {resuming ? '继续中…' : '继续生成报告'}
          </Button>
          <span className="text-xs text-bp-muted flex items-center gap-1">
            <Database className="w-3.5 h-3.5" />
            {uploadedCount < 1
              ? '请至少上传 1 个数据集后继续'
              : autoResumeOnUpload
                ? '上传成功后将自动继续后续流程'
                : '已满足最低上传要求，可手动继续'}
          </span>
        </div>
      )}
    </Card>
  );
}
