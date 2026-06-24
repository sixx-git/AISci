export const bpColors: {
  base: string;
  panel: string;
  surface: string;
  text: string;
  muted: string;
  cyan: { DEFAULT: string; dim: string };
  green: string;
  yellow: string;
  purple: string;
  border: string;
  'panel-glass': string;
  'cyan-tint': string;
};

export const blueprintThemeExtend: {
  colors: { bp: typeof bpColors };
  fontFamily: { bp: string[] };
  fontSize: Record<string, string | [string, { lineHeight?: string; fontWeight?: string }]>;
  borderRadius: { bp: string };
  spacing: { 'bp-panel': string };
  boxShadow: { 'bp-glow': string; 'bp-glow-strong': string };
};
