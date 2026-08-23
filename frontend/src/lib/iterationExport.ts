import env from '@/config/env';
import type { IterativeExperiment, IterationChart, IterationRecordMock } from '@/types/iterativeExperiment';

export interface ChartDownloadRef {
  experimentId: string;
  experimentTitle: string;
  iteration: number;
  name: string;
  /** 传给图表 API 的相对路径，如 smoke/xxx.png */
  path: string;
}

/** 对齐 IterationTimeline 的图表地址解析 */
export function iterationChartHref(chart: { url?: string; path?: string; name?: string }): string {
  if (chart.url?.startsWith('http')) return chart.url;
  if (chart.url?.startsWith('/')) {
    const base = (env.API_BASE_URL || '').replace(/\/$/, '');
    return base ? `${base}${chart.url}` : chart.url;
  }
  const rel = (chart.path || chart.name || '').replace(/^\/+/, '');
  const path = `/api/v1/iterative-experiments/charts/${rel}`;
  const base = (env.API_BASE_URL || '').replace(/\/$/, '');
  return base ? `${base}${path}` : path;
}

export function chartApiRelPath(chart: { url?: string; path?: string; name?: string }): string {
  if (chart.path) return chart.path.replace(/^\/+/, '');
  if (chart.url) {
    const marker = '/iterative-experiments/charts/';
    const idx = chart.url.indexOf(marker);
    if (idx >= 0) return chart.url.slice(idx + marker.length).replace(/^\/+/, '');
    if (!chart.url.startsWith('http') && !chart.url.startsWith('/')) return chart.url.replace(/^\/+/, '');
  }
  return (chart.name || '').replace(/^\/+/, '');
}

export function resolveIterationCharts(it: IterationRecordMock): IterationChart[] {
  const fromResult = it.result?.charts || [];
  if (fromResult.length > 0) return fromResult;
  const notes = it.analysis?.visualization_notes || [];
  return notes
    .map((n) => {
      const name = (n.chart_name || '').trim();
      if (!name) return null;
      const file = name.replace(/^.*[\\/]/, '');
      const rel = `smoke/${file}`;
      return {
        name: file,
        path: rel,
        note: n.description || '',
        url: `/api/v1/iterative-experiments/charts/${rel}`,
      };
    })
    .filter(Boolean) as IterationChart[];
}

export function collectChartRefs(experiments: IterativeExperiment[]): ChartDownloadRef[] {
  const refs: ChartDownloadRef[] = [];
  const seen = new Set<string>();
  for (const exp of experiments) {
    for (const it of exp.iterations || []) {
      for (const chart of resolveIterationCharts(it)) {
        const path = chartApiRelPath(chart);
        if (!path) continue;
        const key = `${exp.id}:${it.iteration_number}:${path}`;
        if (seen.has(key)) continue;
        seen.add(key);
        refs.push({
          experimentId: exp.id,
          experimentTitle: exp.title || exp.hypothesis || exp.id,
          iteration: it.iteration_number,
          name: chart.name || path.replace(/^.*[\\/]/, ''),
          path,
        });
      }
    }
  }
  return refs;
}

export function safeDownloadName(name: string): string {
  return name.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80) || 'chart';
}

export function buildIterationHistoryExport(experiments: IterativeExperiment[]) {
  const charts = collectChartRefs(experiments);
  return {
    generated_at: new Date().toISOString(),
    experiment_count: experiments.length,
    iteration_count: experiments.reduce((n, e) => n + (e.iterations?.length || 0), 0),
    chart_count: charts.length,
    chart_download_paths: charts.map((c) => ({
      experiment_id: c.experimentId,
      iteration: c.iteration,
      name: c.name,
      path: c.path,
      url: iterationChartHref({ path: c.path, name: c.name }),
    })),
    experiments: experiments.map((exp) => ({
      id: exp.id,
      title: exp.title,
      research_goal: exp.research_goal,
      hypothesis: exp.hypothesis,
      constraints: exp.constraints,
      status: exp.status,
      phase: exp.phase,
      run_mode: exp.run_mode,
      data_config: exp.data_config,
      initial_plan: exp.initial_plan,
      iterations: (exp.iterations || []).map((it) => ({
        iteration_number: it.iteration_number,
        status: it.status,
        duration_seconds: it.duration_seconds,
        created_at: it.created_at,
        plan: it.plan,
        result: it.result,
        analysis: it.analysis,
        decision: it.decision,
        metrics: it.metrics || it.result?.metrics,
        error_message: it.error_message,
        charts: resolveIterationCharts(it).map((c) => ({
          name: c.name,
          path: chartApiRelPath(c),
          note: c.note,
          url: iterationChartHref(c),
        })),
      })),
    })),
  };
}
