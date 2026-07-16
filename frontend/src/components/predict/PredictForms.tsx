import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import type { PredictTaskType } from '@/services/predictService';

export type PredictTab = 'generate' | 'score' | 'impact';

interface PredictFormsProps {
  busy: boolean;
  maxReportChars: number;
  onMaxReportCharsChange: (v: number) => void;
  onGenerate: (payload: {
    taskType: PredictTaskType;
    files: FileList;
    apiKey: string;
  }) => void;
  onScore: (payload: {
    taskFile: File;
    reportFile: File;
    sourceFiles: FileList | null;
    apiKey: string;
    maxReportChars: number;
  }) => void;
  onImpact: (payload: {
    pdf: File;
    apiKey: string;
    maxReportChars: number;
    taskLit?: File | null;
    scoresLit?: File | null;
    taskData?: File | null;
    scoresData?: File | null;
    taskClaim?: File | null;
    scoresClaim?: File | null;
  }) => void;
}

const fieldCls =
  'w-full px-3 py-2.5 rounded-lg border border-[#ddd] bg-white text-[0.9rem] text-[#1a1a1a] mb-1 focus:outline-none focus:border-[#333] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-[#f0f0f0] file:text-[#333] file:text-sm file:font-medium';

function FileHint({ files }: { files: FileList | null }) {
  if (!files || files.length === 0) return null;
  return (
    <p className="text-[0.74rem] text-[#888] mt-1 mb-3">
      已选 {files.length} 个：{Array.from(files).map((f) => f.name).join('、')}
    </p>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="text-[0.74rem] text-[#888] -mt-0.5 mb-4">{children}</p>;
}

function Label({ htmlFor, children }: { htmlFor?: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="block text-[0.8rem] font-medium text-[#444] mb-1.5">
      {children}
    </label>
  );
}

function SubmitBtn({
  busy,
  children,
}: {
  busy: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={busy}
      className={cn(
        'w-full py-3 rounded-lg text-[0.9rem] font-medium text-white transition-colors',
        busy ? 'bg-[#1a1a1a]/50 cursor-not-allowed' : 'bg-[#1a1a1a] hover:bg-[#333]',
      )}
    >
      {busy ? '任务进行中…' : children}
    </button>
  );
}

function ApiKeyField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <details className="mb-4">
      <summary className="cursor-pointer text-[0.8rem] text-[#666] hover:text-[#333]">
        API Key（可选）
      </summary>
      <input
        id={id}
        type="password"
        autoComplete="off"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="DASHSCOPE_API_KEY（填写后优先使用）"
        className={cn(fieldCls, 'mt-2')}
      />
    </details>
  );
}

export function PredictForms({
  busy,
  maxReportChars,
  onMaxReportCharsChange,
  onGenerate,
  onScore,
  onImpact,
}: PredictFormsProps) {
  const [tab, setTab] = useState<PredictTab>('impact');

  const [taskType, setTaskType] = useState<PredictTaskType>('literature_review');
  const [genFiles, setGenFiles] = useState<FileList | null>(null);
  const [apiKeyGen, setApiKeyGen] = useState('');

  const [taskFile, setTaskFile] = useState<File | null>(null);
  const [reportFile, setReportFile] = useState<File | null>(null);
  const [sourceFiles, setSourceFiles] = useState<FileList | null>(null);
  const [apiKeyScore, setApiKeyScore] = useState('');

  const [impactPdf, setImpactPdf] = useState<File | null>(null);
  const [apiKeyImpact, setApiKeyImpact] = useState('');
  const [taskLit, setTaskLit] = useState<File | null>(null);
  const [scoresLit, setScoresLit] = useState<File | null>(null);
  const [taskData, setTaskData] = useState<File | null>(null);
  const [scoresData, setScoresData] = useState<File | null>(null);
  const [taskClaim, setTaskClaim] = useState<File | null>(null);
  const [scoresClaim, setScoresClaim] = useState<File | null>(null);

  const tabs: { id: PredictTab; label: string }[] = [
    { id: 'generate', label: '生成评分表' },
    { id: 'score', label: '报告打分' },
    { id: 'impact', label: '科学影响力预测' },
  ];

  return (
    <div className="max-w-[640px] mx-auto text-[#1a1a1a]">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div className="min-w-0 flex-1">
          <h2 className="text-[1.3rem] font-semibold text-[#1a1a1a] mb-1">评分表工具</h2>
          <p className="text-[0.85rem] text-[#666]">
            生成领域评分表，或对已有报告自动打分，或预测论文科学影响力
          </p>
        </div>
        <div className="text-right shrink-0 min-w-[180px]">
          <Label htmlFor="max_report_chars">报告截断上限（字符）</Label>
          <input
            id="max_report_chars"
            type="number"
            min={1000}
            step={10000}
            value={maxReportChars}
            onChange={(e) => onMaxReportCharsChange(Number(e.target.value) || 200000)}
            className={cn(fieldCls, 'w-[160px] text-right mb-0')}
            title="三个 Tab 共用"
          />
          <p className="text-[0.74rem] text-[#888] mt-1">默认 200000，可调</p>
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            disabled={busy}
            onClick={() => setTab(t.id)}
            className={cn(
              'flex-1 py-2.5 rounded-lg border text-[0.85rem] font-medium text-center transition-colors',
              tab === t.id
                ? 'bg-[#1a1a1a] text-white border-[#1a1a1a]'
                : 'bg-[#fafafa] text-[#333] border-[#ddd] hover:border-[#bbb]',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'generate' && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!genFiles || genFiles.length === 0) return;
            onGenerate({ taskType, files: genFiles, apiKey: apiKeyGen });
          }}
        >
          <Label htmlFor="task_type">报告类型</Label>
          <select
            id="task_type"
            className={fieldCls}
            value={taskType}
            onChange={(e) => setTaskType(e.target.value as PredictTaskType)}
          >
            <option value="claim_verification">主张核查 — 论文 PDF</option>
            <option value="data_analysis">数据分析 — PDF / CSV / MD</option>
            <option value="literature_review">科学调研 — 综述 PDF / MD</option>
          </select>

          <Label htmlFor="gen_files">上传文献 / 数据文件</Label>
          <input
            id="gen_files"
            type="file"
            multiple
            accept=".pdf,.csv,.md,.txt"
            required
            className={fieldCls}
            onChange={(e) => setGenFiles(e.target.files)}
          />
          <FileHint files={genFiles} />
          <Hint>研究问题将根据上传文献自动生成</Hint>
          <ApiKeyField id="api_key_gen" value={apiKeyGen} onChange={setApiKeyGen} />
          <SubmitBtn busy={busy}>生成评分表</SubmitBtn>
        </form>
      )}

      {tab === 'score' && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!taskFile || !reportFile) return;
            onScore({
              taskFile,
              reportFile,
              sourceFiles,
              apiKey: apiKeyScore,
              maxReportChars,
            });
          }}
        >
          <Label htmlFor="task_file">评分表 task.json</Label>
          <input
            id="task_file"
            type="file"
            accept=".json,application/json"
            required
            className={fieldCls}
            onChange={(e) => setTaskFile(e.target.files?.[0] ?? null)}
          />
          <Hint>须含 task_type 字段；系统自动选择对应生成器</Hint>

          <Label htmlFor="report_file">待评报告</Label>
          <input
            id="report_file"
            type="file"
            accept=".md,.txt,.pdf"
            required
            className={fieldCls}
            onChange={(e) => setReportFile(e.target.files?.[0] ?? null)}
          />
          <Hint>支持 Markdown / TXT / PDF</Hint>

          <Label htmlFor="source_files">源文献（可选，辅助 source 引用评分）</Label>
          <input
            id="source_files"
            type="file"
            multiple
            accept=".pdf,.csv,.md,.txt"
            className={fieldCls}
            onChange={(e) => setSourceFiles(e.target.files)}
          />
          <FileHint files={sourceFiles} />
          <ApiKeyField id="api_key_score" value={apiKeyScore} onChange={setApiKeyScore} />
          <SubmitBtn busy={busy}>开始打分</SubmitBtn>
        </form>
      )}

      {tab === 'impact' && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!impactPdf) return;
            onImpact({
              pdf: impactPdf,
              apiKey: apiKeyImpact,
              maxReportChars,
              taskLit,
              scoresLit,
              taskData,
              scoresData,
              taskClaim,
              scoresClaim,
            });
          }}
        >
          <Label htmlFor="impact_pdf">上传论文 PDF（必需）</Label>
          <input
            id="impact_pdf"
            type="file"
            accept=".pdf"
            required
            className={fieldCls}
            onChange={(e) => setImpactPdf(e.target.files?.[0] ?? null)}
          />
          {impactPdf && <Hint>已选：{impactPdf.name}</Hint>}

          <div className="my-4 p-3.5 rounded-lg bg-[#f8f9fa] border border-[#e5e5e5]">
            <div className="font-semibold text-[0.88rem] text-[#1a1a1a] mb-2">评分表（可选）</div>
            <p className="text-[0.76rem] text-[#666] mb-3">
              未上传的评分表将自动生成。若已打分，请同时上传 task.json 和 rubric_scores.json。
            </p>
            {(
              [
                ['科学调研报告', setTaskLit, setScoresLit],
                ['数据分析报告', setTaskData, setScoresData],
                ['主张核查报告', setTaskClaim, setScoresClaim],
              ] as const
            ).map(([label, setTask, setScores]) => (
              <div key={label} className="mb-3 last:mb-0 space-y-1">
                <Label>{label} — task.json</Label>
                <input
                  type="file"
                  accept=".json"
                  className={fieldCls}
                  onChange={(e) => setTask(e.target.files?.[0] ?? null)}
                />
                <Label>{label} — rubric_scores.json</Label>
                <input
                  type="file"
                  accept=".json"
                  className={fieldCls}
                  onChange={(e) => setScores(e.target.files?.[0] ?? null)}
                />
              </div>
            ))}
          </div>

          <ApiKeyField id="api_key_impact" value={apiKeyImpact} onChange={setApiKeyImpact} />
          <SubmitBtn busy={busy}>开始预测</SubmitBtn>
          <p className="text-[0.74rem] text-[#888] mt-3 leading-relaxed">
            完整流水线可能需要较长时间（含三类评分表生成与影响力评估）。请保持页面打开直至完成。
          </p>
        </form>
      )}
    </div>
  );
}
