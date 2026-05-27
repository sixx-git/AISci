// ============================================================
// 统一 Mock 数据 —— 所有页面数据均从此文件获取
// 类型定义统一从 @/types 导入
// ============================================================

import {
  BookOpen, Layers, Lightbulb, Brain,
  FlaskConical, FileText, HelpCircle, Sparkles,
  BarChart,
} from 'lucide-react';

import type {
  ProjectOverview,
  StatItem,
  PipelineNodeData,
  Hypothesis,
  DetailedHypothesis,
  ExperimentDesign,
  DetailedExperimentDesign,
  LiteratureItem,
  EvidenceItem,
  AgentNodeData,
  LiteratureStats,
  ReportData,
  ReportSection,
  RunLog,
  ResearchResult,
} from '@/types';

// ==================== 辅助函数 ====================

export function computeLiteratureStats(items: LiteratureItem[]): LiteratureStats {
  return {
    uploaded: items.length,
    parsed: items.filter(i => i.parseStatus === 'completed').length,
    snippets: items.reduce((s, i) => s + i.snippetCount, 0),
    facts: items.reduce((s, i) => s + i.factCount, 0),
  };
}

// ============================================================
// 1. 项目概览（3 个项目）
// ============================================================

export const MOCK_PROJECTS: Record<string, ProjectOverview> = {
  '1': {
    id: '1',
    name: '深度学习优化研究',
    research_field: '人工智能 · 深度学习',
    description: '研究如何通过自适应特征选择和多层次知识迁移，优化深度学习模型的训练效率和小数据集泛化能力。',
    current_stage: '假设评估',
    research_question: '自适应特征选择机制能否显著提升小样本学习模型的跨域泛化能力？',
    created_at: '2026-03-15T08:30:00Z',
    updated_at: '2026-05-20T14:22:00Z',
    status: 'completed',
  },
  '2': {
    id: '2',
    name: '自然语言处理应用',
    research_field: '自然语言处理 · 大语言模型',
    description: '探索基于大语言模型的自然语言处理技术在实际业务场景中的应用和优化。',
    current_stage: '文献挖掘',
    research_question: '如何利用大语言模型的上下文理解能力提升多轮对话的准确性？',
    created_at: '2026-04-01T10:00:00Z',
    updated_at: '2026-05-22T09:15:00Z',
    status: 'running',
  },
  '3': {
    id: '3',
    name: '计算机视觉研究',
    research_field: '计算机视觉 · 图像理解',
    description: '研究计算机视觉领域的新算法，包括目标检测、图像分割和视频理解等前沿方向。',
    current_stage: '问题定义',
    research_question: '基于注意力机制的轻量级目标检测模型能否在边缘设备上达到实时性能？',
    created_at: '2026-04-18T16:45:00Z',
    updated_at: '2026-05-18T11:30:00Z',
    status: 'draft',
  },
};

// 向后兼容别名
export { MOCK_PROJECTS as MOCK_PROJECT_OVERVIEW };

// ============================================================
// 2. 统计卡片（按项目）
// ============================================================

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

// ============================================================
// 3. Pipeline 节点（按项目）
// ============================================================

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

// ============================================================
// 4. 候选假设 —— 基础评分（4 条）
// ============================================================

export const MOCK_HYPOTHESES: Hypothesis[] = [
  {
    id: 'h1',
    title: '自适应特征选择可显著提升小样本泛化能力',
    description: '通过自适应特征选择和多层次知识迁移，可以显著提升深度学习模型在小数据集上的泛化能力。',
    score: 92,
    scores: { novelty: 95, feasibility: 88, scientific_value: 94, clarity: 90, testability: 91 },
  },
  {
    id: 'h2',
    title: '注意力机制的轻量化改进',
    description: '基于稀疏注意力的轻量化模型架构，保持精度同时大幅减少计算资源消耗。',
    score: 86,
    scores: { novelty: 82, feasibility: 90, scientific_value: 85, clarity: 88, testability: 87 },
  },
  {
    id: 'h3',
    title: '自监督预训练策略优化',
    description: '新型对比学习损失函数，提高预训练阶段的特征表示质量。',
    score: 81,
    scores: { novelty: 80, feasibility: 85, scientific_value: 82, clarity: 78, testability: 81 },
  },
  {
    id: 'h4',
    title: '跨模态知识蒸馏突破单模态性能上限',
    description: '利用视觉-语言预训练模型作为教师网络，通过知识蒸馏将跨模态语义信息注入纯文本模型。',
    score: 76,
    scores: { novelty: 91, feasibility: 72, scientific_value: 78, clarity: 75, testability: 70 },
  },
];

// ============================================================
// 5. 候选假设 —— 详细评估（4 条）
// ============================================================

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
];

// ======================== 证据链Mock数据 ========================

export const MOCK_EVIDENCE_CHAINS: Record<string, EvidenceItem[]> = {
  'dh-1': [
    {
      id: 'ev-001',
      project_id: 'proj-001',
      hypothesis_id: 'dh-1',
      document_id: 'doc-100',
      chunk_id: 'chunk-1001',
      fact_text: '癌细胞在低氧环境下会通过激活HIF-1α信号通路来增强葡萄糖摄取和糖酵解活性，这一代谢重编程过程被称为Warburg效应的核心机制。',
      quote_text: 'Under hypoxic conditions, HIF-1α stabilization leads to upregulation of GLUT1, HK2, and LDHA, driving a metabolic switch toward aerobic glycolysis......',
      page_number: 3,
      relevance_score: 0.92,
      source_title: 'Tumor Metabolism and Hypoxia: Mechanisms of Metabolic Reprogramming',
    },
    {
      id: 'ev-002',
      project_id: 'proj-001',
      hypothesis_id: 'dh-1',
      document_id: 'doc-100',
      chunk_id: 'chunk-1005',
      fact_text: '研究表明HIF-1α通过转录激活PDK1基因，抑制丙酮酸脱氢酶复合体活性，从而阻断丙酮酸进入三羧酸循环。',
      quote_text: 'HIF-1α directly binds to HRE in the PDK1 promoter, inducing its expression and subsequently phosphorylating PDH to inhibit its activity......',
      page_number: 5,
      relevance_score: 0.85,
      source_title: 'Tumor Metabolism and Hypoxia: Mechanisms of Metabolic Reprogramming',
    },
    {
      id: 'ev-003',
      project_id: 'proj-001',
      hypothesis_id: 'dh-1',
      document_id: 'doc-101',
      chunk_id: 'chunk-2003',
      fact_text: 'HK2在多种恶性肿瘤中呈现高表达，且与不良预后显著相关，被认为是癌细胞的代谢脆弱点。',
      quote_text: 'HK2 overexpression was observed in 78% of tumor samples and correlated with decreased overall survival (HR=2.34, p<0.001)......',
      page_number: 7,
      relevance_score: 0.88,
      source_title: 'Hexokinase 2 as a Metabolic Vulnerability in Aggressive Cancers',
    },
    {
      id: 'ev-004',
      project_id: 'proj-001',
      hypothesis_id: 'dh-1',
      document_id: 'doc-102',
      chunk_id: 'chunk-3010',
      fact_text: 'Lonidamine是一种HK2抑制剂，已在II期临床试验中显示出对多种实体瘤的抑瘤活性，但存在剂量限制性肝毒性。',
      quote_text: 'In a Phase II trial, lonidamine combined with chemotherapy showed a 32% objective response rate in NSCLC patients, though grade 3 hepatotoxicity was observed in 15%......',
      page_number: 12,
      relevance_score: 0.81,
      source_title: 'Lonidamine in Cancer Therapy: Clinical Experience and Future Directions',
    },
  ],
  'dh-2': [
    {
      id: 'ev-005',
      project_id: 'proj-001',
      hypothesis_id: 'dh-2',
      document_id: undefined,
      chunk_id: 'chunk-4001',
      fact_text: '单细胞RNA测序分析揭示肿瘤微环境中存在多种免疫抑制性细胞亚群，其中Treg细胞和MDSC细胞的比例在治疗后显著升高。',
      quote_text: 'scRNA-seq analysis of tumor-infiltrating lymphocytes revealed a 5.2-fold increase in FOXP3+ Tregs post-chemotherapy......',
      page_number: 2,
      relevance_score: 0.90,
      source_title: 'Single-Cell Profiling of the Tumor Immune Microenvironment',
    },
    {
      id: 'ev-006',
      project_id: 'proj-001',
      hypothesis_id: 'dh-2',
      document_id: undefined,
      chunk_id: 'chunk-4012',
      fact_text: '免疫检查点分子PD-L1在肿瘤细胞和肿瘤相关巨噬细胞上均有表达，其表达水平与免疫治疗响应率正相关。',
      quote_text: 'PD-L1 expression on both tumor cells (TC) and tumor-associated macrophages (TAMs) correlated with improved response to anti-PD-1 therapy (AUC=0.82)......',
      page_number: 8,
      relevance_score: 0.87,
      source_title: 'Single-Cell Profiling of the Tumor Immune Microenvironment',
    },
    {
      id: 'ev-007',
      project_id: 'proj-001',
      hypothesis_id: 'dh-2',
      document_id: 'doc-104',
      chunk_id: 'chunk-5005',
      fact_text: '代谢干预（如二甲双胍使用）可以重塑肿瘤免疫微环境，减少MDSC的浸润并增强CD8+ T细胞的杀伤功能。',
      quote_text: 'Metformin treatment significantly reduced MDSC infiltration by 45% and enhanced CD8+ T cell cytotoxicity in syngeneic tumor models......',
      page_number: 15,
      relevance_score: 0.84,
      source_title: 'Metabolic Interventions Shape the Antitumor Immune Response',
    },
  ],
  'dh-3': [
    {
      id: 'ev-008',
      project_id: 'proj-001',
      hypothesis_id: 'dh-3',
      document_id: 'doc-105',
      chunk_id: 'chunk-6003',
      fact_text: 'CRISPR全基因组筛选鉴定出GLS和GOT2是谷氨酰胺代谢途径中的关键节点基因，敲除后显著抑制肿瘤生长。',
      quote_text: 'Pooled CRISPR screening identified GLS and GOT2 as synthetic lethal partners in KRAS-mutant pancreatic cancer, with GLS KO reducing tumor volume by 72%......',
      page_number: 4,
      relevance_score: 0.91,
      source_title: 'CRISPR-Based Identification of Metabolic Dependencies in KRAS-Mutant Cancers',
    },
    {
      id: 'ev-009',
      project_id: 'proj-001',
      hypothesis_id: 'dh-3',
      document_id: 'doc-106',
      chunk_id: 'chunk-7008',
      fact_text: '谷氨酰胺酶抑制剂CB-839在I期临床试验中展现了良好的安全性特征，但在单药治疗中疗效有限，提示需要联合用药策略。',
      quote_text: 'CB-839 was well-tolerated at doses up to 800mg BID, with disease control rate of 28% as monotherapy, suggesting combination strategies are needed......',
      page_number: 10,
      relevance_score: 0.79,
      source_title: 'Phase I Study of the Glutaminase Inhibitor CB-839 in Solid Tumors',
    },
  ],
  'dh-4': [
    {
      id: 'ev-010',
      project_id: 'proj-001',
      hypothesis_id: 'dh-4',
      document_id: 'doc-107',
      chunk_id: 'chunk-8002',
      fact_text: '纳米脂质体递送系统可将siRNA有效递送至肿瘤组织，在动物模型中实现了80%以上的靶基因沉默效率。',
      quote_text: 'LNPs encapsulating siRNA achieved >80% target gene knockdown in tumor xenografts, with preferential accumulation via the EPR effect......',
      page_number: 6,
      relevance_score: 0.86,
      source_title: 'Lipid Nanoparticle Delivery Systems for Cancer Gene Therapy',
    },
    {
      id: 'ev-011',
      project_id: 'proj-001',
      hypothesis_id: 'dh-4',
      document_id: 'doc-108',
      chunk_id: 'chunk-9001',
      fact_text: '双重靶向策略（同时抑制糖酵解和谷氨酰胺代谢）在体外实验中展现出协同抗肿瘤效应，联合指数CI<1。',
      quote_text: 'Combined inhibition of glycolysis (2-DG) and glutaminolysis (BPTES) showed synergistic cytotoxicity with CI=0.61 in multiple cancer cell lines......',
      page_number: 3,
      relevance_score: 0.93,
      source_title: 'Dual Targeting of Cancer Metabolism: Synergistic Approaches',
    },
  ],
};

// ============================================================
// 6. 文献库（5 篇）
// ============================================================

export const MOCK_LITERATURE: LiteratureItem[] = [
  {
    id: 'lit-1',
    title: 'Attention Is All You Need',
    authors: 'Vaswani et al.',
    year: 2017,
    type: '论文',
    parseStatus: 'completed',
    snippetCount: 34,
    factCount: 12,
    fileSize: '2.1 MB',
    uploadDate: '2026-05-20',
  },
  {
    id: 'lit-2',
    title: 'BERT: Pre-training of Deep Bidirectional Transformers',
    authors: 'Devlin et al.',
    year: 2019,
    type: '论文',
    parseStatus: 'completed',
    snippetCount: 28,
    factCount: 11,
    fileSize: '3.4 MB',
    uploadDate: '2026-05-20',
  },
  {
    id: 'lit-3',
    title: 'Deep Learning Survey',
    authors: 'LeCun, Bengio & Hinton',
    year: 2015,
    type: '综述',
    parseStatus: 'completed',
    snippetCount: 56,
    factCount: 24,
    fileSize: '5.2 MB',
    uploadDate: '2026-05-21',
  },
  {
    id: 'lit-4',
    title: 'Model-Agnostic Meta-Learning for Fast Adaptation',
    authors: 'Finn, Abbeel & Levine',
    year: 2017,
    type: '会议',
    parseStatus: 'parsing',
    snippetCount: 0,
    factCount: 0,
    fileSize: '1.8 MB',
    uploadDate: '2026-05-22',
  },
  {
    id: 'lit-5',
    title: 'ResNet: Deep Residual Learning for Image Recognition',
    authors: 'He et al.',
    year: 2016,
    type: '论文',
    parseStatus: 'pending',
    snippetCount: 0,
    factCount: 0,
    fileSize: '3.1 MB',
    uploadDate: '2026-05-23',
  },
];

// ============================================================
// 7. 智能体工作流节点（8 个）
// ============================================================

export const MOCK_AGENT_NODES: AgentNodeData[] = [
  {
    id: 'problem',
    name: '问题理解智能体',
    shortDesc: '解析研究问题，提取关键概念、约束条件和评估标准',
    status: 'completed',
    duration: 3200,
    inputSummary: '用户输入："如何通过自适应特征选择提升小样本泛化能力？"',
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
    id: 'gaps',
    name: '知识缺口发现智能体',
    shortDesc: '对比已知事实与研究目标，识别研究空白',
    status: 'pending',
    duration: null,
    inputSummary: '23 条已知事实 + 研究目标：提升小样本泛化能力',
    outputSummary: '—',
    logs: [],
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
    id: 'validation',
    name: '小样验证智能体',
    shortDesc: '小规模实验验证，生成验证报告',
    status: 'pending',
    duration: null,
    inputSummary: '待实验设计通过后传入',
    outputSummary: '—',
    logs: [],
    model: 'GPT-4o',
    promptVersion: 'v1.0',
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

// ============================================================
// 8. 实验设计 —— 基础步骤（4 步）
// ============================================================

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

// ============================================================
// 9. 实验设计 —— 详细方案（1 个）
// ============================================================

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

// ============================================================
// 10. 研究报告（1 份）
// ============================================================

export const MOCK_REPORT: ReportData = {
  id: 'report-1',
  title: '科学假设与研究计划：自适应特征选择在小样本泛化中的应用',
  generatedAt: '2026-05-25 14:32:00',
  pdfSuccess: true,
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

## Limitations

1. **计算资源需求高**：Meta-FS 预训练需要 4×A100 GPU 约 12 小时
2. **数据集偏差**：仅验证了图像分类任务，未覆盖 NLP 等其他模态

## References

> ⚠️ **引用合规声明**：以下所有引用均来自已上传文献库中的已验证文献，严格禁止虚构引用。

1. Yan, X., et al. (2019). "Channel Redundancy Analysis in Few-Shot CNNs." *arXiv:1905.xxxxx*. [文献库 ID: lit-1]
2. Sun, Q., et al. (2020). "Meta-Transfer Learning for Few-Shot Learning." *CVPR 2020*. [文献库 ID: lit-2]
3. Finn, C., Abbeel, P., & Levine, S. (2017). "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks." *ICML 2017*. [文献库 ID: lit-3]

---

*本报告由 AI Scientist 工作流自动生成于 2026-05-25，使用模型 GPT-4o / Claude 3.5 Sonnet，Prompt 版本 v2.5。请通过人在回路节点确认关键假设和实验设计。*
`,
  sections: [
    { key: 'paper_title', label: '0. Paper Title', status: 'completed' },
    { key: 'paper_abstract', label: '1. Paper Abstract', status: 'completed' },
    { key: 'problem_statement', label: '2. Problem Statement', status: 'completed' },
    { key: 'literature_facts', label: '3. Literature Facts', status: 'completed' },
    { key: 'knowledge_gaps', label: '4. Knowledge Gaps', status: 'completed' },
    { key: 'scientific_hypothesis', label: '5. Hypothesis', status: 'completed' },
    { key: 'rationale', label: '6. Rationale', status: 'completed' },
    { key: 'technical_details', label: '7. Technical Details', status: 'completed' },
    { key: 'datasets', label: '8. Datasets', status: 'completed' },
    { key: 'source', label: '9. Source', status: 'completed' },
    { key: 'target', label: '10. Target', status: 'completed' },
    { key: 'methods', label: '11. Methods', status: 'completed' },
    { key: 'experiments', label: '12. Experiments', status: 'completed' },
    { key: 'results_feasibility', label: '13. Results', status: 'human_review', note: '仅包含预期结果，需实际执行后补充' },
    { key: 'human_review', label: '14. Human-in-the-loop Review', status: 'completed' },
    { key: 'references', label: '15. References', status: 'completed' },
  ],
  complianceCheck: {
    total_items: 16,
    completed: 14,
    missing: 1,
    human_review: 1,
    references_verified: 4,
    references_suspicious: 0,
    references_replaced: false,
    evidence_fact_count: 6,
    hypothesis_with_evidence_count: 2,
    has_actual_or_simulated_result: true,
    result_type: 'simulated_or_expected',
    items: [
      { key: 'paper_title', label: '0. Paper Title', status: 'completed' },
      { key: 'paper_abstract', label: '1. Paper Abstract', status: 'completed' },
      { key: 'problem_statement', label: '2. Problem Statement', status: 'completed' },
      { key: 'literature_facts', label: '3. Literature Facts', status: 'completed' },
      { key: 'knowledge_gaps', label: '4. Knowledge Gaps', status: 'completed' },
      { key: 'scientific_hypothesis', label: '5. Hypothesis', status: 'completed' },
      { key: 'rationale', label: '6. Rationale', status: 'completed' },
      { key: 'technical_details', label: '7. Technical Details', status: 'completed' },
      { key: 'datasets', label: '8. Datasets', status: 'completed' },
      { key: 'source', label: '9. Source', status: 'completed' },
      { key: 'target', label: '10. Target', status: 'completed' },
      { key: 'methods', label: '11. Methods', status: 'completed' },
      { key: 'experiments', label: '12. Experiments', status: 'completed' },
      { key: 'results_feasibility', label: '13. Results', status: 'human_review', note: '仅包含预期结果，需实际执行后补充' },
      { key: 'human_review', label: '14. Human-in-the-loop Review', status: 'completed' },
      { key: 'references', label: '15. References', status: 'completed' },
    ],
  },
};

/** MOCK_REPORT 的 sections 独立导出（兜底用） */
export const MOCK_REPORT_SECTIONS: ReportSection[] = MOCK_REPORT.sections;

// ============================================================
// 11. 运行日志（6 条）
// ============================================================

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
  "evidence": ["E001", "E002", "E003", "E004"]
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
  "evidence_chain": ["E001→E002→E003→E004"]
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
    inputSummary: '基于主假设"H1"及其证据链，设计完整的实验验证方案。',
    outputSnapshot: `{
  "datasets": { "source": ["Mini-ImageNet", "CIFAR-FS"], "target": ["CUB-200", "Aircraft", "Omniglot"] },
  "baselines": 7,
  "metrics": ["Top-1 Acc", "AUC-ROC", "F1", "FSI", "Inference Time"],
  "steps": 7
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
    outputSnapshot: '{ "error": "文献引用合规性校验失败：检测到 1 条虚构引用" }',
    errorMessage: '引用合规性校验失败：Reference #3 未关联文献库中任何已上传文件。请补充文献后重试。',
    modelParams: { temperature: '0.4', max_tokens: '12288', top_p: '0.95' },
    timestampStart: '2026-05-24T16:40:00Z',
    timestampEnd: '2026-05-24T16:42:08Z',
  },
];

// ============================================================
// 12. 研究结果 —— 聚合数据
// ============================================================

export const MOCK_RESEARCH_RESULTS: ResearchResult = {
  hypotheses: [
    {
      id: 'h1',
      title: '自适应特征选择可显著提升小样本泛化能力',
      description: '通过自适应特征选择和多层次知识迁移，可以显著提升深度学习模型在小数据集上的泛化能力，特别是在跨域任务中。',
      score: 92,
      scores: { novelty: 95, feasibility: 88, scientific_value: 94, clarity: 90, testability: 91 },
    },
    {
      id: 'h2',
      title: '注意力机制的轻量化改进',
      description: '提出一种基于稀疏注意力的轻量化模型架构，可以在保持精度的同时，大幅减少计算资源消耗。',
      score: 86,
      scores: { novelty: 82, feasibility: 90, scientific_value: 85, clarity: 88, testability: 87 },
    },
    {
      id: 'h3',
      title: '自监督预训练策略优化',
      description: '探索新型的对比学习损失函数，提高预训练阶段的特征表示质量。',
      score: 81,
      scores: { novelty: 80, feasibility: 85, scientific_value: 82, clarity: 78, testability: 81 },
    },
    {
      id: 'h4',
      title: '跨模态知识蒸馏突破单模态性能上限',
      description: '利用视觉-语言预训练模型作为教师网络，通过知识蒸馏将跨模态语义信息注入纯文本模型。',
      score: 76,
      scores: { novelty: 91, feasibility: 72, scientific_value: 78, clarity: 75, testability: 70 },
    },
  ],
  literature_evidence: [
    {
      id: 'le-1',
      title: 'Deep Learning for Natural Language Processing',
      author: 'Zhang et al.',
      year: '2023',
      content: '迁移学习在小样本学习中取得了显著进展，但跨域泛化仍是重要挑战。',
      source_type: 'citation',
      relevance: 92,
    },
    {
      id: 'le-2',
      title: 'Attention Is All You Need',
      author: 'Vaswani et al.',
      year: '2017',
      content: '注意力机制彻底改变了序列建模，但计算复杂度较高。',
      source_type: 'quote',
      relevance: 88,
    },
    {
      id: 'le-3',
      title: 'Self-Supervised Learning Survey',
      author: 'Chen et al.',
      year: '2022',
      content: '对比学习是自监督学习中最有效的方法之一。',
      source_type: 'concept',
      relevance: 85,
    },
  ],
  experiment_design: [
    {
      id: 'e1', step: 1, name: '基准模型训练',
      description: '使用标准预训练模型在目标数据集上训练，建立性能基准。',
      expected_result: '达到现有文献中的基准性能',
      success_criteria: '准确率在 ±5% 范围内',
    },
    {
      id: 'e2', step: 2, name: '特征空间分析',
      description: '分析不同层的特征表示，识别关键信息区域。',
      expected_result: '识别出任务相关的特征空间分布',
      success_criteria: '可视化结果支持假设',
    },
    {
      id: 'e3', step: 3, name: '改进方案实现',
      description: '实现提出的优化方法，进行对比实验。',
      expected_result: '性能显著优于基准方法',
      success_criteria: '准确率提升 ≥ 5%',
    },
    {
      id: 'e4', step: 4, name: '消融实验验证',
      description: '验证各个组件的有效性。',
      expected_result: '完整模型优于任一单独组件',
      success_criteria: '每一个组件贡献 ≥ 2% 性能提升',
    },
  ],
};