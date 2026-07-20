import type { ReactNode } from 'react';
import { Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { loopConfigKey } from '@/lib/storageKeys';
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
  enableProConAdversarial: false,
  adversarialMode: 'off',
  conChallengeMaxRounds: 2,
};

const VALID_ITERATION_MODES = new Set<IterationMode>(['human', 'teaching_auto', 'discovery_auto']);
const VALID_ADVERSARIAL_MODES = new Set<AdversarialMode>(['off', 'single_group', 'multi_group']);

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(n)));
}

/** 校验并合并本地存储 / 外部传入的 Loop 配置。 */
export function normalizeLoopConfig(raw: unknown): LoopConfigState {
  const src = raw && typeof raw === 'object' ? (raw as Partial<LoopConfigState>) : {};
  const iterationMode = VALID_ITERATION_MODES.has(src.iterationMode as IterationMode)
    ? (src.iterationMode as IterationMode)
    : DEFAULT_LOOP_CONFIG.iterationMode;
  const enableProConAdversarial =
    typeof src.enableProConAdversarial === 'boolean'
      ? src.enableProConAdversarial
      : DEFAULT_LOOP_CONFIG.enableProConAdversarial;
  let adversarialMode = VALID_ADVERSARIAL_MODES.has(src.adversarialMode as AdversarialMode)
    ? (src.adversarialMode as AdversarialMode)
    : DEFAULT_LOOP_CONFIG.adversarialMode;
  if (!enableProConAdversarial) {
    adversarialMode = 'off';
  } else if (adversarialMode === 'off') {
    adversarialMode = 'single_group';
  }
  return {
    iterationMode,
    enableHitl: typeof src.enableHitl === 'boolean' ? src.enableHitl : DEFAULT_LOOP_CONFIG.enableHitl,
    numIdeas: clampInt(src.numIdeas, 1, 8, DEFAULT_LOOP_CONFIG.numIdeas),
    literatureMaxPapers: clampInt(src.literatureMaxPapers, 5, 30, DEFAULT_LOOP_CONFIG.literatureMaxPapers),
    maxRounds: clampInt(src.maxRounds, 1, 5, DEFAULT_LOOP_CONFIG.maxRounds),
    gateStagnantRounds: clampInt(src.gateStagnantRounds, 1, 4, DEFAULT_LOOP_CONFIG.gateStagnantRounds),
    enableProConAdversarial,
    adversarialMode,
    conChallengeMaxRounds: clampInt(
      src.conChallengeMaxRounds,
      1,
      4,
      DEFAULT_LOOP_CONFIG.conChallengeMaxRounds,
    ),
  };
}

export function loadLoopConfig(projectId: string | undefined | null): LoopConfigState {
  if (!projectId || typeof window === 'undefined') return { ...DEFAULT_LOOP_CONFIG };
  try {
    const raw = localStorage.getItem(loopConfigKey(projectId));
    if (!raw) return { ...DEFAULT_LOOP_CONFIG };
    return normalizeLoopConfig(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_LOOP_CONFIG };
  }
}

export function saveLoopConfig(projectId: string | undefined | null, config: LoopConfigState): void {
  if (!projectId || typeof window === 'undefined') return;
  try {
    localStorage.setItem(loopConfigKey(projectId), JSON.stringify(normalizeLoopConfig(config)));
  } catch {
    /* ignore quota / private mode */
  }
}

export function loopConfigToRunOptions(config: LoopConfigState): Record<string, unknown> {
  const normalized = normalizeLoopConfig(config);
  return {
    iteration_mode: normalized.iterationMode,
    num_ideas: normalized.numIdeas,
    literature_max_papers: normalized.literatureMaxPapers,
    discovery_max_rounds: normalized.maxRounds,
    gate_stagnant_rounds: normalized.gateStagnantRounds,
    // 假设生成门控可选；可行性评估后由后端强制 handoff，不再经此开关自动跑迭代实验/报告
    enable_hitl_gate: false,
    enable_pro_con_adversarial: normalized.enableProConAdversarial,
    adversarial_mode: normalized.adversarialMode,
    con_challenge_max_rounds: normalized.conChallengeMaxRounds,
    enable_science_iteration_observe: true,
  };
}

export const ITERATION_MODE_HINTS: Record<IterationMode, string> = {
  human:
    '人工主导：可行性评估后自动暂停；请在「迭代实验」页完成实验设计与沙箱验证，并手动生成报告。',
  teaching_auto:
    '轻量自动：验证或图表检查失败时自动精化（旧实验环已退役；请以「迭代实验」页反馈重设计为主）。可行性评估后同样暂停。',
  discovery_auto:
    '深度自动：评审未 Accept 时自动刷新文献并重跑假设→迭代实验→报告（最多 N 轮）；不在可行性评估后暂停。',
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
                adversarialMode: e.target.checked
                  ? value.adversarialMode === 'off'
                    ? 'single_group'
                    : value.adversarialMode
                  : 'off',
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
