import { useState, type ReactNode } from 'react';
import { Settings2, FlaskConical } from 'lucide-react';
import { Button } from '@/components/Button';
import { pipelineService } from '@/services/pipelineService';
import { cn } from '@/lib/utils';
import type { PipelineRunMode, QualityTrendEntry, AdversarialMode } from '@/types';

export interface LoopConfigState {
  pipelineMode: PipelineRunMode;
  numIdeas: number;
  discoveryMaxRounds: number;
  minImprovementDelta: number;
  enableTeachingAutoRefinement: boolean;
  enableGapSearch: boolean;
  coverageGapThreshold: number;
  dataSpecGapThreshold: number;
  maxGapRounds: number;
  enablePlotCritique: boolean;
  enableFederatedCampaign: boolean;
  federatedCampaignMax: number;
  sandboxUseDocker: boolean;
  enableProConAdversarial: boolean;
  adversarialMode: AdversarialMode;
  conChallengeMaxRounds: number;
}

export const DEFAULT_LOOP_CONFIG: LoopConfigState = {
  pipelineMode: 'teaching',
  numIdeas: 3,
  discoveryMaxRounds: 3,
  minImprovementDelta: 3,
  enableTeachingAutoRefinement: true,
  enableGapSearch: true,
  coverageGapThreshold: 70,
  dataSpecGapThreshold: 60,
  maxGapRounds: 2,
  enablePlotCritique: true,
  enableFederatedCampaign: true,
  federatedCampaignMax: 2,
  sandboxUseDocker: false,
  enableProConAdversarial: true,
  adversarialMode: 'single_group',
  conChallengeMaxRounds: 2,
};

export function loopConfigToRunOptions(config: LoopConfigState): Record<string, unknown> {
  return {
    pipeline_mode: config.pipelineMode,
    num_ideas: config.numIdeas,
    discovery_max_rounds: config.discoveryMaxRounds,
    min_improvement_delta: config.minImprovementDelta,
    enable_teaching_auto_refinement: config.enableTeachingAutoRefinement,
    enable_gap_search: config.enableGapSearch,
    coverage_gap_threshold: config.coverageGapThreshold,
    data_spec_gap_threshold: config.dataSpecGapThreshold,
    max_gap_rounds: config.maxGapRounds,
    enable_plot_vlm_critique: config.enablePlotCritique,
    enable_federated_campaign_loop: config.enableFederatedCampaign,
    federated_campaign_max: config.federatedCampaignMax,
    sandbox_use_docker: config.sandboxUseDocker,
    enable_hf_auto_import: true,
    enable_hitl_gate: false,
    enable_pro_con_adversarial: config.enableProConAdversarial,
    adversarial_mode: config.adversarialMode,
    con_challenge_max_rounds: config.conChallengeMaxRounds,
  };
}

interface LoopConfigPanelProps {
  value: LoopConfigState;
  onChange: (next: LoopConfigState) => void;
  disabled?: boolean;
  qualityTrend?: QualityTrendEntry[];
  compact?: boolean;
}

export function LoopConfigPanel({
  value,
  onChange,
  disabled = false,
  qualityTrend,
  compact = false,
}: LoopConfigPanelProps) {
  const [dryRunSummary, setDryRunSummary] = useState<string | null>(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);

  const patch = (partial: Partial<LoopConfigState>) => onChange({ ...value, ...partial });

  const handleDryRun = async () => {
    setDryRunLoading(true);
    setDryRunSummary(null);
    try {
      const res = await pipelineService.loopDryRun({
        run_options: loopConfigToRunOptions(value),
        quality_trend: (qualityTrend ?? []) as Array<Record<string, unknown>>,
        round_num: 2,
      });
      if (res.code === 200 && res.data?.summary) {
        setDryRunSummary(res.data.summary);
      } else {
        setDryRunSummary(res.message || 'Dry-run 失败');
      }
    } catch (e: unknown) {
      setDryRunSummary(e instanceof Error ? e.message : 'Dry-run 请求失败');
    } finally {
      setDryRunLoading(false);
    }
  };

  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-panel/30', compact ? 'p-2' : 'p-3')}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 text-xs text-bp-muted font-medium">
          <Settings2 className="w-3.5 h-3.5 text-bp-cyan" />
          Loop 统一配置
        </span>
        <Button
          size="sm"
          variant="secondary"
          icon={<FlaskConical className="w-3.5 h-3.5" />}
          disabled={disabled || dryRunLoading}
          onClick={handleDryRun}
        >
          {dryRunLoading ? '模拟中…' : 'Dry-run 决策'}
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="运行模式">
          <select
            value={value.pipelineMode}
            onChange={(e) => patch({ pipelineMode: e.target.value as PipelineRunMode })}
            disabled={disabled}
            className="input-field py-1.5 px-2 text-sm w-auto"
          >
            <option value="teaching">Teaching — 单轮精化</option>
            <option value="discovery">Discovery — 自动循环</option>
          </select>
        </Field>

        <Field label="num_ideas">
          <input
            type="number"
            min={1}
            max={8}
            value={value.numIdeas}
            onChange={(e) => patch({ numIdeas: Math.max(1, Math.min(8, Number(e.target.value) || 3)) })}
            disabled={disabled}
            className="input-field py-1.5 px-2 text-sm w-16"
          />
        </Field>

        {value.pipelineMode === 'discovery' && (
          <>
            <Field label="最大轮次">
              <input
                type="number"
                min={1}
                max={5}
                value={value.discoveryMaxRounds}
                onChange={(e) => patch({ discoveryMaxRounds: Math.max(1, Math.min(5, Number(e.target.value) || 3)) })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
            <Field label="CQS Δ 阈值">
              <input
                type="number"
                min={0}
                max={20}
                step={0.5}
                value={value.minImprovementDelta}
                onChange={(e) => patch({ minImprovementDelta: Number(e.target.value) || 3 })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
          </>
        )}

        {value.pipelineMode === 'teaching' && (
          <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
            <input
              type="checkbox"
              checked={value.enableTeachingAutoRefinement}
              onChange={(e) => patch({ enableTeachingAutoRefinement: e.target.checked })}
              disabled={disabled}
              className="rounded border-bp-border"
            />
            验证失败自动精化
          </label>
        )}

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.enableGapSearch}
            onChange={(e) => patch({ enableGapSearch: e.target.checked })}
            disabled={disabled}
            className="rounded border-bp-border"
          />
          Gap 自动补搜
        </label>

        {value.enableGapSearch && (
          <>
            <Field label="完备性 %">
              <input
                type="number"
                min={0}
                max={100}
                value={value.coverageGapThreshold}
                onChange={(e) => patch({ coverageGapThreshold: Number(e.target.value) || 70 })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
            <Field label="DataSpec %">
              <input
                type="number"
                min={0}
                max={100}
                value={value.dataSpecGapThreshold}
                onChange={(e) => patch({ dataSpecGapThreshold: Number(e.target.value) || 60 })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
            <Field label="Gap 轮次">
              <input
                type="number"
                min={1}
                max={4}
                value={value.maxGapRounds}
                onChange={(e) => patch({ maxGapRounds: Math.max(1, Math.min(4, Number(e.target.value) || 2)) })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
          </>
        )}

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.enableProConAdversarial}
            onChange={(e) =>
              patch({
                enableProConAdversarial: e.target.checked,
                adversarialMode: e.target.checked ? value.adversarialMode : 'off',
              })
            }
            disabled={disabled}
            className="rounded border-bp-border"
          />
          红蓝对抗（正方/反方）
        </label>

        {value.enableProConAdversarial && (
          <>
            <Field label="对抗模式">
              <select
                value={value.adversarialMode}
                onChange={(e) => patch({ adversarialMode: e.target.value as AdversarialMode })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm min-w-[140px]"
              >
                <option value="single_group">单研究组</option>
                <option value="multi_group">多研究组（组间攻防）</option>
              </select>
            </Field>
            {value.adversarialMode === 'single_group' && (
              <Field label="反方轮次">
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={value.conChallengeMaxRounds}
                  onChange={(e) =>
                    patch({ conChallengeMaxRounds: Math.max(1, Math.min(4, Number(e.target.value) || 2)) })
                  }
                  disabled={disabled}
                  className="input-field py-1.5 px-2 text-sm w-16"
                />
              </Field>
            )}
          </>
        )}

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.enablePlotCritique}
            onChange={(e) => patch({ enablePlotCritique: e.target.checked })}
            disabled={disabled}
            className="rounded border-bp-border"
          />
          VLM 图表评审
        </label>

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.enableFederatedCampaign}
            onChange={(e) => patch({ enableFederatedCampaign: e.target.checked })}
            disabled={disabled}
            className="rounded border-bp-border"
          />
          联邦 Campaign
        </label>

        {value.enableFederatedCampaign && (
          <Field label="Campaign 轮次">
            <input
              type="number"
              min={1}
              max={3}
              value={value.federatedCampaignMax}
              onChange={(e) => patch({ federatedCampaignMax: Math.max(1, Math.min(3, Number(e.target.value) || 2)) })}
              disabled={disabled}
              className="input-field py-1.5 px-2 text-sm w-16"
            />
          </Field>
        )}

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.sandboxUseDocker}
            onChange={(e) => patch({ sandboxUseDocker: e.target.checked })}
            disabled={disabled}
            className="rounded border-bp-border"
          />
          沙箱 Docker
        </label>
      </div>

      {!compact && (
        <div className="w-full text-xs text-bp-muted leading-relaxed border-t border-bp-border pt-3 mt-3">
          <table className="w-full border-collapse">
            <thead>
              <tr className="text-left text-bp-text">
                <th className="pr-3 pb-1 font-medium">模式</th>
                <th className="pr-3 pb-1 font-medium">阶段暂停</th>
                <th className="pr-3 pb-1 font-medium">多轮迭代</th>
                <th className="pb-1 font-medium">典型场景</th>
              </tr>
            </thead>
            <tbody>
              <tr className={value.pipelineMode === 'teaching' ? 'text-bp-cyan' : ''}>
                <td className="pr-3 py-1">Teaching</td>
                <td className="pr-3 py-1">关闭（全自动）</td>
                <td className="pr-3 py-1">最多 1 轮自动精化</td>
                <td className="py-1">研究生仿真、人工把关</td>
              </tr>
              <tr className={value.pipelineMode === 'discovery' ? 'text-bp-cyan' : ''}>
                <td className="pr-3 py-1">Discovery</td>
                <td className="pr-3 py-1">关闭</td>
                <td className="pr-3 py-1">最多 {value.discoveryMaxRounds} 轮（CQS 停滞停止）</td>
                <td className="py-1">Sakana-like 自动探索</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {dryRunSummary && (
        <p className="mt-2 text-xs text-bp-cyan border-t border-bp-border pt-2">
          Dry-run：{dryRunSummary}
        </p>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="text-xs text-bp-muted block mb-1">{label}</label>
      {children}
    </div>
  );
}
