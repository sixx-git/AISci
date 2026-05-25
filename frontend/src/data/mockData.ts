import type { Project, Hypothesis, ExperimentDesign } from '@/types';
import {
  BookOpen, Layers, Lightbulb, Brain,
  FlaskConical, FileText, HelpCircle, Sparkles,
  BarChart,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ============ 项目概览扩展类型 ============
export interface ProjectOverviewData extends Project {
  research_field: string;
  current_stage: string;
}

// ============ 统计卡片类型 ============
export interface StatItem {
  id: string;
  label: string;
  value: number;
  icon: LucideIcon;
  color: string;
}

// ============ Pipeline 节点类型 ============
export interface PipelineNodeData {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  icon: LucideIcon;
}

// ============ 项目概览数据 ============
export const MOCK_PROJECT_OVERVIEW: Record<string, ProjectOverviewData> = {
  '1': {
    id: '1',
    name: '深度学习优化研究',
    research_field: '人工智能 · 深度学习',
    description:
      '研究如何通过自适应特征选择和多层次知识迁移，优化深度学习模型的训练效率和小数据集泛化能力。',
    current_stage: '假设评估',
    created_at: '2026-03-15T08:30:00Z',
    updated_at: '2026-05-20T14:22:00Z',
    status: 'completed',
  },
  '2': {
    id: '2',
    name: '自然语言处理应用',
    research_field: '自然语言处理 · 大语言模型',
    description:
      '探索基于大语言模型的自然语言处理技术在实际业务场景中的应用和优化。',
    current_stage: '文献挖掘',
    created_at: '2026-04-01T10:00:00Z',
    updated_at: '2026-05-22T09:15:00Z',
    status: 'running',
  },
  '3': {
    id: '3',
    name: '计算机视觉研究',
    research_field: '计算机视觉 · 图像理解',
    description:
      '研究计算机视觉领域的新算法，包括目标检测、图像分割和视频理解等前沿方向。',
    current_stage: '问题定义',
    created_at: '2026-04-18T16:45:00Z',
    updated_at: '2026-05-18T11:30:00Z',
    status: 'draft',
  },
};

// ============ 统计卡片数据 ============
export const MOCK_STATS: Record<string, StatItem[]> = {
  '1': [
    { id: 'literature', label: '文献数量', value: 12, icon: BookOpen, color: 'text-blue-400' },
    { id: 'snippets', label: '知识片段', value: 47, icon: Layers, color: 'text-purple-400' },
    { id: 'facts', label: '提取事实', value: 23, icon: Sparkles, color: 'text-yellow-400' },
    { id: 'hypotheses', label: '候选假设', value: 3, icon: Lightbulb, color: 'text-green-400' },
    { id: 'experiments', label: '实验设计', value: 4, icon: FlaskConical, color: 'text-cyan-400' },
    { id: 'reports', label: '生成报告', value: 2, icon: FileText, color: 'text-rose-400' },
  ],
  '2': [
    { id: 'literature', label: '文献数量', value: 8, icon: BookOpen, color: 'text-blue-400' },
    { id: 'snippets', label: '知识片段', value: 31, icon: Layers, color: 'text-purple-400' },
    { id: 'facts', label: '提取事实', value: 15, icon: Sparkles, color: 'text-yellow-400' },
    { id: 'hypotheses', label: '候选假设', value: 2, icon: Lightbulb, color: 'text-green-400' },
    { id: 'experiments', label: '实验设计', value: 2, icon: FlaskConical, color: 'text-cyan-400' },
    { id: 'reports', label: '生成报告', value: 0, icon: FileText, color: 'text-rose-400' },
  ],
};

export const DEFAULT_STATS: StatItem[] = [
  { id: 'literature', label: '文献数量', value: 0, icon: BookOpen, color: 'text-blue-400' },
  { id: 'snippets', label: '知识片段', value: 0, icon: Layers, color: 'text-purple-400' },
  { id: 'facts', label: '提取事实', value: 0, icon: Sparkles, color: 'text-yellow-400' },
  { id: 'hypotheses', label: '候选假设', value: 0, icon: Lightbulb, color: 'text-green-400' },
  { id: 'experiments', label: '实验设计', value: 0, icon: FlaskConical, color: 'text-cyan-400' },
  { id: 'reports', label: '生成报告', value: 0, icon: FileText, color: 'text-rose-400' },
];

// ============ Pipeline 节点数据 ============
export const MOCK_PIPELINE_NODES: Record<string, PipelineNodeData[]> = {
  '1': [
    { id: 'question', label: '研究问题', status: 'completed', icon: HelpCircle },
    { id: 'parse', label: '文献解析', status: 'completed', icon: BookOpen },
    { id: 'extract', label: '事实提取', status: 'completed', icon: Sparkles },
    { id: 'gaps', label: '知识缺口', status: 'completed', icon: Lightbulb },
    { id: 'hypothesis', label: '假设生成', status: 'completed', icon: Brain },
    { id: 'experiment', label: '实验设计', status: 'running', icon: FlaskConical },
    { id: 'report', label: '报告生成', status: 'pending', icon: FileText },
  ],
  '2': [
    { id: 'question', label: '研究问题', status: 'completed', icon: HelpCircle },
    { id: 'parse', label: '文献解析', status: 'completed', icon: BookOpen },
    { id: 'extract', label: '事实提取', status: 'running', icon: Sparkles },
    { id: 'gaps', label: '知识缺口', status: 'pending', icon: Lightbulb },
    { id: 'hypothesis', label: '假设生成', status: 'pending', icon: Brain },
    { id: 'experiment', label: '实验设计', status: 'pending', icon: FlaskConical },
    { id: 'report', label: '报告生成', status: 'pending', icon: FileText },
  ],
};

export const DEFAULT_PIPELINE_NODES: PipelineNodeData[] = [
  { id: 'question', label: '研究问题', status: 'pending', icon: HelpCircle },
  { id: 'parse', label: '文献解析', status: 'pending', icon: BookOpen },
  { id: 'extract', label: '事实提取', status: 'pending', icon: Sparkles },
  { id: 'gaps', label: '知识缺口', status: 'pending', icon: Lightbulb },
  { id: 'hypothesis', label: '假设生成', status: 'pending', icon: Brain },
  { id: 'experiment', label: '实验设计', status: 'pending', icon: FlaskConical },
  { id: 'report', label: '报告生成', status: 'pending', icon: FileText },
];

// ============ 候选假设数据 ============
export const MOCK_HYPOTHESES: Hypothesis[] = [
  {
    id: 'h1',
    title: '深度迁移学习优化方法',
    description:
      '通过自适应特征选择和多层次知识迁移，可以显著提升深度学习模型在小数据集上的泛化能力。',
    score: 92,
    scores: { novelty: 95, feasibility: 88, scientific_value: 94, clarity: 90, testability: 91 },
  },
  {
    id: 'h2',
    title: '注意力机制的轻量化改进',
    description:
      '基于稀疏注意力的轻量化模型架构，保持精度同时大幅减少计算资源消耗。',
    score: 86,
    scores: { novelty: 82, feasibility: 90, scientific_value: 85, clarity: 88, testability: 87 },
  },
  {
    id: 'h3',
    title: '自监督预训练策略优化',
    description:
      '新型对比学习损失函数，提高预训练阶段的特征表示质量。',
    score: 81,
    scores: { novelty: 80, feasibility: 85, scientific_value: 82, clarity: 78, testability: 81 },
  },
];

// ============ 候选假设扩展类型（用于 HypothesesPage） ============
export interface DetailedHypothesis {
  id: string;
  title: string;
  content: string;
  reasoning: string;
  evidenceCount: number;
  novelty: number;
  verifiability: number;
  dataAvailability: number;
  overallScore: number;
  riskWarning: string;
  isPrimary: boolean;
  status: 'draft' | 'evaluated' | 'confirmed';
}

export const MOCK_DETAILED_HYPOTHESES: DetailedHypothesis[] = [
  {
    id: 'dh-1',
    title: '自适应特征选择可显著提升小样本泛化能力',
    content: '提出一种基于元学习的自适应特征选择机制（Meta-FS），在预训练阶段通过强化学习动态搜索最优特征子集。在仅有 50-200 个标注样本的条件下，该方法预期能将分类准确率提升 8-15%，并在 5 个跨域基准数据集上验证其泛化效果。',
    reasoning: '文献[1][3][7]表明特征选择对泛化能力有正向影响，但缺乏小样本场景下的系统验证。文献[5]的 Meta-Learning 框架提供了自适应搜索的技术基础。知识缺口分析确认：现有方法均依赖固定特征集或手动调参。',
    evidenceCount: 12,
    novelty: 88,
    verifiability: 92,
    dataAvailability: 78,
    overallScore: 86,
    riskWarning: '元学习训练过程计算开销较大，需要至少 4×A100 GPU；小样本场景下方差较高，可能需要重复实验验证。',
    isPrimary: true,
    status: 'evaluated',
  },
  {
    id: 'dh-2',
    title: '稀疏注意力机制在保持精度的同时可降低 40% 推理成本',
    content: '设计一种基于 Top-k 稀疏化的动态注意力剪枝策略（SparseAttn-V2），在推理阶段仅保留注意力权重最高的 k 个 token 对。理论分析预期 FLOPs 降低 35-45%，同时在 GLUE 和 SuperGLUE 基准上精度损失控制在 0.5% 以内。',
    reasoning: '文献[2][4]证明了注意力矩阵的稀疏性，但现有方法（如 Reformer、Linformer）在短序列上反而增加了开销。文献[8]的 Top-k 策略在 CV 领域效果显著，迁移到 NLP 有理论基础。',
    evidenceCount: 9,
    novelty: 75,
    verifiability: 95,
    dataAvailability: 90,
    overallScore: 87,
    riskWarning: 'Top-k 阈值选择对任务敏感，需针对不同任务单独调参；极短序列（<16 tokens）场景下稀疏化收益有限。',
    isPrimary: false,
    status: 'evaluated',
  },
  {
    id: 'dh-3',
    title: '基于对比学习的预训练策略可减少 60% 标注数据需求',
    content: '提出一种多粒度对比学习框架（MG-Contrast），同时利用句子级、段落级和文档级对比信号进行预训练。预期在下游分类任务中，仅用 40% 的标注数据即可达到全量监督学习的性能水平。',
    reasoning: '文献[6][10]表明对比学习在自监督预训练中效果显著，但现有方法多为单粒度。文献[11]的多粒度方法在 CV 中有效，但尚未在 NLP 预训练中探索。文献[3]的实证分析指出数据效率是当前瓶颈。',
    evidenceCount: 15,
    novelty: 82,
    verifiability: 85,
    dataAvailability: 70,
    overallScore: 79,
    riskWarning: '多粒度对比信号可能导致冲突梯度，需要精心设计损失权重；标注数据成本本身可能高于训练成本。',
    isPrimary: false,
    status: 'draft',
  },
  {
    id: 'dh-4',
    title: '跨模态知识蒸馏可突破单模态模型性能上限',
    content: '利用视觉-语言预训练模型（如 CLIP）作为教师网络，通过知识蒸馏将跨模态语义信息注入纯文本模型。预期在语义理解任务上获得 3-5% 的提升，且在低资源语言上泛化效果更显著。',
    reasoning: '文献[9][12]展示了跨模态模型的强大语义理解能力。文献[13]的知识蒸馏方法为跨模态迁移提供了技术路径。当前纯文本模型在常识推理上存在天花板效应的证据来自文献[14]。',
    evidenceCount: 8,
    novelty: 91,
    verifiability: 72,
    dataAvailability: 65,
    overallScore: 76,
    riskWarning: '视觉-语言模型与纯文本模型的表示空间对齐难度高；蒸馏过程可能丢失重要的文本特有特征；跨模态数据集构建成本高。',
    isPrimary: false,
    status: 'draft',
  },
  {
    id: 'dh-5',
    title: '动态课程学习策略可加速模型收敛并提升最终性能',
    content: '基于样本难度估计的自动课程学习策略（Auto-CL），通过在线评估每个样本的学习难度，动态调整训练数据顺序和采样权重。预期收敛速度提升 20-30%，最终性能提升 1-3 个百分点。',
    reasoning: '文献[15][16]的理论分析表明课程学习对非凸优化有帮助。文献[17]的难度估计方法提供了自动化基础，但现有方法在 NLP 领域验证不足。文献[18]的实证研究表明训练顺序对 Transformer 有显著影响。',
    evidenceCount: 10,
    novelty: 78,
    verifiability: 88,
    dataAvailability: 92,
    overallScore: 86,
    riskWarning: '难度估计模型本身需要训练，引入了额外的计算开销和超参数；课程策略可能在特定任务上反而降低性能。',
    isPrimary: false,
    status: 'draft',
  },
];

// ============ 实验设计数据 ============
export const MOCK_EXPERIMENTS: ExperimentDesign[] = [
  {
    id: 'e1', step: 1, name: '基准模型训练',
    description: '使用标准预训练模型在目标数据集上训练，建立性能基准。',
    expected_result: '达到现有文献中的基准性能',
    success_criteria: '准确率在基准 ±5% 范围内',
  },
  {
    id: 'e2', step: 2, name: '特征空间分析',
    description: '分析不同层的特征表示，识别关键信息区域。',
    expected_result: '识别出任务相关的特征空间分布',
    success_criteria: '可视化结果支持研究假设',
  },
  {
    id: 'e3', step: 3, name: '对比实验验证',
    description: '实现提出的优化方法，与基线方法进行全面对比。',
    expected_result: '性能显著优于基准方法',
    success_criteria: '准确率提升 ≥ 5%，F1 提升 ≥ 3%',
  },
  {
    id: 'e4', step: 4, name: '消融实验',
    description: '逐一移除各优化组件，验证每个模块的独立贡献。',
    expected_result: '完整模型优于任一单独组件',
    success_criteria: '每个组件贡献 ≥ 2% 性能提升',
  },
];

// ============ 文献库类型 ============
export interface LiteratureItem {
  id: string;
  title: string;
  authors: string;
  year: number;
  type: '论文' | '综述' | '会议' | '预印本';
  parseStatus: 'pending' | 'parsing' | 'completed' | 'error';
  snippetCount: number;
  factCount: number;
  fileSize: string;
  uploadDate: string;
}

export interface LiteratureStats {
  uploaded: number;
  parsed: number;
  snippets: number;
  facts: number;
}

// ============ 文献库数据 ============
export const MOCK_LITERATURE: LiteratureItem[] = [
  {
    id: 'lit-1',
    title: 'Attention Is All You Need',
    authors: 'Vaswani et al.',
    year: 2017,
    type: '会议',
    parseStatus: 'completed',
    snippetCount: 24,
    factCount: 15,
    fileSize: '1.2 MB',
    uploadDate: '2026-05-10',
  },
  {
    id: 'lit-2',
    title: 'BERT: Pre-training of Deep Bidirectional Transformers',
    authors: 'Devlin et al.',
    year: 2019,
    type: '会议',
    parseStatus: 'completed',
    snippetCount: 31,
    factCount: 22,
    fileSize: '2.1 MB',
    uploadDate: '2026-05-12',
  },
  {
    id: 'lit-3',
    title: 'Deep Residual Learning for Image Recognition',
    authors: 'He et al.',
    year: 2016,
    type: '会议',
    parseStatus: 'completed',
    snippetCount: 18,
    factCount: 11,
    fileSize: '1.8 MB',
    uploadDate: '2026-05-08',
  },
  {
    id: 'lit-4',
    title: 'A Survey of Large Language Models',
    authors: 'Zhao et al.',
    year: 2023,
    type: '综述',
    parseStatus: 'parsing',
    snippetCount: 0,
    factCount: 0,
    fileSize: '4.5 MB',
    uploadDate: '2026-05-20',
  },
  {
    id: 'lit-5',
    title: 'Learning Transferable Visual Models From Natural Language Supervision',
    authors: 'Radford et al.',
    year: 2021,
    type: '预印本',
    parseStatus: 'completed',
    snippetCount: 27,
    factCount: 19,
    fileSize: '3.2 MB',
    uploadDate: '2026-05-15',
  },
  {
    id: 'lit-6',
    title: 'Denoising Diffusion Probabilistic Models',
    authors: 'Ho et al.',
    year: 2020,
    type: '会议',
    parseStatus: 'pending',
    snippetCount: 0,
    factCount: 0,
    fileSize: '2.7 MB',
    uploadDate: '2026-05-22',
  },
];

export function computeLiteratureStats(items: LiteratureItem[]): LiteratureStats {
  return {
    uploaded: items.length,
    parsed: items.filter((i) => i.parseStatus === 'completed').length,
    snippets: items.reduce((sum, i) => sum + i.snippetCount, 0),
    facts: items.reduce((sum, i) => sum + i.factCount, 0),
  };
}

// ============ 智能体工作流类型 ============
export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'human_review';

export interface AgentNodeData {
  id: string;
  name: string;
  shortDesc: string;
  status: AgentStatus;
  duration: number | null; // ms
  inputSummary: string;
  outputSummary: string;
  logs: string[];
  model: string;
  promptVersion: string;
  icon: LucideIcon;
}

// ============ 工作流数据 ============
export const MOCK_AGENT_NODES: AgentNodeData[] = [
  {
    id: 'problem',
    name: '问题理解智能体',
    shortDesc: '解析研究问题，提取关键概念、约束条件和评估标准',
    status: 'completed',
    duration: 3200,
    inputSummary: '用户输入：\"如何通过自适应特征选择提升小样本泛化能力？\"',
    outputSummary: '识别到 3 个关键概念（特征选择、小样本学习、泛化能力），定义了 5 项评估指标。',
    logs: [
      '[14:30:01] 接收到研究问题',
      '[14:30:01] 实体识别：检测到 3 个核心概念',
      '[14:30:01] 关系抽取：构建概念关联图',
      '[14:30:02] 约束分析：数据量 < 1000 样本',
      '[14:30:03] 问题理解完成，生成结构化描述',
    ],
    model: 'GPT-4o',
    promptVersion: 'v2.1',
    icon: HelpCircle,
  },
  {
    id: 'literature',
    name: '文献挖掘智能体',
    shortDesc: '检索语义相关文献，构建知识图谱与引用网络',
    status: 'completed',
    duration: 8500,
    inputSummary: '检索关键词：few-shot learning, feature selection, domain adaptation, transfer learning',
    outputSummary: '检索到 47 篇相关文献，筛选出 12 篇高相关性论文，构建了 31 节点的知识图谱。',
    logs: [
      '[14:30:03] 构建语义检索查询',
      '[14:30:04] 检索 arXiv: 23 篇',
      '[14:30:05] 检索 Semantic Scholar: 18 篇',
      '[14:30:06] 检索 PubMed: 6 篇',
      '[14:30:07] 去重后共 47 篇候选文献',
      '[14:30:08] 相关性排序：Top-12 通过阈值',
      '[14:30:09] 实体抽取：31 个知识节点',
      '[14:30:11] 文献挖掘完成',
    ],
    model: 'GPT-4o + SciBERT',
    promptVersion: 'v2.3',
    icon: BookOpen,
  },
  {
    id: 'extract',
    name: '事实提取智能体',
    shortDesc: '从文献中提取结构化科学事实与实验数据',
    status: 'completed',
    duration: 6200,
    inputSummary: '12 篇文献全文，31 个知识节点上下文',
    outputSummary: '提取 23 条结构化事实，其中 15 条为方法类、5 条为结果类、3 条为数据集类。',
    logs: [
      '[14:30:11] 加载文献全文',
      '[14:30:12] 分句与段落检测',
      '[14:30:13] NER 实体提取：方法/数据集/指标/结论',
      '[14:30:14] 三值验证检查：15/23 通过',
      '[14:30:15] 结构化事实存入知识库',
      '[14:30:17] 事实提取完成',
    ],
    model: 'GPT-4o',
    promptVersion: 'v1.8',
    icon: Sparkles,
  },
  {
    id: 'gaps',
    name: '知识缺口发现智能体',
    shortDesc: '对比已知事实与研究目标，识别研究空白',
    status: 'running',
    duration: null,
    inputSummary: '23 条已知事实 + 研究目标：提升小样本泛化能力',
    outputSummary: '分析中…正在进行知识缺口交叉对比。',
    logs: [
      '[14:30:17] 加载事实库（23 条）',
      '[14:30:18] 构建研究目标知识图谱',
      '[14:30:19] 交叉对比中…',
      '[14:30:20] 检测到潜在缺口：自适应特征选择方法在小样本场景下缺乏系统验证',
    ],
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v3.0',
    icon: Lightbulb,
  },
  {
    id: 'hypothesis',
    name: '假设生成智能体',
    shortDesc: '基于知识缺口，生成可验证的候选科学假设',
    status: 'pending',
    duration: null,
    inputSummary: '待知识缺口筛选完成后传入',
    outputSummary: '—',
    logs: [],
    model: 'GPT-4o',
    promptVersion: 'v2.5',
    icon: Brain,
  },
  {
    id: 'evaluation',
    name: '可行性评估智能体',
    shortDesc: '评估假设的新颖性、可行性、科学价值和可测试性',
    status: 'pending',
    duration: null,
    inputSummary: '待假设生成后传入',
    outputSummary: '—',
    logs: [],
    model: 'GPT-4o + Review Model',
    promptVersion: 'v2.0',
    icon: BarChart,
  },
  {
    id: 'experiment',
    name: '实验设计智能体',
    shortDesc: '自动设计实验方案、评估指标与验证流程',
    status: 'pending',
    duration: null,
    inputSummary: '待假设评估通过后传入',
    outputSummary: '—',
    logs: [],
    model: 'GPT-4o',
    promptVersion: 'v2.0',
    icon: FlaskConical,
  },
  {
    id: 'report',
    name: '报告生成智能体',
    shortDesc: '整合所有结果，生成结构化研究报告',
    status: 'pending',
    duration: null,
    inputSummary: '待所有前置节点完成后传入',
    outputSummary: '—',
    logs: [],
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v1.5',
    icon: FileText,
  },
];