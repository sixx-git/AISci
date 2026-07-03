/**
 * Blueprint tokens for Tailwind/PostCSS (plain JS — dev server 可稳定加载).
 * 与 designs/aisci-ui.pen Pencil 变量同步；TS 侧见 src/config/designTokens.ts
 */

/** @type {const} */
export const bpColors = {
  base: '#0A1628',
  panel: '#0F172A',
  surface: '#1E293B',
  text: '#F1F5F9',
  muted: '#94A3B8',
  cyan: {
    DEFAULT: '#38BDF8',
    dim: '#38BDF866',
  },
  green: '#22C55E',
  yellow: '#FACC15',
  purple: '#A855F7',
  border: '#334155',
  'panel-glass': '#0F172A99',
  'cyan-tint': '#38BDF822',
};

/** @type {import('tailwindcss').Config['theme']} */
export const blueprintThemeExtend = {
  colors: {
    bp: bpColors,
  },
  fontFamily: {
    bp: ['JetBrains Mono', 'ui-monospace', 'monospace'],
  },
  fontSize: {
    'bp-annot': ['12px', { lineHeight: '1.5' }],
    'bp-body': ['13px', { lineHeight: '1.55' }],
    'bp-heading': ['36px', { lineHeight: '1.2', fontWeight: '700' }],
    'bp-metric': ['22px', { lineHeight: '1', fontWeight: '700' }],
  },
  borderRadius: {
    bp: '2px',
  },
  spacing: {
    'bp-panel': '14px',
  },
  boxShadow: {
    'bp-glow': '0 0 20px rgba(56, 189, 248, 0.08)',
    'bp-glow-strong': '0 0 20px rgba(56, 189, 248, 0.2)',
  },
};
