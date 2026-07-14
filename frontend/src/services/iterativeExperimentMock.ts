import type {
  DataConfig,
  DatasetRecommendation,
  IterativeExperiment,
  IterativeExperimentStore,
  IterationRecordMock,
  RunMode,
} from '@/types/iterativeExperiment';
import { iterativeExperimentsKey } from '@/lib/storageKeys';

function nowIso() {
  return new Date().toISOString();
}

function newId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `ie_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function emptyStore(): IterativeExperimentStore {
  return { experiments: [], reportExperimentIds: [] };
}

function loadStore(projectId: string): IterativeExperimentStore {
  try {
    const raw = localStorage.getItem(iterativeExperimentsKey(projectId));
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as IterativeExperimentStore;
    return {
      experiments: Array.isArray(parsed.experiments) ? parsed.experiments : [],
      reportExperimentIds: Array.isArray(parsed.reportExperimentIds)
        ? parsed.reportExperimentIds
        : [],
    };
  } catch {
    return emptyStore();
  }
}

function saveStore(projectId: string, store: IterativeExperimentStore) {
  localStorage.setItem(iterativeExperimentsKey(projectId), JSON.stringify(store));
}

function getOrThrow(projectId: string, experimentId: string): {
  store: IterativeExperimentStore;
  experiment: IterativeExperiment;
  index: number;
} {
  const store = loadStore(projectId);
  const index = store.experiments.findIndex((e) => e.id === experimentId);
  if (index < 0) throw new Error('实验不存在');
  return { store, experiment: store.experiments[index], index };
}

function persist(
  projectId: string,
  store: IterativeExperimentStore,
  experiment: IterativeExperiment,
  index: number,
) {
  experiment.updated_at = nowIso();
  store.experiments[index] = experiment;
  saveStore(projectId, store);
  return experiment;
}

function mockRecommendations(hypothesis: string): DatasetRecommendation[] {
  const hint = hypothesis.slice(0, 40) || '当前假设';
  return [
    {
      name: 'Task Benchmark CSV',
      description: '与假设任务对齐的公开基准表结构数据（mock）',
      reason: `用于验证「${hint}」的主指标与基线对比`,
      download_url: 'https://example.com/datasets/task-benchmark',
      expected_columns: ['id', 'feature_1', 'feature_2', 'label'],
      size_hint: '~5k 行',
      file_format: 'csv',
      is_required: true,
    },
    {
      name: 'Domain Sensor / HAR Style',
      description: '目录型多模态示例（SisFall / UCI_HAR 风格，mock）',
      reason: '若假设涉及传感器或行为序列，可作为补充数据',
      download_url: 'https://example.com/datasets/har-style',
      expected_columns: ['subject_id', 'timestamp', 'acc_x', 'acc_y', 'acc_z', 'activity'],
      size_hint: '目录 ~100MB',
      file_format: 'directory',
      is_required: true,
    },
    {
      name: 'Optional Ablation Split',
      description: '可选消融划分表',
      reason: '用于补充对照实验划分子集',
      file_format: 'csv',
      is_required: false,
    },
  ];
}

function mockScript(hypothesis: string, data: DataConfig): NonNullable<IterativeExperiment['initial_plan']> {
  const cols = data.columns?.length ? data.columns.join(', ') : 'feature_*, label';
  return {
    title: '假设验证分析脚本（mock）',
    description: `针对假设生成的可执行分析方案（前端 mock，接通后端后将由 shaxiang ScriptDesigner 生成）`,
    methodology:
      '分层采样 → 训练/评估基线与目标方法 → 输出主指标、混淆矩阵与分布对比图；失败时走 IDE 式 smoke 修补循环。',
    analysis_script: [
      '# mock analysis script — will be replaced by shaxiang ScriptDesigner',
      'def run(df, params):',
      `    # hypothesis: ${hypothesis.slice(0, 80).replace(/\n/g, ' ')}`,
      `    # columns: ${cols}`,
      '    metrics = {"accuracy": 0.82, "f1": 0.79, "primary_metric": "accuracy"}',
      '    return {"metrics": metrics, "plots": []}',
      '',
    ].join('\n'),
    script_params: { sample_size: data.sample_size || 5000 },
    success_criteria: ['smoke 试跑产出 metrics', '至少 1 张有效图表', '无行级泄漏的交叉验证'],
  };
}

function mockIteration(
  experiment: IterativeExperiment,
  n: number,
): IterationRecordMock {
  const smoke = experiment.run_mode === 'smoke_only';
  const baseAcc = 0.72 + n * 0.03 + (smoke ? 0 : 0.02);
  const acc = Math.min(0.97, Number(baseAcc.toFixed(3)));
  const f1 = Math.min(0.96, Number((acc - 0.03).toFixed(3)));
  return {
    iteration_number: n,
    status: 'success',
    plan: {
      title: experiment.initial_plan?.title || `迭代方案 #${n}`,
      methodology: experiment.initial_plan?.methodology,
    },
    result: {
      metrics: { accuracy: acc, f1, primary_metric: 'accuracy', run_scope: smoke ? 'smoke' : 'full' },
      charts: [
        { name: `iter_${n}_confusion_matrices.png`, note: '混淆矩阵（mock）' },
        { name: `iter_${n}_performance_comparison.png`, note: '性能对比（mock）' },
      ],
      summary: smoke
        ? `第 ${n} 轮动态小样验收完成（mock）`
        : `第 ${n} 轮全量推演完成（mock）`,
    },
    analysis: {
      summary: `指标表现 ${smoke ? 'smoke' : 'full'}：accuracy=${acc}`,
      strengths: ['脚本通过试跑门禁', '主指标可比较'],
      weaknesses: acc < 0.85 ? ['主指标仍有提升空间', '建议补充人工反馈重写脚本'] : ['分布可能需进一步检查'],
    },
    decision: {
      continue: n < experiment.max_iterations && acc < 0.9,
      reason:
        n >= experiment.max_iterations
          ? '已达最大迭代轮数'
          : acc >= 0.9
            ? '主指标达标，建议结束'
            : '建议继续迭代或根据反馈重设计脚本',
    },
    metrics: {
      accuracy: acc,
      f1,
      primary_metric: 'accuracy',
      run_scope: smoke ? 'smoke' : 'full',
    },
    duration_seconds: smoke ? 2.4 + n * 0.3 : 8.5 + n,
    created_at: nowIso(),
  };
}

export const iterativeExperimentMock = {
  list(projectId: string): IterativeExperiment[] {
    return loadStore(projectId).experiments.slice().sort(
      (a, b) => (a.updated_at < b.updated_at ? 1 : -1),
    );
  },

  get(projectId: string, experimentId: string): IterativeExperiment | null {
    return loadStore(projectId).experiments.find((e) => e.id === experimentId) ?? null;
  },

  getReportExperimentIds(projectId: string): string[] {
    const store = loadStore(projectId);
    const existing = new Set(store.experiments.map((e) => e.id));
    return store.reportExperimentIds.filter((id) => existing.has(id));
  },

  setReportExperimentIds(projectId: string, ids: string[]): string[] {
    const store = loadStore(projectId);
    const existing = new Set(store.experiments.map((e) => e.id));
    store.reportExperimentIds = ids.filter((id) => existing.has(id));
    saveStore(projectId, store);
    return store.reportExperimentIds;
  },

  toggleReportExperiment(projectId: string, experimentId: string): string[] {
    const current = this.getReportExperimentIds(projectId);
    const next = current.includes(experimentId)
      ? current.filter((id) => id !== experimentId)
      : [...current, experimentId];
    return this.setReportExperimentIds(projectId, next);
  },

  create(
    projectId: string,
    input: {
      hypothesis: string;
      research_goal?: string;
      constraints?: string[];
      executor_type: 'sandbox' | 'simulation';
      max_iterations: number;
    },
  ): IterativeExperiment {
    const hypothesis = input.hypothesis.trim();
    if (!hypothesis) throw new Error('请填写实验假设');
    const store = loadStore(projectId);
    const experiment: IterativeExperiment = {
      id: newId(),
      project_id: projectId,
      title: hypothesis.length > 30 ? `${hypothesis.slice(0, 30)}…` : hypothesis,
      research_goal: (input.research_goal || hypothesis).trim(),
      hypothesis,
      constraints: (input.constraints || []).map((c) => c.trim()).filter(Boolean),
      executor_type: input.executor_type,
      max_iterations: Math.max(1, Math.min(20, input.max_iterations || 10)),
      current_iteration: 0,
      phase: 'created',
      status: 'created',
      run_mode: 'smoke_only',
      dataset_recommendations: null,
      data_config: null,
      initial_plan: null,
      human_feedback: null,
      feedback_status: 'none',
      iterations: [],
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    store.experiments.unshift(experiment);
    saveStore(projectId, store);

    if (input.executor_type === 'sandbox') {
      return this.recommendDatasets(projectId, experiment.id);
    }

    // simulation：跳过数据阶段，直接可有初始「方案」
    experiment.phase = 'script_designed';
    experiment.initial_plan = {
      title: '模拟实验方案（mock）',
      description: '数学/仿真类执行器，无需上传真实数据集',
      methodology: '基于参数化仿真生成曲线与对比指标（mock）',
      analysis_script: 'def run(params): return {"metrics": {"score": 0.5}}',
      script_params: {},
      success_criteria: ['完成至少 1 轮仿真'],
    };
    store.experiments[0] = experiment;
    saveStore(projectId, store);
    return experiment;
  },

  delete(projectId: string, experimentId: string): void {
    const store = loadStore(projectId);
    store.experiments = store.experiments.filter((e) => e.id !== experimentId);
    store.reportExperimentIds = store.reportExperimentIds.filter((id) => id !== experimentId);
    saveStore(projectId, store);
  },

  recommendDatasets(projectId: string, experimentId: string, humanFeedback?: string): IterativeExperiment {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    if (experiment.executor_type !== 'sandbox') {
      throw new Error('模拟实验无需推荐数据集');
    }
    const base = mockRecommendations(experiment.hypothesis);
    if (humanFeedback?.trim()) {
      base.unshift({
        name: 'Feedback-tuned Split',
        description: '根据人工反馈追加的推荐数据（mock）',
        reason: `反馈摘要：${humanFeedback.trim().slice(0, 80)}`,
        is_required: false,
        file_format: 'csv',
      });
    }
    experiment.dataset_recommendations = base;
    experiment.phase = 'data_recommended';
    return persist(projectId, store, experiment, index);
  },

  /**
   * 对齐 shaxiang：缺数据不可设计脚本。
   * mock 下校验路径/文件名非空，并写入 data_config。
   */
  verifyAndBindData(projectId: string, experimentId: string, dataConfig: DataConfig): IterativeExperiment {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    if (experiment.executor_type !== 'sandbox') {
      throw new Error('模拟实验无需绑定数据');
    }
    const path = (dataConfig.source_path || dataConfig.file_name || '').trim();
    if (!path) {
      throw new Error('请先上传文件或指定数据路径（对齐 shaxiang：缺数据不可继续）');
    }
    if (dataConfig.source_type === 'directory' && !dataConfig.profile_name) {
      throw new Error('directory 模式需要选择预置 Profile 或完成 AutoDetect 确认');
    }

    experiment.data_config = {
      ...dataConfig,
      source_path: path,
      row_count: dataConfig.row_count ?? 4800,
      columns: dataConfig.columns?.length
        ? dataConfig.columns
        : ['id', 'feature_1', 'feature_2', 'label'],
      sample_size: dataConfig.sample_size ?? 5000,
    };
    experiment.phase = 'data_uploaded';
    return persist(projectId, store, experiment, index);
  },

  designScript(projectId: string, experimentId: string, dataConfig?: DataConfig): IterativeExperiment {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);

    if (experiment.executor_type === 'sandbox') {
      if (dataConfig) {
        this.verifyAndBindData(projectId, experimentId, dataConfig);
        const refreshed = getOrThrow(projectId, experimentId);
        Object.assign(experiment, refreshed.experiment);
        store.experiments[index] = experiment;
      }
      if (!experiment.data_config?.source_path && !experiment.data_config?.file_name) {
        throw new Error('尚未绑定可用数据，已阻断设计脚本（对齐 shaxiang）');
      }
    }

    experiment.initial_plan = mockScript(
      experiment.hypothesis,
      experiment.data_config || { source_type: 'uploaded', source_path: 'simulation' },
    );
    experiment.phase = 'script_designed';
    experiment.status = 'created';
    experiment.feedback_status = experiment.human_feedback ? 'applied' : experiment.feedback_status;
    return persist(projectId, store, experiment, index);
  },

  setRunMode(projectId: string, experimentId: string, runMode: RunMode): IterativeExperiment {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    experiment.run_mode = runMode;
    return persist(projectId, store, experiment, index);
  },

  runIteration(projectId: string, experimentId: string): IterationRecordMock {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    if (!experiment.initial_plan) {
      throw new Error('请先设计分析脚本');
    }
    if (
      experiment.executor_type === 'sandbox'
      && !experiment.data_config?.source_path
      && !experiment.data_config?.file_name
    ) {
      throw new Error('缺数据，不可执行迭代（对齐 shaxiang）');
    }
    if (experiment.current_iteration >= experiment.max_iterations) {
      throw new Error('已达最大迭代轮数');
    }

    const n = experiment.current_iteration + 1;
    const record = mockIteration(experiment, n);
    experiment.iterations.push(record);
    experiment.current_iteration = n;
    experiment.status = 'running';
    experiment.phase = 'running';

    if (!record.decision.continue || n >= experiment.max_iterations) {
      experiment.phase = 'completed';
      experiment.status = 'completed';
    }

    persist(projectId, store, experiment, index);
    return record;
  },

  runToCompletion(projectId: string, experimentId: string): IterativeExperiment {
    let guard = 0;
    while (guard < 30) {
      const exp = this.get(projectId, experimentId);
      if (!exp) throw new Error('实验不存在');
      if (exp.phase === 'completed' || exp.status === 'completed') return exp;
      if (exp.current_iteration >= exp.max_iterations) {
        const { store, experiment, index } = getOrThrow(projectId, experimentId);
        experiment.phase = 'completed';
        experiment.status = 'completed';
        return persist(projectId, store, experiment, index);
      }
      this.runIteration(projectId, experimentId);
      guard += 1;
    }
    const done = this.get(projectId, experimentId);
    if (!done) throw new Error('实验不存在');
    return done;
  },

  submitFeedback(projectId: string, experimentId: string, feedback: string): IterativeExperiment {
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    const text = feedback.trim();
    if (!text) throw new Error('请输入反馈内容');
    experiment.human_feedback = text;
    experiment.feedback_status = 'submitted';
    return persist(projectId, store, experiment, index);
  },

  redesignFromFeedback(projectId: string, experimentId: string, feedback: string): IterativeExperiment {
    this.submitFeedback(projectId, experimentId, feedback);
    const { store, experiment, index } = getOrThrow(projectId, experimentId);
    if (experiment.executor_type === 'sandbox' && !experiment.data_config) {
      throw new Error('缺数据，不可重设计脚本');
    }
    const plan = mockScript(
      experiment.hypothesis,
      experiment.data_config || { source_type: 'uploaded', source_path: 'simulation' },
    );
    plan.title = '基于反馈重设计脚本（mock）';
    plan.description = `反馈已注入：${feedback.trim().slice(0, 120)}`;
    experiment.initial_plan = plan;
    experiment.phase = 'script_designed';
    experiment.feedback_status = 'applied';
    return persist(projectId, store, experiment, index);
  },
};
