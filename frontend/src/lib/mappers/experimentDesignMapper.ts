import type { BackendExperimentDesign } from '@/services/experimentService';
import type {
  DetailedExperimentDesign,
  ExperimentBaseline,
  ExperimentMetric,
  ExperimentStep,
} from '@/types';
import { safeParseJson } from '@/lib/json';

const categoryLabel: Record<string, string> = {
  traditional: '传统方法',
  deep: '深度方法',
  sota: 'SOTA',
};

const categoryColor: Record<string, string> = {
  traditional: 'bg-bp-panel text-bp-muted border-bp-border',
  deep: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30',
  sota: 'bg-bp-purple/15 text-bp-purple border-bp-purple/30',
};

function parseBaselines(raw: string): ExperimentBaseline[] {
  const fallback: ExperimentBaseline[] = raw
    ? [{ name: '基线方法', description: raw, category: 'traditional' as const }]
    : [];
  return safeParseJson<ExperimentBaseline[]>(raw, fallback);
}

function parseMetrics(raw: string): ExperimentMetric[] {
  const fallback: ExperimentMetric[] = raw
    ? [{ name: '评估指标', description: raw, target: '待定' }]
    : [];
  return safeParseJson<ExperimentMetric[]>(raw, fallback);
}

function parseSteps(raw: string): ExperimentStep[] {
  const fallback: ExperimentStep[] = raw
    ? [{ step: 1, title: '实验步骤', description: raw, expected: '待验证' }]
    : [];
  return safeParseJson<ExperimentStep[]>(raw, fallback);
}

function parseLimitations(raw: string): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    if (typeof parsed === 'string') return [parsed];
    return [String(parsed)];
  } catch {
    return raw.split('\n').filter((l) => l.trim());
  }
}

function extractDatasetName(text: string, fallback: string): string {
  if (!text) return fallback;
  const firstLine = text.split('\n')[0]?.trim();
  if (firstLine && firstLine.length <= 80) return firstLine;
  return firstLine?.slice(0, 80) + '…' || fallback;
}

export function mapBackendExperimentDesignToDetailed(d: BackendExperimentDesign): DetailedExperimentDesign {
  return {
    id: d.id,
    hypothesisTitle: d.hypothesis || '未知假设',
    objective: d.hypothesis
      ? `验证假设：${d.hypothesis.slice(0, 200)}${d.hypothesis.length > 200 ? '...' : ''}`
      : d.methods || '暂无实验目标',
    methods: d.methods || '',
    sourceDataset: extractDatasetName(d.source_data, '源数据集'),
    sourceDescription: d.source_data || '',
    targetDataset: extractDatasetName(d.target_data, '目标数据集'),
    targetDescription: d.target_data || '',
    baselines: parseBaselines(d.baselines),
    metrics: parseMetrics(d.metrics),
    steps: parseSteps(d.experimental_steps),
    expectedResults: d.expected_results || '',
    limitations: parseLimitations(d.limitations),
  };
}

export { categoryLabel, categoryColor };
