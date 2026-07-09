import type { ReactNode } from 'react';
import { Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { PipelineRunMode, AdversarialMode } from '@/types';

export interface LoopConfigState {
  pipelineMode: PipelineRunMode;
  numIdeas: number;
  literatureMaxPapers: number;
  discoveryMaxRounds: number;
  minImprovementDelta: number;
  enableTeachingAutoRefinement: boolean;
  enableGapSearch: boolean;
  coverageGapThreshold: number;
  dataSpecGapThreshold: number;
  maxGapRounds: number;
  enablePlotCritique: boolean;
  enableProConAdversarial: boolean;
  adversarialMode: AdversarialMode;
  conChallengeMaxRounds: number;
}

export const DEFAULT_LOOP_CONFIG: LoopConfigState = {
  pipelineMode: 'teaching',
  numIdeas: 3,
  literatureMaxPapers: 10,
  discoveryMaxRounds: 3,
  minImprovementDelta: 3,
  enableTeachingAutoRefinement: true,
  enableGapSearch: true,
  coverageGapThreshold: 70,
  dataSpecGapThreshold: 60,
  maxGapRounds: 2,
  enablePlotCritique: true,
  enableProConAdversarial: true,
  adversarialMode: 'single_group',
  conChallengeMaxRounds: 2,
};

export function loopConfigToRunOptions(config: LoopConfigState): Record<string, unknown> {
  return {
    pipeline_mode: config.pipelineMode,
    num_ideas: config.numIdeas,
    literature_max_papers: config.literatureMaxPapers,
    discovery_max_rounds: config.discoveryMaxRounds,
    min_improvement_delta: config.minImprovementDelta,
    enable_teaching_auto_refinement: config.enableTeachingAutoRefinement,
    enable_gap_search: config.enableGapSearch,
    coverage_gap_threshold: config.coverageGapThreshold,
    data_spec_gap_threshold: config.dataSpecGapThreshold,
    max_gap_rounds: config.maxGapRounds,
    enable_plot_vlm_critique: config.enablePlotCritique,
    enable_federated_campaign_loop: true,
    federated_campaign_max: 2,
    sandbox_use_docker: false,
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
  compact?: boolean;
}

export function LoopConfigPanel({
  value,
  onChange,
  disabled = false,
  compact = false,
}: LoopConfigPanelProps) {
  const patch = (partial: Partial<LoopConfigState>) => onChange({ ...value, ...partial });

  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-panel/30', compact ? 'p-2' : 'p-3')}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 text-xs text-bp-muted font-medium">
          <Settings2 className="w-3.5 h-3.5 text-bp-cyan" />
          Loop 统一配置
        </span>
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

        <Field label="候选假设数">
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

        <Field label="文献检索篇数">
          <input
            type="number"
            min={5}
            max={30}
            value={value.literatureMaxPapers}
            onChange={(e) =>
              patch({ literatureMaxPapers: Math.max(5, Math.min(30, Number(e.target.value) || 10)) })
            }
            disabled={disabled}
            className="input-field py-1.5 px-2 text-sm w-16"
            title="控制文献挖掘阶段向量检索与外部论文搜索的规模"
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
            验证失败后自动重试
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
            <Field label="文献补搜触发 %">
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
            <Field label="数据集补搜触发 %">
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
            <Field label="补搜最多轮数">
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
          小样验证图表质量检查
        </label>
      </div>
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
