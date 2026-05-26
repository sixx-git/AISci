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

// ============ 实验设计扩展类型（用于 ExperimentDesignPage） ============
export interface ExperimentStep {
  step: number;
  title: string;
  description: string;
  expected: string;
}

export interface DetailedExperimentDesign {
  id: string;
  hypothesisTitle: string;
  objective: string;
  methods: string;
  sourceDataset: string;
  sourceDescription: string;
  targetDataset: string;
  targetDescription: string;
  baselines: { name: string; description: string; category: 'traditional' | 'deep' | 'sota' }[];
  metrics: { name: string; description: string; target: string }[];
  steps: ExperimentStep[];
  expectedResults: string;
  limitations: string[];
}

export const MOCK_DETAILED_EXPERIMENT: DetailedExperimentDesign = {
  id: 'exp-1',
  hypothesisTitle: '自适应特征选择可显著提升小样本泛化能力',
  objective: '验证 Meta-FS（基于元学习的自适应特征选择机制）在小样本场景下对分类模型泛化能力的提升效果。核心目标：在 50-200 个标注样本条件下，Meta-FS 相较于传统特征选择方法（LASSO、RF、PCA）以及现有元学习方法（MAML、ProtoNet），在跨域分类任务上的准确率提升 ≥ 8%。',
  methods: '采用两阶段实验设计：(1) 预训练阶段，在源域数据集上训练 Meta-FS 特征选择器，使用 REINFORCE 策略梯度优化离散特征选择决策；(2) 微调阶段，在目标域的小样本训练集上对选定的特征子集训练分类器（SVM / 轻量 MLP），并在测试集上评估泛化性能。所有实验重复 5 次取平均 ± 标准差。',
  sourceDataset: 'Mini-ImageNet / CIFAR-FS',
  sourceDescription: '来自计算机视觉领域的标准小样本学习基准。Mini-ImageNet 包含 100 类，每类 600 张图像；CIFAR-FS 包含 100 类，每类 600 张图像。数据已标准化为 84×84 分辨率。',
  targetDataset: '跨域目标数据集（CUB-200 / FGVC-Aircraft / Omniglot）',
  targetDescription: 'CUB-200 为细粒度鸟类分类（200 类），FGVC-Aircraft 为飞机型号分类（100 类），Omniglot 为手写字符识别（1623 类）。选择跨域数据集以评估泛化能力。每个目标域随机采样 5-way-1-shot 和 5-way-5-shot 任务。',
  baselines: [
    { name: 'LASSO Regression', description: '基于 L1 正则化的线性特征选择方法', category: 'traditional' },
    { name: 'Random Forest Importance', description: '基于随机森林的特征重要性排序选择', category: 'traditional' },
    { name: 'PCA + SVM', description: '主成分分析降维后连接 SVM 分类器', category: 'traditional' },
    { name: 'MAML', description: 'Model-Agnostic Meta-Learning，经典元学习方法', category: 'deep' },
    { name: 'ProtoNet', description: 'Prototypical Networks，基于原型度量的元学习', category: 'deep' },
    { name: 'ANIL', description: 'Almost No Inner Loop，简化版 MAML', category: 'sota' },
    { name: 'MetaOptNet', description: '基于凸优化的元学习分类器', category: 'sota' },
  ],
  metrics: [
    { name: 'Top-1 Accuracy', description: '5-way 分类准确率（主指标）', target: '≥ 8% 相对提升' },
    { name: 'AUC-ROC', description: '分类器的 ROC 曲线下面积', target: '≥ 0.85' },
    { name: 'F1 Score', description: '精确率与召回率的调和平均', target: '≥ 0.80' },
    { name: 'Feature Stability Index', description: '多次运行中特征选择结果的一致性（Jaccard 相似度）', target: '≥ 0.75' },
    { name: 'Inference Time', description: '单次推理的端到端延迟', target: '< 50ms' },
  ],
  steps: [
    { step: 1, title: '环境准备与数据加载', description: '配置 PyTorch 1.13+ 环境，安装 torchmeta、learn2learn 等元学习库。下载并预处理 Mini-ImageNet、CIFAR-FS、CUB-200、FGVC-Aircraft、Omniglot 数据集。划分元训练集、元验证集、元测试集。', expected: '所有数据集成功加载，类别和样本数量与文献一致' },
    { step: 2, title: '基线方法复现', description: '实现 7 个基线方法（3 传统 + 4 深度学习），在 5-way-1-shot 和 5-way-5-shot 设置下运行，记录 Top-1 Accuracy 作为性能基准。确保复现结果与原始论文偏差 ≤ 2%。', expected: '7 个基线方法均成功运行，基准性能记录完整' },
    { step: 3, title: 'Meta-FS 模型训练', description: '在 Mini-ImageNet 上训练 Meta-FS 特征选择器。使用 ResNet-12 作为特征提取骨干网络，REINFORCE 算法优化离散选择策略。训练 100 个 episode，学习率 1e-3，Adam 优化器。', expected: '训练损失收敛，特征选择策略趋于稳定（最后 20 episode 标准差 < 0.1）' },
    { step: 4, title: '小样本微调与评估', description: '在目标域小样本训练集上（1-shot/5-shot），使用 Meta-FS 选定的特征子集训练 SVM 分类器。在测试集上计算所有指标。每个设置重复 5 次（不同随机种子）取平均。', expected: 'Meta-FS 在 5-shot 设置下 Top-1 Accuracy 优于所有基线 ≥ 8%' },
    { step: 5, title: '消融实验', description: '(a) 移除自适应选择 → 固定随机特征子集；(b) 移除元学习 → 在单任务上训练特征选择器；(c) 移除 REINFORCE → 贪心特征选择。逐一分析各组件的独立贡献。', expected: '完整模型优于所有消融变体，每个组件 ≥ 2% 贡献' },
    { step: 6, title: '跨域泛化分析', description: '使用在 Mini-ImageNet 上训练的 Meta-FS，直接在三个目标域上测试（不额外微调特征选择器），对比各基线方法的性能下降幅度。', expected: 'Meta-FS 的跨域性能下降幅度显著小于基线方法（性能保留率 ≥ 85%）' },
    { step: 7, title: '结果统计与报告', description: '汇总所有实验结果，进行显著性检验（配对 t-test，α=0.05）。生成表格和可视化图表（箱线图、雷达图），撰写实验分析报告。', expected: '主要比较的 p 值均 < 0.05，实验结论具有统计显著性' },
  ],
  expectedResults: '预期 Meta-FS 在 5-way-5-shot 设置下平均 Top-1 Accuracy 达到 78-82%（基线最优方法 MetaOptNet 约 70%），相对提升 11-17%。在 1-shot 设置下预期提升 6-10%。特征选择稳定性（FSI）预期 ≥ 0.80，表明方法具有较强的可复现性。消融实验预期揭示：自适应机制贡献最大（约 5%），元学习框架其次（约 3%），REINFORCE 策略贡献（约 2%）。',
  limitations: [
    '计算资源限制：Meta-FS 预训练需要 4×A100 GPU 约 12 小时，部分场景下成本较高',
    '特征选择粒度：当前为全局特征选择，未考虑不同样本可能需要不同特征子集',
    '数据集偏差：源域和目标域均为图像分类任务，未验证 NLP 等其他模态的迁移效果',
    '超参数敏感性：REINFORCE 的 baseline 函数和熵正则化系数需要针对不同场景调参',
    '样本量下限：实验假设最少 50 个标注样本；样本少于 20 时元学习可能不收敛',
  ],
};

// ============ 研究报告类型 ============
export type ReportSectionStatus = 'completed' | 'missing' | 'human_review';

export interface ReportSection {
  key: string;
  label: string;
  status: ReportSectionStatus;
  note?: string;
}

export interface ReportData {
  id: string;
  title: string;
  generatedAt: string;
  markdownContent: string;
  sections: ReportSection[];
}

export const MOCK_REPORT: ReportData = {
  id: 'report-1',
  title: '科学假设与研究计划：自适应特征选择在小样本泛化中的应用',
  generatedAt: '2026-05-25 14:32:00',
  markdownContent: `# 科学假设与研究计划

## Problem Statement

在小样本学习（Few-Shot Learning）场景下，深度学习模型的泛化能力受到特征冗余和过拟合的严重制约。现有方法通常依赖固定的特征集或手动调参，缺乏对特征空间的自适应搜索能力。本研究旨在回答以下核心问题：**自适应特征选择机制能否在小样本条件下显著提升模型的跨域泛化能力？**

## Rationale

### 理论基础

文献证据表明，特征选择对模型泛化能力具有显著的正向影响（证据集 E001-E004）。具体而言：

1. **特征冗余问题**（E001）：Mini-ImageNet 基准上，约 40% 的 CNN 特征通道在 Few-Shot 任务中贡献度低于 1%，移除这些通道对准确率影响微乎其微（Yan et al., 2019）。
2. **自适应选择的潜力**（E002）：强化学习驱动的特征搜索策略在 CIFAR-FS 上实现了比固定选择高 12.3% 的准确率。这为将强化学习方法应用于特征选择提供了直接的技术路径。
3. **跨域泛化的难点**（E003）：已有研究表明，在源域上学习的特征选择策略直接迁移到目标域时，性能平均下降 8-15%（Sun et al., 2020）。
4. **元学习框架的优势**（E004）：MAML 等元学习方法天然适合跨任务泛化，为自适应特征选择提供了理想的技术框架。

### 知识缺口

研究背景中识别出的关键缺口是：**现有方法在跨域小样本场景下，均依赖固定特征集或手动调参策略，缺少一种端到端的、基于强化学习的自适应特征选择方法**。

## Technical Details

### 核心方法：Meta-FS

Meta-FS（Meta-Learning based Feature Selection）是一种两阶段自适应特征选择框架：

- **阶段一：元学习特征选择器训练**
  - 使用 ResNet-12 作为主干网络提取特征
  - REINFORCE 策略梯度优化离散特征选择决策
  - 在源域数据集（Mini-ImageNet / CIFAR-FS）上进行跨任务元训练

- **阶段二：目标域自适应微调**
  - 利用选定的特征子集训练轻量级分类器（SVM）
  - 在小样本训练集 (1-shot / 5-shot) 上进行微调
  - 目标域测试集评估泛化性能

### 关键技术组件

1. **特征选择器**：基于策略网络 \\(\\pi_\\theta\\)，输出每个特征通道的选择概率
2. **REINFORCE 算法**：使用策略梯度更新，奖励函数为元验证集上的分类准确率
3. **分类器**：线性 SVM（1-shot）或轻量 MLP（5-shot），避免过参数化

## Datasets

### Source Data
- **Mini-ImageNet**：100 类，每类 600 张图像，84×84 分辨率
- **CIFAR-FS**：100 类，每类 600 张图像，32×32→84×84 上采样

### Target Data
- **CUB-200-2011**：细粒度鸟类分类，200 类
- **FGVC-Aircraft**：飞机型号分类，100 类
- **Omniglot**：手写字符识别，1623 类

所有目标域数据集采用 5-way-1-shot 和 5-way-5-shot 采样策略，每个设置重复 5 次实验。

## Methods

### 基线方法

| 类别 | 方法 | 描述 |
|------|------|------|
| 传统 | LASSO Regression | 基于 L1 正则化的线性特征选择 |
| 传统 | Random Forest | 基于树模型的特征重要性排序 |
| 传统 | PCA + SVM | 主成分分析降维 + SVM 分类 |
| 深度学习 | MAML | 经典元学习框架 |
| 深度学习 | ProtoNet | 原型网络度量学习 |
| SOTA | ANIL | 简化内循环的元学习方法 |
| SOTA | MetaOptNet | 基于凸优化的元学习分类器 |

### 评估指标

- **Top-1 Accuracy**：分类准确率（主指标）
- **AUC-ROC**：区分能力评估
- **F1 Score**：精确率与召回率调和平均
- **Feature Stability Index (FSI)**：特征选择可复现性
- **Inference Time**：推理效率

### 实验流程

1. 环境配置与数据加载
2. 基线方法复现（目标：偏差 ≤ 2%）
3. Meta-FS 模型训练（100 episodes，Adam lr=1e-3）
4. 小样本微调与评估（5 次重复取平均）
5. 消融实验（组件贡献分析）
6. 跨域泛化分析（3 个目标域）
7. 显著性检验与结果汇总

## Expected Results

| 实验设置 | 基线最优 | Meta-FS 预期 | 相对提升 |
|----------|----------|-------------|----------|
| 5-way-1-shot | 52.3±1.8% | 58-62% | +11-19% |
| 5-way-5-shot | 70.1±1.2% | 78-82% | +11-17% |

消融实验预期揭示：自适应机制贡献最大（约 5%），元学习框架其次（约 3%），REINFORCE 策略贡献（约 2%）。

## Limitations

1. **计算资源需求高**：Meta-FS 预训练需要 4×A100 GPU 约 12 小时
2. **数据集偏差**：仅验证了图像分类任务，未覆盖 NLP 等其他模态
3. **样本量下限**：实验假设最少 50 个标注样本
4. **超参数敏感**：REINFORCE baseline 函数需要针对不同场景调参

## References

> ⚠️ **引用合规声明**：以下所有引用均来自已上传文献库中的已验证文献，严格禁止虚构引用。

1. Yan, X., et al. (2019). "Channel Redundancy Analysis in Few-Shot CNNs." *arXiv:1905.xxxxx*. [文献库 ID: lit-1]
2. Sun, Q., et al. (2020). "Meta-Transfer Learning for Few-Shot Learning." *CVPR 2020*. [文献库 ID: lit-2]
3. Finn, C., Abbeel, P., & Levine, S. (2017). "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks." *ICML 2017*. [文献库 ID: lit-3]
4. Snell, J., Swersky, K., & Zemel, R. (2017). "Prototypical Networks for Few-Shot Learning." *NeurIPS 2017*. [文献库 ID: lit-4]
5. Lee, K., et al. (2019). "Meta-Learning with Differentiable Convex Optimization." *CVPR 2019*. [文献库 ID: lit-5]
6. Chen, W. Y., et al. (2019). "A Closer Look at Few-Shot Classification." *ICLR 2019*. [文献库 ID: lit-6]

---

*本报告由 AI Scientist 工作流自动生成于 2026-05-25，使用模型 GPT-4o / Claude 3.5 Sonnet，Prompt 版本 v2.5。请通过人在回路节点确认关键假设和实验设计。*
`,

  sections: [
    { key: 'problem_statement', label: 'Problem Statement', status: 'completed' },
    { key: 'rationale', label: 'Rationale', status: 'completed' },
    { key: 'technical_details', label: 'Technical Details', status: 'completed' },
    { key: 'datasets', label: 'Datasets', status: 'completed' },
    { key: 'source', label: 'Source', status: 'completed' },
    { key: 'target', label: 'Target', status: 'completed' },
    { key: 'paper_title', label: 'Paper Title', status: 'completed' },
    { key: 'paper_abstract', label: 'Paper Abstract', status: 'human_review', note: '建议补充更详细的贡献陈述' },
    { key: 'methods', label: 'Methods', status: 'completed' },
    { key: 'experiments', label: 'Experiments', status: 'completed' },
    { key: 'results', label: 'Results', status: 'missing', note: '需在实验执行后填充实际数据' },
    { key: 'references', label: 'References', status: 'completed' },
  ],
};

// ============ 运行日志类型 ============
export type RunLogStatus = 'success' | 'running' | 'failed' | 'pending';
export type RunLogStage = '问题理解' | '文献挖掘' | '假设生成' | '实验设计' | '实验执行' | '报告生成';

export interface RunLog {
  id: string;
  projectName: string;
  runTime: string;
  stage: RunLogStage;
  model: string;
  promptVersion: string;
  duration: string;
  status: RunLogStatus;
  // 详情
  inputSummary: string;
  outputSnapshot: string;
  errorMessage?: string;
  modelParams: Record<string, string>;
  timestampStart: string;
  timestampEnd?: string;
}

export const MOCK_RUN_LOGS: RunLog[] = [
  {
    id: 'run-001',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-25 09:15:22',
    stage: '问题理解',
    model: 'GPT-4o',
    promptVersion: 'v2.5',
    duration: '18s',
    status: 'success',
    inputSummary: '用户输入：研究小样本学习中特征选择对泛化能力的影响。系统自动提取关键词并生成结构化研究问题。',
    outputSnapshot: `{
  "research_question": "自适应特征选择机制能否显著提升小样本学习模型的跨域泛化能力？",
  "keywords": ["小样本学习", "特征选择", "泛化能力", "元学习", "跨域迁移"],
  "scope": "计算机视觉 / 图像分类"
}`,
    modelParams: { temperature: '0.7', max_tokens: '4096', top_p: '0.95' },
    timestampStart: '2026-05-25T09:15:22Z',
    timestampEnd: '2026-05-25T09:15:40Z',
  },
  {
    id: 'run-002',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-25 09:16:05',
    stage: '文献挖掘',
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v2.5',
    duration: '2m 34s',
    status: 'success',
    inputSummary: '检索关键词：few-shot learning, feature selection, meta-learning, cross-domain。检索源：arXiv, Semantic Scholar, DBLP。',
    outputSnapshot: `{
  "retrieved": 12,
  "deduplicated": 9,
  "highly_relevant": 4,
  "evidence": [
    "E001: 特征冗余在Few-Shot CNN中的定量分析",
    "E002: 强化学习驱动的特征选择策略",
    "E003: 跨域小样本泛化的难点分析",
    "E004: MAML在跨任务泛化中的优势"
  ]
}`,
    modelParams: { temperature: '0.3', max_tokens: '8192', top_p: '0.9' },
    timestampStart: '2026-05-25T09:16:05Z',
    timestampEnd: '2026-05-25T09:18:39Z',
  },
  {
    id: 'run-003',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-25 10:02:11',
    stage: '假设生成',
    model: 'GPT-4o',
    promptVersion: 'v2.5',
    duration: '1m 47s',
    status: 'success',
    inputSummary: '基于 4 条高质量证据（E001-E004）和知识缺口分析，生成结构化科学假设。',
    outputSnapshot: `{
  "hypothesis": "自适应特征选择（Meta-FS）可显著提升小样本泛化能力",
  "confidence": 0.82,
  "evidence_chain": ["E001→E002→E003→E004"],
  "alternatives": [
    "H2: 数据增强优于特征选择",
    "H3: 正则化方法可替代自适应选择"
  ]
}`,
    modelParams: { temperature: '0.5', max_tokens: '4096', top_p: '0.95' },
    timestampStart: '2026-05-25T10:02:11Z',
    timestampEnd: '2026-05-25T10:03:58Z',
  },
  {
    id: 'run-004',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-25 11:20:45',
    stage: '实验设计',
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v2.5',
    duration: '3m 12s',
    status: 'success',
    inputSummary: '基于主假设"H1"及其证据链，设计完整的实验验证方案，包括数据集、基线方法、评估指标和实验步骤。',
    outputSnapshot: `{
  "datasets": { "source": ["Mini-ImageNet", "CIFAR-FS"], "target": ["CUB-200", "Aircraft", "Omniglot"] },
  "baselines": 7,
  "metrics": ["Top-1 Acc", "AUC-ROC", "F1", "FSI", "Inference Time"],
  "steps": 7,
  "verifiability": { "has_dataset": true, "has_baselines": true, "has_metrics": true, "has_steps": true, "has_expected_results": true }
}`,
    modelParams: { temperature: '0.4', max_tokens: '8192', top_p: '0.9' },
    timestampStart: '2026-05-25T11:20:45Z',
    timestampEnd: '2026-05-25T11:23:57Z',
  },
  {
    id: 'run-005',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-25 14:15:30',
    stage: '实验执行',
    model: 'GPT-4o',
    promptVersion: 'v2.5',
    duration: '—',
    status: 'running',
    inputSummary: '启动 Meta-FS 实验执行：5-way-1-shot 设置，3 个目标域，7 个基线方法对比。预计总运行时间约 12 小时（4×A100）。',
    outputSnapshot: '实验进行中… 已完成 CUB-200 数据集的基线方法复现。',
    errorMessage: undefined,
    modelParams: { temperature: '0.2', max_tokens: '2048', top_p: '0.9' },
    timestampStart: '2026-05-25T14:15:30Z',
  },
  {
    id: 'run-006',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-24 16:40:00',
    stage: '报告生成',
    model: 'GPT-4o + Claude 3.5',
    promptVersion: 'v2.4',
    duration: '2m 08s',
    status: 'failed',
    inputSummary: '基于假设生成结果和实验设计计划，生成科学假设与研究计划报告。',
    outputSnapshot: '{ "error": "文献引用合规性校验失败：检测到 1 条虚构引用（Ref #3 未在文献库中找到对应条目）" }',
    errorMessage: '引用合规性校验失败：Reference #3 "Johnson et al. 2024" 未关联文献库中任何已上传文件。请补充文献后重试。',
    modelParams: { temperature: '0.4', max_tokens: '12288', top_p: '0.95' },
    timestampStart: '2026-05-24T16:40:00Z',
    timestampEnd: '2026-05-24T16:42:08Z',
  },
  {
    id: 'run-007',
    projectName: 'Meta-Learning Survey',
    runTime: '2026-05-23 08:30:15',
    stage: '文献挖掘',
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v2.3',
    duration: '1m 52s',
    status: 'success',
    inputSummary: '检索关键词：meta-learning, few-shot classification, gradient-based, metric-based。检索源：arXiv, NeurIPS, ICML, ICLR。',
    outputSnapshot: `{
  "retrieved": 23,
  "deduplicated": 18,
  "highly_relevant": 7,
  "evidence": [
    "MAML (Finn et al. 2017)",
    "ProtoNet (Snell et al. 2017)",
    "ANIL (Raghu et al. 2020)",
    "MetaOptNet (Lee et al. 2019)"
  ]
}`,
    modelParams: { temperature: '0.3', max_tokens: '8192', top_p: '0.9' },
    timestampStart: '2026-05-23T08:30:15Z',
    timestampEnd: '2026-05-23T08:32:07Z',
  },
  {
    id: 'run-008',
    projectName: 'Domain Adaptation Study',
    runTime: '2026-05-22 19:00:00',
    stage: '假设生成',
    model: 'Claude 3.5 Sonnet',
    promptVersion: 'v2.3',
    duration: '42s',
    status: 'failed',
    inputSummary: '基于域自适应文献检索结果，尝试生成科学假设。',
    outputSnapshot: '生成中断：文献证据不足（仅 2 条高相关），无法支撑有效假设生成。',
    errorMessage: '假设生成中止：高质量文献证据数量（2）低于最低阈值（3）。建议扩展检索范围或调整研究主题。',
    modelParams: { temperature: '0.5', max_tokens: '4096', top_p: '0.95' },
    timestampStart: '2026-05-22T19:00:00Z',
    timestampEnd: '2026-05-22T19:00:42Z',
  },
  {
    id: 'run-009',
    projectName: 'AI Scientist Demo',
    runTime: '2026-05-26 07:00:00',
    stage: '实验执行',
    model: 'GPT-4o',
    promptVersion: 'v2.5',
    duration: '—',
    status: 'pending',
    inputSummary: '待执行：Meta-FS 5-way-5-shot 实验（前次 1-shot 实验已完成）。',
    outputSnapshot: '—',
    modelParams: { temperature: '0.2', max_tokens: '2048', top_p: '0.9' },
    timestampStart: '2026-05-26T07:00:00Z',
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