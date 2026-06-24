/**
 * Blueprint design tokens — 与 Pencil 设计稿 `designs/aisci-ui.pen` 同步。
 * Tailwind/PostCSS 单源: `frontend/tailwind.blueprint.js`
 * @see designs/aisci-ui-spec.md §2
 */

import { bpColors, blueprintThemeExtend } from '../../tailwind.blueprint.js';

/** Pencil 变量名 → 色值（与 .pen 文件 variables 一致） */
export const pencilVariables = {
  'bp-bg': bpColors.base,
  'bp-panel': bpColors.panel,
  'bp-surface': bpColors.surface,
  'bp-text': bpColors.text,
  'bp-muted': bpColors.muted,
  'bp-cyan': bpColors.cyan.DEFAULT,
  'bp-cyan-dim': bpColors.cyan.dim,
  'bp-green': bpColors.green,
  'bp-yellow': bpColors.yellow,
  'bp-purple': bpColors.purple,
  'bg-blueprint': bpColors.base,
  'bg-primary': bpColors.panel,
  'bg-card': bpColors.surface,
  'border-default': bpColors.border,
  'text-primary': '#F8FAFC',
  'text-secondary': '#94A3B8',
  'accent-sky': '#0EA5E9',
  'accent-sky-light': bpColors.cyan.DEFAULT,
  'accent-green': bpColors.green,
  'accent-purple': bpColors.purple,
} as const;

export const blueprintColors = blueprintThemeExtend.colors;

export const blueprintCssVariables: Record<string, string> = {
  '--bp-bg': bpColors.base,
  '--bp-panel': bpColors.panel,
  '--bp-surface': bpColors.surface,
  '--bp-text': bpColors.text,
  '--bp-muted': bpColors.muted,
  '--bp-cyan': bpColors.cyan.DEFAULT,
  '--bp-cyan-dim': bpColors.cyan.dim,
  '--bp-green': bpColors.green,
  '--bp-yellow': bpColors.yellow,
  '--bp-purple': bpColors.purple,
  '--bp-border': bpColors.border,
  '--bp-panel-glass': bpColors['panel-glass'],
  '--bp-cyan-tint': bpColors['cyan-tint'],
  '--text-primary': pencilVariables['text-primary'],
  '--text-secondary': pencilVariables['text-secondary'],
};

export const blueprintTheme = blueprintThemeExtend;
