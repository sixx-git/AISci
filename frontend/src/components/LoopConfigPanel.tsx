import type { ReactNode } from 'react';
import { Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AdversarialMode, IterationMode } from '@/types';

export interface LoopConfigState {
  iterationMode: IterationMode;
  enableHitl: boolean;
  numIdeas: number;
  literatureMaxPapers: number;
  maxRounds: number;
  gateStagnantRounds: number;
  enableProConAdversarial: boolean;
  adversarialMode: AdversarialMode;
  conChallengeMaxRounds: number;
}

export const DEFAULT_LOOP_CONFIG: LoopConfigState = {
  iterationMode: 'human',
  enableHitl: false,
  numIdeas: 3,
  literatureMaxPapers: 10,
  maxRounds: 3,
  gateStagnantRounds: 2,
  enableProConAdversarial: true,
  adversarialMode: 'single_group',
  conChallengeMaxRounds: 2,
};

export function loopConfigToRunOptions(config: LoopConfigState): Record<string, unknown> {
  return {
    iteration_mode: config.iterationMode,
    num_ideas: config.numIdeas,
    literature_max_papers: config.literatureMaxPapers,
    discovery_max_rounds: config.maxRounds,
    gate_stagnant_rounds: config.gateStagnantRounds,
    // 假设生成/评估与报告不再走 HITL；人工审在假设页与「迭代实验」页完成
    enable_hitl_gate: false,
    enable_pro_con_adversarial: config.enableProConAdversarial,
    adversarial_mode: config.adversarialMode,
    con_challenge_max_rounds: config.conChallengeMaxRounds,
    enable_science_iteration_observe: true,
  };
}

export const ITERATION_MODE_HINTS: Record<IterationMode, string> = {
  human:
    '人工主导：在「候选假设」与「迭代实验」页审阅；支持阶段修订与单阶段重跑，无关键阶段 HITL 门控。',
  teaching_auto:
    '轻量自动：验证或图表检查失败时自动精化（旧实验环已退役；请以「迭代实验」页反馈重设计为主）。',
  discovery_auto:
    '深度自动：评审未 Accept 时自动刷新文献并重跑假设→迭代实验→报告（最多 N 轮）。',
};

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
          迭代模式
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="宏闭环模式">
          <select
            value={value.iterationMode}
            onChange={(e) => patch({ iterationMode: e.target.value as IterationMode })}
            disabled={disabled}
            className="input-field py-1.5 px-2 text-sm min-w-[180px]"
          >
            <option value="human">人工主导（推荐）</option>
            <option value="teaching_auto">轻量自动精化</option>
            <option value="discovery_auto">深度 Discovery 循环</option>
          </select>
        </Field>

        {value.iterationMode === 'discovery_auto' && (
          <>
            <Field label="最大轮次">
              <input
                type="number"
                min={1}
                max={5}
                value={value.maxRounds}
                onChange={(e) => patch({ maxRounds: Math.max(1, Math.min(5, Number(e.target.value) || 3)) })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
            <Field label="Gate 停滞轮次">
              <input
                type="number"
                min={1}
                max={4}
                value={value.gateStagnantRounds}
                onChange={(e) => patch({ gateStagnantRounds: Math.max(1, Math.min(4, Number(e.target.value) || 2)) })}
                disabled={disabled}
                className="input-field py-1.5 px-2 text-sm w-16"
              />
            </Field>
          </>
        )}

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
          />
        </Field>

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
          红蓝对抗审核
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
                <option value="single_group">单研究组（正方/反方）</option>
                <option value="multi_group">多研究组（组间攻防）</option>
              </select>
            </Field>
            {value.adversarialMode === 'single_group' && (
              <Field label="反方挑战轮次">
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
