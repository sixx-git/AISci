import { useState, useMemo, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Save, Play, ArrowRight, CheckCircle, XCircle, AlertTriangle,
  Tag, Target, BookOpen,
  FileOutput, Brain,
  HelpCircle, ClipboardCheck, Loader2,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { projectService } from '@/services/projectService';
import { researchQuestionKey } from '@/lib/storageKeys';
import type { ProjectOverview } from '@/types';

// ============ 表单数据类型 ============
export interface ResearchQuestionForm {
  researchDomain: string;
  researchQuestion: string;
  researchGoal: string;
  background: string;
  constraints: string;
  expectedOutput: string;
}

const EMPTY_FORM: ResearchQuestionForm = {
  researchDomain: '',
  researchQuestion: '',
  researchGoal: '',
  background: '',
  constraints: '',
  expectedOutput: '',
};

// ============ localStorage 工具函数 ============
function loadDraft(projectId: string | undefined): ResearchQuestionForm {
  if (!projectId) return { ...EMPTY_FORM };
  try {
    const saved = localStorage.getItem(researchQuestionKey(projectId));
    if (!saved) return { ...EMPTY_FORM };
    const parsed = JSON.parse(saved) as Partial<ResearchQuestionForm>;
    const form = { ...EMPTY_FORM };
    for (const key of Object.keys(EMPTY_FORM) as (keyof ResearchQuestionForm)[]) {
      if (parsed[key] != null) form[key] = String(parsed[key]);
    }
    return form;
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
  { label: '限制条件', key: 'constraints' },
  { label: '期望输出', key: 'expectedOutput' },
];

// ============ 前端字段 → 后端 snake_case 映射 ============
const FORM_TO_API_MAP: Partial<Record<keyof ResearchQuestionForm, string>> = {
  researchDomain: 'research_domain',
  researchQuestion: 'research_question',
  researchGoal: 'research_goal',
  background: 'research_background',
  constraints: 'constraints',
  expectedOutput: 'expected_output',
};

function formToApiPayload(form: ResearchQuestionForm): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [formKey, apiKey] of Object.entries(FORM_TO_API_MAP)) {
    if (apiKey && form[formKey as keyof ResearchQuestionForm]) {
      payload[apiKey] = form[formKey as keyof ResearchQuestionForm];
    }
  }
  return payload;
}

function pickNonEmptyField(local: string, remote: unknown): string {
  const trimmed = local.trim();
  if (trimmed) return local;
  const fromServer = String(remote ?? '').trim();
  return fromServer || local;
}

function projectToForm(p: ProjectOverview, prev: ResearchQuestionForm): ResearchQuestionForm {
  return {
    ...prev,
    researchDomain: pickNonEmptyField(prev.researchDomain, p.research_domain || p.research_field),
    researchQuestion: pickNonEmptyField(prev.researchQuestion, p.research_question),
    researchGoal: pickNonEmptyField(prev.researchGoal, p.research_goal),
    background: pickNonEmptyField(prev.background, p.research_background),
    constraints: pickNonEmptyField(prev.constraints, p.constraints),
    expectedOutput: pickNonEmptyField(prev.expectedOutput, p.expected_output),
  };
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
          <span className="absolute bottom-2 right-3 text-xs text-bp-muted">
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
  onSaved?: () => void;
  /** Pipeline 运行中轮询后端，自动回填空字段 */
  pollWhileRunning?: boolean;
  revalidateKey?: number;
}

export function ResearchQuestionPage({
  projectId,
  onSaved,
  pollWhileRunning = false,
  revalidateKey = 0,
}: ResearchQuestionPageProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ResearchQuestionForm>(() => loadDraft(projectId));
  const [saveStatus, setSaveStatus] = useState<SaveStatus>({ type: 'idle' });
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    if (!projectId || !pollWhileRunning) return undefined;
    const timer = setInterval(() => setReloadTick((t) => t + 1), 2500);
    return () => clearInterval(timer);
  }, [projectId, pollWhileRunning]);

  useEffect(() => {
    if (!projectId) {
      setPageLoading(false);
      setPageError('未提供项目 ID');
      return;
    }

    setPageLoading(true);
    setPageError(null);

    projectService.getProject(projectId).then((res) => {
      if (res.code !== 200 || !res.data) {
        setPageError(res.message || '加载项目信息失败');
        return;
      }
      const p = res.data;
      setForm((prev) => projectToForm(p, prev));
    }).catch((e) => {
      setPageError(e instanceof Error ? e.message : '加载项目信息失败');
    }).finally(() => setPageLoading(false));
  }, [projectId, reloadTick, revalidateKey]);

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
        bg: 'bg-bp-cyan-tint border-bp-cyan/30',
        text: '保存中...',
        textColor: 'text-bp-cyan',
      },
      success: {
        icon: <CheckCircle className={iconClass} />,
        bg: 'bg-bp-green/10 border-bp-green/30',
        text: '研究问题已保存',
        textColor: 'text-bp-green',
      },
      error: {
        icon: <XCircle className={iconClass} />,
        bg: 'bg-danger-500/10 border-danger-500/30',
        text: `保存失败: ${(saveStatus as { type: 'error'; message: string }).message}`,
        textColor: 'text-danger-300',
      },
      localSaved: {
        icon: <AlertTriangle className={iconClass} />,
        bg: 'bg-bp-yellow/10 border-bp-yellow/30',
        text: (saveStatus as { type: 'localSaved'; message: string }).message,
        textColor: 'text-bp-yellow',
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

  if (pageLoading) {
    return (
      <Card>
        <LoadingState message="正在加载研究问题…" />
      </Card>
    );
  }

  if (pageError) {
    return (
      <Card>
        <ErrorState
          message={pageError}
          onRetry={() => setReloadTick((t) => t + 1)}
        />
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* ========== 左侧：表单 ========== */}
      <div className="lg:col-span-2 space-y-5">
        <Card title="研究问题定义" subtitle="填写以下信息，AI 将基于这些内容展开研究">
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
              <span>表单完整度</span>
              <span className="text-bp-muted font-mono">
                {filledCount}/{Object.keys(form).length}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}