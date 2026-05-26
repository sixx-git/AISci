import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Save, Play, ArrowRight, CheckCircle,
  Tag, Target, BookOpen, Database,
  AlertTriangle, FileOutput, Brain,
  HelpCircle, ClipboardCheck,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';

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

const STORAGE_KEY = 'aisci_research_question_draft';

const EMPTY_FORM: ResearchQuestionForm = {
  researchDomain: '',
  researchQuestion: '',
  researchGoal: '',
  background: '',
  dataSource: '',
  constraints: '',
  expectedOutput: '',
};

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
}

export function ResearchQuestionPage({ projectId }: ResearchQuestionPageProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ResearchQuestionForm>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? { ...EMPTY_FORM, ...JSON.parse(saved) } : { ...EMPTY_FORM };
    } catch {
      return { ...EMPTY_FORM };
    }
  });
  const [saved, setSaved] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);

  const updateField = (key: keyof ResearchQuestionForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleRunAgent = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
    setAgentRunning(true);
    setTimeout(() => setAgentRunning(false), 2000);
  };

  const filledCount = useMemo(
    () => Object.values(form).filter((v) => v.trim().length > 0).length,
    [form],
  );

  const totalFields = Object.keys(form).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* ========== 左侧：表单 ========== */}
      <div className="lg:col-span-2 space-y-5">
        <Card title="研究问题定义" subtitle="填写以下信息，AI 将基于这些内容展开研究">
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
              icon={saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
              variant={saved ? 'primary' : 'secondary'}
              onClick={handleSave}
            >
              {saved ? '已保存' : '保存研究问题'}
            </Button>
            <Button
              icon={
                agentRunning
                  ? undefined
                  : <Play className="w-4 h-4" />
              }
              isLoading={agentRunning}
              variant="primary"
              onClick={handleRunAgent}
            >
              {agentRunning ? '智能体运行中…' : '运行问题理解智能体'}
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