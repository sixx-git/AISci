import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import type { PredictTaskType } from '@/services/predictService';

export type PredictTab = 'generate' | 'score' | 'impact';

/** 影响力预测：每类报告的预置材料模式 */
export type ImpactRubricMode = 'auto' | 'task_only' | 'scores_only' | 'both';

type ReportKind = 'lit' | 'data' | 'claim';

interface RubricSlotState {
  mode: ImpactRubricMode;
  task: File | null;
  scores: File | null;
  saveDir: string;
}

interface PredictFormsProps {
  busy: boolean;
  maxReportChars: number;
  onMaxReportCharsChange: (v: number) => void;
  onGenerate: (payload: {
    taskType: PredictTaskType;
    files: FileList;
    apiKey: string;
    saveDir: string;
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
    saveDirLit?: string;
    saveDirData?: string;
    saveDirClaim?: string;
  }) => void;
}

const REPORT_SLOTS: Array<{ kind: ReportKind; label: string }> = [
  { kind: 'lit', label: '科学调研报告' },
  { kind: 'data', label: '数据分析报告' },
  { kind: 'claim', label: '主张核查报告' },
];

const RUBRIC_MODES: Array<{ id: ImpactRubricMode; label: string; hint: string }> = [
  { id: 'auto', label: '自动生成', hint: '不上传，流水线内生成评分表并打分' },
  { id: 'task_only', label: '仅评分表', hint: '提交已生成的 task.json，系统对其打分' },
  { id: 'scores_only', label: '仅打分结果', hint: '提交已生成的 rubric_scores.json，直接用于影响力评估' },
  { id: 'both', label: '评分表 + 打分', hint: '同时提交 task.json 与 rubric_scores.json' },
];

function emptySlot(): RubricSlotState {
  return { mode: 'auto', task: null, scores: null, saveDir: '' };
}

function validateSlot(label: string, slot: RubricSlotState): string | null {
  if (slot.mode === 'task_only' && !slot.task) {
    return `请为「${label}」上传评分表 task.json`;
  }
  if (slot.mode === 'scores_only' && !slot.scores) {
    return `请为「${label}」上传打分结果 rubric_scores.json`;
  }
  if (slot.mode === 'both' && (!slot.task || !slot.scores)) {
    return `请为「${label}」同时上传 task.json 与 rubric_scores.json`;
  }
  return null;
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
  const [saveDir, setSaveDir] = useState('');

  const [taskFile, setTaskFile] = useState<File | null>(null);
  const [reportFile, setReportFile] = useState<File | null>(null);
  const [sourceFiles, setSourceFiles] = useState<FileList | null>(null);
  const [apiKeyScore, setApiKeyScore] = useState('');

  const [impactPdf, setImpactPdf] = useState<File | null>(null);
  const [apiKeyImpact, setApiKeyImpact] = useState('');
  const [rubricSlots, setRubricSlots] = useState<Record<ReportKind, RubricSlotState>>({
    lit: emptySlot(),
    data: emptySlot(),
    claim: emptySlot(),
  });
  const [impactFormError, setImpactFormError] = useState<string | null>(null);

  const updateSlot = (kind: ReportKind, patch: Partial<RubricSlotState>) => {
    setRubricSlots((prev) => ({
      ...prev,
      [kind]: { ...prev[kind], ...patch },
    }));
  };

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
            const normalized = saveDir.trim().replace(/^["']+|["']+$/g, '');
            if (normalized !== saveDir.trim()) setSaveDir(normalized);
            onGenerate({
              taskType,
              files: genFiles,
              apiKey: apiKeyGen,
              saveDir: normalized,
            });
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

          <Label htmlFor="save_dir">评分表保存路径（可选）</Label>
          <input
            id="save_dir"
            type="text"
            value={saveDir}
            onChange={(e) => setSaveDir(e.target.value)}
            placeholder={String.raw`例如: D:\rubrics 或 D:\rubrics\task.json`}
            className={fieldCls}
            autoComplete="off"
            spellCheck={false}
          />
          <Hint>
            粘贴本机绝对路径。填目录则保存为该目录下的 task.json；填 .json 文件则写入该文件。留空可稍后下载。
          </Hint>

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
            for (const slotMeta of REPORT_SLOTS) {
              const err = validateSlot(slotMeta.label, rubricSlots[slotMeta.kind]);
              if (err) {
                setImpactFormError(err);
                return;
              }
            }
            setImpactFormError(null);
            const normalizePath = (v: string) => v.trim().replace(/^["']+|["']+$/g, '');
            const pickTask = (kind: ReportKind) => {
              const s = rubricSlots[kind];
              return s.mode === 'task_only' || s.mode === 'both' ? s.task : null;
            };
            const pickScores = (kind: ReportKind) => {
              const s = rubricSlots[kind];
              return s.mode === 'scores_only' || s.mode === 'both' ? s.scores : null;
            };
            const pickSaveDir = (kind: ReportKind) => {
              const s = rubricSlots[kind];
              return s.mode === 'auto' ? normalizePath(s.saveDir) : '';
            };
            onImpact({
              pdf: impactPdf,
              apiKey: apiKeyImpact,
              maxReportChars,
              taskLit: pickTask('lit'),
              scoresLit: pickScores('lit'),
              taskData: pickTask('data'),
              scoresData: pickScores('data'),
              taskClaim: pickTask('claim'),
              scoresClaim: pickScores('claim'),
              saveDirLit: pickSaveDir('lit'),
              saveDirData: pickSaveDir('data'),
              saveDirClaim: pickSaveDir('claim'),
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
            <div className="font-semibold text-[0.88rem] text-[#1a1a1a] mb-1">
              预置评分材料（按报告类型可选）
            </div>
            <p className="text-[0.76rem] text-[#666] mb-4 leading-relaxed">
              每类报告可任选一种：自动生成、仅提交已有评分表、仅提交已有打分、或评分表与打分一并提交。
              未选择上传的类型将在流水线中自动生成并打分。
            </p>

            {REPORT_SLOTS.map(({ kind, label }) => {
              const slot = rubricSlots[kind];
              return (
                <div
                  key={kind}
                  className="mb-4 last:mb-0 pb-4 last:pb-0 border-b last:border-b-0 border-[#e8e8e8]"
                >
                  <div className="text-[0.84rem] font-medium text-[#1a1a1a] mb-2">{label}</div>
                  <div className="flex flex-col gap-1.5 mb-3">
                    {RUBRIC_MODES.map((m) => (
                      <label
                        key={m.id}
                        className={cn(
                          'flex items-start gap-2 text-[0.78rem] cursor-pointer rounded-md px-2 py-1.5',
                          slot.mode === m.id ? 'bg-white border border-[#ddd]' : 'border border-transparent hover:bg-white/70',
                        )}
                      >
                        <input
                          type="radio"
                          name={`impact_rubric_mode_${kind}`}
                          className="mt-0.5"
                          checked={slot.mode === m.id}
                          disabled={busy}
                          onChange={() =>
                            updateSlot(kind, {
                              mode: m.id,
                              // 切换模式时清空不相关文件，避免误传
                              task: m.id === 'scores_only' ? null : slot.task,
                              scores: m.id === 'task_only' ? null : slot.scores,
                            })
                          }
                        />
                        <span>
                          <span className="font-medium text-[#333]">{m.label}</span>
                          <span className="block text-[0.72rem] text-[#888] mt-0.5">{m.hint}</span>
                        </span>
                      </label>
                    ))}
                  </div>

                  {(slot.mode === 'task_only' || slot.mode === 'both') && (
                    <div className="mb-2">
                      <Label>评分表 task.json</Label>
                      <input
                        type="file"
                        accept=".json,application/json"
                        className={fieldCls}
                        disabled={busy}
                        onChange={(e) => updateSlot(kind, { task: e.target.files?.[0] ?? null })}
                      />
                      {slot.task && <Hint>已选：{slot.task.name}</Hint>}
                    </div>
                  )}

                  {(slot.mode === 'scores_only' || slot.mode === 'both') && (
                    <div>
                      <Label>打分结果 rubric_scores.json</Label>
                      <input
                        type="file"
                        accept=".json,application/json"
                        className={fieldCls}
                        disabled={busy}
                        onChange={(e) => updateSlot(kind, { scores: e.target.files?.[0] ?? null })}
                      />
                      {slot.scores && <Hint>已选：{slot.scores.name}</Hint>}
                    </div>
                  )}

                  {slot.mode === 'auto' && (
                    <div className="mt-1">
                      <Label htmlFor={`impact_save_dir_${kind}`}>评分表保存路径（可选）</Label>
                      <input
                        id={`impact_save_dir_${kind}`}
                        type="text"
                        value={slot.saveDir}
                        disabled={busy}
                        onChange={(e) => updateSlot(kind, { saveDir: e.target.value })}
                        placeholder={String.raw`例如: D:\rubrics 或 D:\rubrics\task_${kind}.json`}
                        className={fieldCls}
                        autoComplete="off"
                        spellCheck={false}
                      />
                      <Hint>
                        自动生成完成后写入本机路径；填目录时按类型保存为不同文件名，避免互相覆盖。
                      </Hint>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {impactFormError && (
            <p className="mb-3 text-[0.8rem] text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              {impactFormError}
            </p>
          )}

          <ApiKeyField id="api_key_impact" value={apiKeyImpact} onChange={setApiKeyImpact} />
          <SubmitBtn busy={busy}>开始预测</SubmitBtn>
          <p className="text-[0.74rem] text-[#888] mt-3 leading-relaxed">
            选择「自动生成」的类型耗时更长；已提交打分结果的类型会跳过生成与打分。请保持页面打开直至完成。
          </p>
        </form>
      )}
    </div>
  );
}
