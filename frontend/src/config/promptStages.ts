/** 与 backend STAGE_TEMPLATE_MAP / prompts/*.md 一致的 8 个 Pipeline 阶段 */
export interface PromptStageItem {
  key: string;
  label: string;
  agent: string;
  description: string;
  /** 不提供 Sakana/AISci 范式预设（固定报告模板） */
  presetLocked?: boolean;
}

export const PIPELINE_PROMPT_STAGES: PromptStageItem[] = [
  {
    key: 'problem_understanding',
    label: '问题理解',
    agent: 'ProblemUnderstandingAgent',
    description: '结构化研究问题、领域、关键词与边界',
  },
  {
    key: 'literature_mining',
    label: '文献挖掘',
    agent: 'LiteratureMiningAgent',
    description: '从文献抽取 facts、citation_map、不确定点',
  },
  {
    key: 'knowledge_gap',
    label: '知识缺口',
    agent: 'KnowledgeGapAgent',
    description: '识别缺口、矛盾与研究机会',
  },
  {
    key: 'hypothesis_generation',
    label: '假设生成',
    agent: 'HypothesisGenerationAgent',
    description: '生成带 fact_id / 数据字段引用的候选假设',
  },
  {
    key: 'hypothesis_review',
    label: '假设评估',
    agent: 'HypothesisReviewAgent',
    description: '五维评分、优劣分析与修改建议',
  },
  {
    key: 'experiment_design',
    label: '实验设计',
    agent: 'ExperimentDesignAgent',
    description: '基线、指标、步骤与数据需求',
  },
  {
    key: 'small_validation',
    label: '小样验证',
    agent: 'SmallValidationAgent',
    description: '小样验证方案与沙箱执行',
  },
  {
    key: 'report_generation',
    label: '报告生成',
    agent: 'ReportGenerationAgent',
    description: '12 章研究报告 Markdown / LaTeX',
    presetLocked: true,
  },
];

export const PROMPT_STAGE_KEYS = new Set(PIPELINE_PROMPT_STAGES.map((s) => s.key));
