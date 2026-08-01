import type { ReactNode } from 'react';
import { Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { loopConfigKey } from '@/lib/storageKeys';
import type { AdversarialMode, IterationMode } from '@/types';

export interface LoopConfigState {
  /** 仅支持人工主导；读取旧配置时会强制归一为 human */
  iterationMode: IterationMode;
  enableHitl: boolean;
  numIdeas: number;
  literatureMaxPapers: number;
  enableProConAdversarial: boolean;
  adversarialMode: AdversarialMode;
  conChallengeMaxRounds: number;
  evidenceReasoningMaxRounds: number;
  enableGapSearch: boolean;
}

export const DEFAULT_LOOP_CONFIG: LoopConfigState = {
  iterationMode: 'human',
  enableHitl: false,
  numIdeas: 3,
  literatureMaxPapers: 10,
  enableProConAdversarial: false,
  adversarialMode: 'off',
  conChallengeMaxRounds: 2,
  evidenceReasoningMaxRounds: 1,
  enableGapSearch: false,
};

const VALID_ADVERSARIAL_MODES = new Set<AdversarialMode>(['off', 'single_group', 'multi_group']);

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(n)));
}

/** 校验并合并本地存储 / 外部传入的 Loop 配置（强制人工主导）。 */
export function normalizeLoopConfig(raw: unknown): LoopConfigState {
  const src = raw && typeof raw === 'object' ? (raw as Partial<LoopConfigState> & Record<string, unknown>) : {};
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
    iterationMode: 'human',
    enableHitl: typeof src.enableHitl === 'boolean' ? src.enableHitl : DEFAULT_LOOP_CONFIG.enableHitl,
    numIdeas: clampInt(src.numIdeas, 1, 8, DEFAULT_LOOP_CONFIG.numIdeas),
    literatureMaxPapers: clampInt(src.literatureMaxPapers, 5, 30, DEFAULT_LOOP_CONFIG.literatureMaxPapers),
    enableProConAdversarial,
    adversarialMode,
    conChallengeMaxRounds: clampInt(
      src.conChallengeMaxRounds,
      1,
      4,
      DEFAULT_LOOP_CONFIG.conChallengeMaxRounds,
    ),
    evidenceReasoningMaxRounds: clampInt(
      src.evidenceReasoningMaxRounds,
      1,
      5,
      DEFAULT_LOOP_CONFIG.evidenceReasoningMaxRounds,
    ),
    enableGapSearch:
      typeof src.enableGapSearch === 'boolean' ? src.enableGapSearch : DEFAULT_LOOP_CONFIG.enableGapSearch,
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
    iteration_mode: 'human',
    num_ideas: normalized.numIdeas,
    literature_max_papers: normalized.literatureMaxPapers,
    // 假设生成门控可选；可行性评估后由后端强制 handoff，不再经此开关自动跑迭代实验/报告
    enable_hitl_gate: false,
    enable_pro_con_adversarial: normalized.enableProConAdversarial,
    adversarial_mode: normalized.adversarialMode,
    con_challenge_max_rounds: normalized.conChallengeMaxRounds,
    enable_science_iteration_observe: true,
    pause_after_hypothesis_review: true,
    enable_teaching_auto_refinement: false,
    evidence_reasoning_max_rounds: normalized.evidenceReasoningMaxRounds,
    enable_gap_search: normalized.enableGapSearch,
  };
}

export const ITERATION_MODE_HINTS: Record<'human', string> = {
  human:
    '人工主导：可行性评估后自动暂停；请在「迭代实验」页完成实验设计与沙箱验证，并手动生成报告。',
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
  const patch = (partial: Partial<LoopConfigState>) => onChange(normalizeLoopConfig({ ...value, ...partial }));

  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-panel/30', compact ? 'p-2' : 'p-3')}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1.5 text-xs text-bp-muted font-medium">
          <Settings2 className="w-3.5 h-3.5 text-bp-cyan" />
          运行配置
        </span>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-bp-green/15 text-bp-green border border-bp-green/30">
          人工主导
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-3">
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

        <Field label="证据链迭代轮数">
          <input
            type="number"
            min={1}
            max={5}
            value={value.evidenceReasoningMaxRounds}
            onChange={(e) =>
              patch({ evidenceReasoningMaxRounds: Math.max(1, Math.min(5, Number(e.target.value) || 1)) })
            }
            disabled={disabled}
            className="input-field py-1.5 px-2 text-sm w-16"
          />
        </Field>

        <label className="flex items-center gap-2 text-xs text-bp-muted cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={value.enableGapSearch}
            onChange={(e) => patch({ enableGapSearch: e.target.checked })}
            disabled={disabled}
            className="rounded border-bp-border"
          />
          Gap 补搜
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
