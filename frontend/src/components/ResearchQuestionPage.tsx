import { useState, useMemo, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Save, Play, ArrowRight, CheckCircle, XCircle, AlertTriangle,
  Tag, Target, BookOpen, Database,
  FileOutput, Brain,
  HelpCircle, ClipboardCheck, Loader2,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { projectService } from '@/services/projectService';
import { researchQuestionKey } from '@/lib/storageKeys';

// ============ 表单数据类型 ============
export interface ResearchQuestionForm {
  researchDomain: string;
  researchQuestion: string;
  researchGoal: string;
  background: string;
  dataSource: string;
  constraints: string;
  expectedOutput: string;
  dataEntities: string;
  dataTargetVariables: string;
  dataMergeStrategy: string;
  dataPreferredSources: string;
  dataNeedNote: string;
  coverageGapThreshold: string;
  dataSpecGapThreshold: string;
  maxGapRounds: string;
  autoLiteratureDiscovery: string;
}

const EMPTY_FORM: ResearchQuestionForm = {
  researchDomain: '',
  researchQuestion: '',
  researchGoal: '',
  background: '',
  dataSource: '',
  constraints: '',
  expectedOutput: '',
  dataEntities: '',
  dataTargetVariables: '',
  dataMergeStrategy: 'auto',
  dataPreferredSources: '',
  dataNeedNote: '',
  coverageGapThreshold: '70',
  dataSpecGapThreshold: '60',
  maxGapRounds: '2',
  autoLiteratureDiscovery: 'true',
};

// ============ localStorage 工具函数 ============
function loadDraft(projectId: string | undefined): ResearchQuestionForm {
  if (!projectId) return { ...EMPTY_FORM };
  try {
    const saved = localStorage.getItem(researchQuestionKey(projectId));
    return saved ? { ...EMPTY_FORM, ...JSON.parse(saved) } : { ...EMPTY_FORM };
  } catch {
    return { ...EMPTY_FORM };
  }
}

function saveDraft(projectId: string, form: ResearchQuestionForm): void {
  try {
    localStorage.setItem(researchQuestionKey(projectId), JSON.stringify(form));
  } catch {
    // localStorage 写入失败时静默，不影响主流程
  }
}

// ============ 表单字段定义 ============
interface FormField {
  key: keyof ResearchQuestionForm;
  label: string;
  placeholder: string;
  icon: React.FC<{ className?: string }>;
  rows?: number;
}

const FORM_FIELDS: FormField[] = [
  {
    key: 'researchDomain',
    label: '研究领域',
    placeholder: '例如：计算机视觉、自然语言处理、生物信息学…',
    icon: Tag,
  },
  {
    key: 'researchQuestion',
    label: '研究问题',
    placeholder: '描述你希望 AI 科学家帮你探索的核心科学问题…',
    icon: HelpCircle,
    rows: 3,
  },
  {
    key: 'researchGoal',
    label: '研究目标',
    placeholder: '明确你希望达成的具体研究目标…',
    icon: Target,
    rows: 3,
  },
  {
    key: 'background',
    label: '已知背景',
    placeholder: '已有知识、相关理论、前人的研究成果…',
    icon: BookOpen,
    rows: 4,
  },
  {
    key: 'dataSource',
    label: '数据来源',
    placeholder: '可用的数据集、API、实验数据等…',
    icon: Database,
    rows: 2,
  },
  {
    key: 'constraints',
    label: '限制条件',
    placeholder: '算力限制、时间约束、数据隐私要求等…',
    icon: AlertTriangle,
    rows: 2,
  },
  {
    key: 'expectedOutput',
    label: '期望输出',
    placeholder: '你期望的研究产出：论文、报告、数据集、模型等…',
    icon: FileOutput,
    rows: 2,
  },
];

// ============ 预览项 ============
interface PreviewItem {
  label: string;
  key: keyof ResearchQuestionForm;
}

const PREVIEW_ITEMS: PreviewItem[] = [
  { label: '研究领域', key: 'researchDomain' },
  { label: '研究问题', key: 'researchQuestion' },
  { label: '研究目标', key: 'researchGoal' },
  { label: '已知背景', key: 'background' },
  { label: '数据来源', key: 'dataSource' },
  { label: '限制条件', key: 'constraints' },
  { label: '期望输出', key: 'expectedOutput' },
];

// ============ 前端字段 → 后端 snake_case 映射 ============
const FORM_TO_API_MAP: Partial<Record<keyof ResearchQuestionForm, string>> = {
  researchDomain: 'research_domain',
  researchQuestion: 'research_question',
  researchGoal: 'research_goal',
  background: 'research_background',
  dataSource: 'data_source',
  constraints: 'constraints',
  expectedOutput: 'expected_output',
};

function parseCommaList(text: string): string[] {
  return text
    .split(/[,;，；\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formToApiPayload(form: ResearchQuestionForm): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [formKey, apiKey] of Object.entries(FORM_TO_API_MAP)) {
    if (apiKey && form[formKey as keyof ResearchQuestionForm]) {
      payload[apiKey] = form[formKey as keyof ResearchQuestionForm];
    }
  }
  const hints: Record<string, unknown> = {};
  const entities = parseCommaList(form.dataEntities);
  const targets = parseCommaList(form.dataTargetVariables);
  const sources = parseCommaList(form.dataPreferredSources);
  if (entities.length) hints.entities_of_interest = entities;
  if (targets.length) hints.target_variables = targets;
  if (sources.length) hints.preferred_sources = sources;
  if (form.dataMergeStrategy && form.dataMergeStrategy !== 'auto') {
    hints.merge_strategy_hint = form.dataMergeStrategy;
  }
  if (form.dataNeedNote.trim()) hints.data_need_note = form.dataNeedNote.trim();
  if (Object.keys(hints).length > 0) {
    payload.data_spec_hints = hints;
  }
  const acq: Record<string, unknown> = {};
  const covThr = parseFloat(form.coverageGapThreshold);
  const specThr = parseFloat(form.dataSpecGapThreshold);
  const rounds = parseInt(form.maxGapRounds, 10);
  if (!Number.isNaN(covThr)) acq.coverage_gap_threshold = covThr;
  if (!Number.isNaN(specThr)) acq.data_spec_gap_threshold = specThr;
  if (!Number.isNaN(rounds)) acq.max_gap_rounds = Math.max(1, Math.min(4, rounds));
  acq.enable_gap_search = true;
  if (form.autoLiteratureDiscovery === 'false') {
    acq.auto_literature_discovery = false;
  } else if (form.autoLiteratureDiscovery === 'true') {
    acq.auto_literature_discovery = true;
  }
  if (Object.keys(acq).length > 0) {
    payload.data_acquisition = acq;
  }
  return payload;
}

// ============ 状态类型 ============
type SaveStatus =
  | { type: 'idle' }
  | { type: 'saving' }
  | { type: 'success' }
  | { type: 'error'; message: string }
  | { type: 'localSaved'; message: string };

// ============ 输入框组件 ============
interface InputFieldProps {
  field: FormField;
  value: string;
  onChange: (key: keyof ResearchQuestionForm, value: string) => void;
}

function InputField({ field, value, onChange }: InputFieldProps) {
  const Icon = field.icon;
  const charCount = value.length;

  return (
    <div>
      <label className="flex items-center gap-1.5 text-sm font-medium text-bp-text mb-1.5">
        <Icon className="w-4 h-4 text-bp-cyan" />
        {field.label}
      </label>
      {field.rows ? (
        <div className="relative">
          <textarea
            value={value}
            onChange={(e) => onChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            rows={field.rows}
            className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan focus:ring-1 focus:ring-bp-cyan/50 transition-all resize-none"
          />
          <span className="absolute bottom-2 right-3 text-[11px] text-bp-muted">
            {charCount}
          </span>
        </div>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={field.placeholder}
          className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan focus:ring-1 focus:ring-bp-cyan/50 transition-all"
        />
      )}
    </div>
  );
}

// ============ 主组件 ============
interface ResearchQuestionPageProps {
  projectId: string;
  projectMode?: string;
  onSaved?: () => void;
}

const FL_FORM_TEMPLATE: ResearchQuestionForm = {
  researchDomain: '联邦学习 / 分布式机器学习',
  researchQuestion:
    '在非独立同分布（Non-IID）数据和异构客户端模型结构条件下，如何通过知识蒸馏或个性化联邦机制提升联邦学习系统的模型精度、收敛速度和通信效率？',
  researchGoal:
    '在 Non-IID 与异构客户端条件下，设计并验证知识蒸馏、个性化联邦或 VFL 机制，提升全局/本地精度、收敛速度与通信效率。',
  background:
    '联邦学习在 Non-IID 客户端、异构模型与通信约束下常出现 client drift、收敛慢与通信开销高。',
  dataSource: '历史联邦实验 CSV、公开 FL benchmark、组内标注报告',
  constraints: 'Non-IID 划分、通信带宽、privacy_budget、客户端参与率',
  expectedOutput: '联邦 baseline 对比报告、通信-精度权衡分析、隐私机制建议',
  dataEntities: 'client_id, party_id, entity_id',
  dataTargetVariables: 'global_accuracy, f1_score, communication_cost_mb',
  dataMergeStrategy: 'join',
  dataPreferredSources: 'paper_table, huggingface, zenodo',
  dataNeedNote: '需要 Non-IID 划分下的 baseline 与通信轮次指标',
  coverageGapThreshold: '70',
  dataSpecGapThreshold: '60',
  maxGapRounds: '2',
  autoLiteratureDiscovery: 'true',
};

const VFL_FORM_TEMPLATE: ResearchQuestionForm = {
  researchDomain: '垂直联邦学习 / 隐私计算 / 多方协同建模',
  researchQuestion:
    '在垂直联邦学习场景中，如何在样本对齐和隐私保护约束下，利用多方异构特征提升大模型微调任务的预测性能与通信效率？',
  researchGoal:
    '设计 PSI/样本对齐、Secure Aggregation、差分隐私与 Split Learning 实验，对比 VFL baselines 并形成闭环迭代计划。',
  background:
    '特征分布在不同参与方，标签方与特征方分离；需在 entity_id 对齐与 privacy_budget 约束下纵向融合特征。',
  dataSource: '历史多方特征 CSV、人工标注报告、VFL 实验日志、aligned_id 对齐表',
  constraints: '样本 ID 对齐、特征方/标签方不可 Raw 共享、privacy_budget、通信轮次、对齐成功率',
  expectedOutput: 'VFL baseline 对比、通信-精度-隐私权衡、下一轮 replan 建议',
  dataEntities: 'entity_id, party_id, sample_id',
  dataTargetVariables: 'auc, accuracy, communication_cost_mb',
  dataMergeStrategy: 'join',
  dataPreferredSources: 'paper_table, supplementary, zenodo',
  dataNeedNote: '需多方特征对齐表与标签方指标',
  coverageGapThreshold: '70',
  dataSpecGapThreshold: '60',
  maxGapRounds: '2',
  autoLiteratureDiscovery: 'true',
};

export function ResearchQuestionPage({ projectId, projectMode, onSaved }: ResearchQuestionPageProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ResearchQuestionForm>(() => loadDraft(projectId));
  const [saveStatus, setSaveStatus] = useState<SaveStatus>({ type: 'idle' });

  useEffect(() => {
    if (!projectId) return;
    projectService.getProject(projectId).then((res) => {
      if (res.code !== 200 || !res.data) return;
      const p = res.data;
      const hints = p.config?.data_spec_hints || {};
      setForm((prev) => ({
        ...prev,
        researchDomain: String(p.research_domain || p.research_field || prev.researchDomain),
        researchQuestion: String(p.research_question || prev.researchQuestion),
        researchGoal: String(p.research_goal || prev.researchGoal),
        background: String(p.research_background || prev.background),
        dataSource: String(p.data_source || prev.dataSource),
        constraints: String(p.constraints || prev.constraints),
        expectedOutput: String(p.expected_output || prev.expectedOutput),
        dataEntities: Array.isArray(hints.entities_of_interest)
          ? (hints.entities_of_interest as string[]).join(', ')
          : prev.dataEntities,
        dataTargetVariables: Array.isArray(hints.target_variables)
          ? (hints.target_variables as string[]).join(', ')
          : prev.dataTargetVariables,
        dataPreferredSources: Array.isArray(hints.preferred_sources)
          ? (hints.preferred_sources as string[]).join(', ')
          : prev.dataPreferredSources,
        dataMergeStrategy: String(hints.merge_strategy_hint || prev.dataMergeStrategy || 'auto'),
        dataNeedNote: String(hints.data_need_note || prev.dataNeedNote),
        coverageGapThreshold: String(
          p.config?.data_acquisition?.coverage_gap_threshold ?? prev.coverageGapThreshold,
        ),
        dataSpecGapThreshold: String(
          p.config?.data_acquisition?.data_spec_gap_threshold ?? prev.dataSpecGapThreshold,
        ),
        maxGapRounds: String(
          p.config?.data_acquisition?.max_gap_rounds ?? prev.maxGapRounds,
        ),
        autoLiteratureDiscovery:
          p.config?.data_acquisition?.auto_literature_discovery === false
            ? 'false'
            : p.config?.data_acquisition?.auto_literature_discovery === true
              ? 'true'
              : prev.autoLiteratureDiscovery,
      }));
    }).catch(() => { /* ignore */ });
  }, [projectId]);

  const updateField = useCallback(
    (key: keyof ResearchQuestionForm, value: string) => {
      setForm((prev) => ({ ...prev, [key]: value }));
      // 输入变化时清除成功/错误提示，回到空闲状态
      setSaveStatus((prev) => (prev.type === 'idle' ? prev : { type: 'idle' }));
    },
    [],
  );

  // ========== 保存（localStorage + 后端） ==========
  const handleSave = useCallback(async () => {
    if (!projectId) return;

    // 第一步：始终保存到 localStorage
    saveDraft(projectId, form);
    setSaveStatus({ type: 'saving' });

    try {
      const payload = formToApiPayload(form);
      const res = await projectService.updateProject(projectId, payload);

      if (res.code === 200) {
        setSaveStatus({ type: 'success' });
        onSaved?.();
      } else {
        throw new Error(res.message || '后端返回异常');
      }
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : String(err);
      // localStorage 已保存，但后端失败
      setSaveStatus({
        type: 'localSaved',
        message: `已保存本地草稿，但同步后端失败: ${detail}`,
      });
    }

    // 3 秒后自动清除提示
    setTimeout(() => setSaveStatus({ type: 'idle' }), 4000);
  }, [projectId, form, onSaved]);

  // ========== 运行问题理解智能体 ==========
  const handleRunAgent = useCallback(async () => {
    if (!projectId) return;

    saveDraft(projectId, form);
    setSaveStatus({ type: 'saving' });

    try {
      const payload = formToApiPayload(form);
      await projectService.updateProject(projectId, payload);

      setSaveStatus({ type: 'success' });
      onSaved?.();
      navigate(`/projects/${projectId}?tab=workflow`);
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : String(err);
      setSaveStatus({
        type: 'localSaved',
        message: `已保存本地草稿，但同步后端失败: ${detail}`,
      });
      setTimeout(() => setSaveStatus({ type: 'idle' }), 5000);
    }
  }, [projectId, form, onSaved, navigate]);

  const filledCount = useMemo(
    () => Object.values(form).filter((v) => v.trim().length > 0).length,
    [form],
  );

  const totalFields = Object.keys(form).length;

  // ========== 保存状态提示条 ==========
  const renderStatusBar = () => {
    if (saveStatus.type === 'idle') return null;

    const iconClass = 'w-4 h-4 flex-shrink-0';

    const configs: Record<SaveStatus['type'], { icon: React.ReactNode; bg: string; text: string; textColor: string } | null> = {
      idle: null,
      saving: {
        icon: <Loader2 className={`${iconClass} animate-spin`} />,
        bg: 'bg-blue-500/10 border-blue-500/30',
        text: '保存中...',
        textColor: 'text-blue-300',
      },
      success: {
        icon: <CheckCircle className={iconClass} />,
        bg: 'bg-green-500/10 border-green-500/30',
        text: '研究问题已保存',
        textColor: 'text-green-300',
      },
      error: {
        icon: <XCircle className={iconClass} />,
        bg: 'bg-red-500/10 border-red-500/30',
        text: `保存失败: ${(saveStatus as { type: 'error'; message: string }).message}`,
        textColor: 'text-red-300',
      },
      localSaved: {
        icon: <AlertTriangle className={iconClass} />,
        bg: 'bg-yellow-500/10 border-yellow-500/30',
        text: (saveStatus as { type: 'localSaved'; message: string }).message,
        textColor: 'text-yellow-300',
      },
    };

    const config = configs[saveStatus.type];
    if (!config) return null;

    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${config.bg} mb-4 text-sm`}>
        <span className={config.textColor}>{config.icon}</span>
        <span className={config.textColor}>{config.text}</span>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* ========== 左侧：表单 ========== */}
      <div className="lg:col-span-2 space-y-5">
        <Card title="研究问题定义" subtitle="填写以下信息，AI 将基于这些内容展开研究">
          {projectMode === 'federated_learning' && (
            <div className="mb-4 p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
              <p className="text-xs text-cyan-300 mb-2">
                当前为<strong className="text-cyan-200">联邦学习科研模式</strong>，提供横向联邦与<strong className="text-violet-300">垂直联邦（VFL）</strong>模板。
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  onClick={() => setForm({ ...FL_FORM_TEMPLATE })}
                >
                  横向联邦模板
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  onClick={() => setForm({ ...VFL_FORM_TEMPLATE })}
                >
                  垂直联邦（VFL）模板
                </Button>
              </div>
            </div>
          )}
          {/* 状态提示 */}
          {renderStatusBar()}

          <div className="space-y-4">
            {FORM_FIELDS.map((field) => (
              <InputField
                key={field.key}
                field={field}
                value={form[field.key]}
                onChange={updateField}
              />
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-bp-border space-y-4">
            <h4 className="text-sm font-semibold text-indigo-200 flex items-center gap-1.5">
              <Database className="w-4 h-4" />
              结构化数据需求（DataSpec）
            </h4>
            <p className="text-xs text-bp-muted">
              可选：指定跨表对齐字段、目标变量与偏好数据源，将在多源数据采集阶段与自动推断的 DataSpec 合并。
            </p>
            <div>
              <label className="text-sm font-medium text-bp-text mb-1.5 block">实体 / 对齐字段（逗号分隔）</label>
              <input
                type="text"
                value={form.dataEntities}
                onChange={(e) => updateField('dataEntities', e.target.value)}
                placeholder="例如：patient_id, sample_id, client_id"
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-bp-text mb-1.5 block">目标变量 / 指标（逗号分隔）</label>
              <input
                type="text"
                value={form.dataTargetVariables}
                onChange={(e) => updateField('dataTargetVariables', e.target.value)}
                placeholder="例如：accuracy, f1_score, auc"
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-bp-text mb-1.5 block">合并策略</label>
                <select
                  value={form.dataMergeStrategy}
                  onChange={(e) => updateField('dataMergeStrategy', e.target.value)}
                  className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text"
                >
                  <option value="auto">自动（auto）</option>
                  <option value="stack">纵向堆叠（stack）</option>
                  <option value="join">按键连接（join）</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-bp-text mb-1.5 block">偏好数据源（逗号分隔）</label>
                <input
                  type="text"
                  value={form.dataPreferredSources}
                  onChange={(e) => updateField('dataPreferredSources', e.target.value)}
                  placeholder="zenodo, huggingface, paper_table"
                  className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-bp-text mb-1.5 block">补充数据需求说明</label>
              <textarea
                value={form.dataNeedNote}
                onChange={(e) => updateField('dataNeedNote', e.target.value)}
                placeholder="例如：需要对照实验的 baseline 表与消融实验指标…"
                rows={2}
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2.5 text-sm text-bp-text placeholder:text-bp-muted resize-none"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-bp-border/80">
              <div>
                <label className="text-xs font-medium text-bp-muted mb-1 block">完备性阈值 (%)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={form.coverageGapThreshold}
                  onChange={(e) => updateField('coverageGapThreshold', e.target.value)}
                  className="w-full bg-bp-base border border-bp-border rounded-lg px-2 py-1.5 text-sm text-bp-text"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-bp-muted mb-1 block">DataSpec 阈值 (%)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={form.dataSpecGapThreshold}
                  onChange={(e) => updateField('dataSpecGapThreshold', e.target.value)}
                  className="w-full bg-bp-base border border-bp-border rounded-lg px-2 py-1.5 text-sm text-bp-text"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-bp-muted mb-1 block">Gap 最大轮次</label>
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={form.maxGapRounds}
                  onChange={(e) => updateField('maxGapRounds', e.target.value)}
                  className="w-full bg-bp-base border border-bp-border rounded-lg px-2 py-1.5 text-sm text-bp-text"
                />
              </div>
            </div>
            <div className="pt-2 border-t border-bp-border/80">
              <label className="flex items-center gap-2 text-sm text-bp-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.autoLiteratureDiscovery !== 'false'}
                  onChange={(e) =>
                    updateField('autoLiteratureDiscovery', e.target.checked ? 'true' : 'false')
                  }
                  className="rounded border-bp-border bg-bp-base text-bp-cyan focus:ring-bp-cyan/50"
                />
                文献不足时自动检索 arXiv / OpenAlex 并导入
              </label>
              <p className="text-[10px] text-bp-muted mt-1 ml-6">
                项目文献少于 3 篇时触发；关闭后仅使用已上传的 PDF 与 arXiv 文献。
              </p>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex flex-wrap items-center gap-3 mt-6 pt-4 border-t border-bp-border">
            <Button
              icon={
                saveStatus.type === 'saving' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : saveStatus.type === 'success' ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <Save className="w-4 h-4" />
                )
              }
              variant={saveStatus.type === 'success' ? 'primary' : 'secondary'}
              disabled={saveStatus.type === 'saving'}
              onClick={handleSave}
            >
              {saveStatus.type === 'saving' ? '保存中...' : '保存研究问题'}
            </Button>
            <Button
              icon={<Play className="w-4 h-4" />}
              disabled={saveStatus.type === 'saving'}
              variant="primary"
              onClick={handleRunAgent}
            >
              保存并进入工作流
            </Button>
            <Button
              icon={<ArrowRight className="w-4 h-4" />}
              variant="secondary"
              onClick={() => navigate(`/projects/${projectId}?tab=literature`)}
            >
              下一步：文献库
            </Button>
          </div>
        </Card>
      </div>

      {/* ========== 右侧：预览卡片 ========== */}
      <div className="lg:col-span-1 space-y-4">
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-bp bg-bp-cyan-tint flex items-center justify-center">
              <Brain className="w-4 h-4 text-bp-cyan" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-bp-text">问题理解预览</h4>
              <p className="text-xs text-bp-muted">系统如何理解你的研究</p>
            </div>
          </div>

          {/* 完成度 */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-bp-muted">完成度</span>
              <span className="text-bp-muted">
                {filledCount}/{totalFields} 项
              </span>
            </div>
            <div className="h-1.5 bg-bp-panel rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-bp-cyan to-bp-cyan/70 rounded-full transition-all duration-500"
                style={{ width: `${(filledCount / totalFields) * 100}%` }}
              />
            </div>
          </div>

          <div className="space-y-3">
            {PREVIEW_ITEMS.map((item) => {
              const val = form[item.key]?.trim();
              return (
                <div key={item.key}>
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <ClipboardCheck className="w-3.5 h-3.5 text-bp-muted" />
                    <span className="text-xs font-medium text-bp-muted">{item.label}</span>
                  </div>
                  {val ? (
                    <p className="text-xs text-bp-text pl-5 line-clamp-2">{val}</p>
                  ) : (
                    <p className="text-xs text-bp-muted pl-5 italic">尚未填写</p>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* 统计信息 */}
        <Card>
          <div className="text-xs text-bp-muted space-y-2">
            <div className="flex justify-between">
              <span>表单字符数</span>
              <span className="text-bp-muted font-mono">
                {Object.values(form).reduce((s, v) => s + v.length, 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>已识别关键词</span>
              <span className="text-bp-cyan font-mono">
                {form.researchDomain.trim() ? '✓' : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>知识图谱节点</span>
              <span className="text-bp-muted font-mono">
                {filledCount > 3 ? '~' + filledCount * 4 : '—'}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}