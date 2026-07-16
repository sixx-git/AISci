import { cn } from '@/lib/utils';
import type { PredictJobStatus } from '@/services/predictService';
import { predictService } from '@/services/predictService';

interface JobStatusPanelProps {
  status: PredictJobStatus | null;
  busy: boolean;
}

export function JobStatusPanel({ status, busy }: JobStatusPanelProps) {
  if (!status && !busy) return null;

  const progress = Math.min(100, Math.max(0, Number(status?.progress ?? (busy ? 2 : 0))));
  const state = status?.status || (busy ? 'running' : '');
  const failed = state === 'failed';
  const done = state === 'completed';
  const jobId = status?.job_id;
  const mode = status?.job_mode;

  return (
    <div
      className={cn(
        'mt-5 rounded-lg p-3.5 text-[0.85rem]',
        failed && 'bg-[#fef2f2] text-[#b91c1c]',
        done && 'bg-[#f0fdf4] text-[#166534]',
        !failed && !done && 'bg-[#f5f5f5] text-[#444]',
      )}
    >
      <div className="font-medium">
        {failed
          ? '任务失败'
          : done
            ? '任务完成'
            : status?.message || '任务进行中…'}
      </div>

      <div className="h-1.5 bg-[#e5e5e5] rounded-sm overflow-hidden mt-2.5 mb-2">
        <div
          className={cn(
            'h-full rounded-sm transition-all duration-400',
            failed ? 'bg-[#b91c1c]' : done ? 'bg-[#166534]' : 'bg-[#1a1a1a]',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="flex justify-between text-[0.74rem] text-[#666]">
        <span>{done ? '已完成' : failed ? '已中断' : '处理中'}</span>
        <span className="font-mono">{progress}%</span>
      </div>

      {failed && status?.error && (
        <p className="mt-2 text-[0.8rem] whitespace-pre-wrap">{String(status.error)}</p>
      )}

      {done && jobId && (
        <div className="mt-3 flex flex-wrap gap-2">
          {mode === 'generate' && (
            <a
              href={predictService.downloadUrl(jobId, 'task')}
              download="task.json"
              className="inline-block px-3.5 py-1.5 rounded-md bg-[#1a1a1a] text-white text-[0.78rem] font-semibold hover:bg-[#333]"
            >
              下载 task.json
            </a>
          )}
          {mode === 'score' && (
            <a
              href={predictService.downloadUrl(jobId, 'scores')}
              download="rubric_scores.json"
              className="inline-block px-3.5 py-1.5 rounded-md bg-[#1a1a1a] text-white text-[0.78rem] font-semibold hover:bg-[#333]"
            >
              下载 rubric_scores.json
            </a>
          )}
          {mode === 'impact' && (
            <a
              href={predictService.downloadUrl(jobId, 'impact')}
              download="impact_report.json"
              className="inline-block px-3.5 py-1.5 rounded-md bg-[#1a1a1a] text-white text-[0.78rem] font-semibold hover:bg-[#333]"
            >
              下载 impact_report.json
            </a>
          )}
        </div>
      )}

      {Array.isArray(status?.logs) && status.logs.length > 0 && (
        <div className="mt-2.5 max-h-[140px] overflow-y-auto bg-white border border-[#e5e5e5] rounded-md px-2.5 py-2 font-mono text-[0.68rem] leading-snug text-[#555]">
          {status.logs.slice(-40).map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
