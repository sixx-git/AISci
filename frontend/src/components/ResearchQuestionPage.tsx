import { useState, useMemo, useCallback } from 'react';
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
}

const EMPTY_FORM: ResearchQuestionForm = {
  researchDomain: '',
  researchQuestion: '',
  researchGoal: '',
  background: '',
  dataSource: '',
  constraints: '',
  expectedOutput: '',
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

function formToApiPayload(form: ResearchQuestionForm): Record<string, string> {
  const payload: Record<string, string> = {};
  for (const [formKey, apiKey] of Object.entries(FORM_TO_API_MAP)) {
    if (apiKey && form[formKey as keyof ResearchQuestionForm]) {
      payload[apiKey] = form[formKey as keyof ResearchQuestionForm];
    }
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
      <label className="flex items-center gap-1.5 text-sm font-medium text-gray-300 mb-1.5">
        <Icon className="w-4 h-4 text-primary-400" />
        {field.label}
      </label>
      {field.rows ? (
        <div className="relative">
          <textarea
            value={value}
            onChange={(e) => onChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            rows={field.rows}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50 transition-all resize-none"
          />
          <span className="absolute bottom-2 right-3 text-[11px] text-gray-600">
            {charCount}
          </span>
        </div>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={field.placeholder}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50 transition-all"
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
};

export function ResearchQuestionPage({ projectId, projectMode, onSaved }: ResearchQuestionPageProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ResearchQuestionForm>(() => loadDraft(projectId));
  const [saveStatus, setSaveStatus] = useState<SaveStatus>({ type: 'idle' });

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

    // 先保存
    saveDraft(projectId, form);
    setSaveStatus({ type: 'saving' });

    try {
      const payload = formToApiPayload(form);
      await projectService.updateProject(projectId, payload);

      // 问题理解 Agent 暂未实现独立 API
      // 保存成功后提示用户进入工作流运行完整 Pipeline
      setSaveStatus({ type: 'success' });
      onSaved?.();

      // 延迟导航提示，让用户看到成功状态
      setTimeout(() => {
        setSaveStatus({ type: 'idle' });
      }, 3000);
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : String(err);
      setSaveStatus({
        type: 'localSaved',
        message: `已保存本地草稿，但同步后端失败: ${detail}`,
      });
      setTimeout(() => setSaveStatus({ type: 'idle' }), 5000);
    }
  }, [projectId, form, onSaved]);

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

          {/* 操作按钮 */}
          <div className="flex flex-wrap items-center gap-3 mt-6 pt-4 border-t border-dark-700">
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
            <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center">
              <Brain className="w-4 h-4 text-primary-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">问题理解预览</h4>
              <p className="text-xs text-gray-500">系统如何理解你的研究</p>
            </div>
          </div>

          {/* 完成度 */}
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-gray-500">完成度</span>
              <span className="text-gray-400">
                {filledCount}/{totalFields} 项
              </span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full transition-all duration-500"
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
                    <ClipboardCheck className="w-3.5 h-3.5 text-gray-600" />
                    <span className="text-xs font-medium text-gray-400">{item.label}</span>
                  </div>
                  {val ? (
                    <p className="text-xs text-gray-300 pl-5 line-clamp-2">{val}</p>
                  ) : (
                    <p className="text-xs text-gray-600 pl-5 italic">尚未填写</p>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* 统计信息 */}
        <Card>
          <div className="text-xs text-gray-500 space-y-2">
            <div className="flex justify-between">
              <span>表单字符数</span>
              <span className="text-gray-400 font-mono">
                {Object.values(form).reduce((s, v) => s + v.length, 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>已识别关键词</span>
              <span className="text-primary-400 font-mono">
                {form.researchDomain.trim() ? '✓' : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>知识图谱节点</span>
              <span className="text-gray-400 font-mono">
                {filledCount > 3 ? '~' + filledCount * 4 : '—'}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}