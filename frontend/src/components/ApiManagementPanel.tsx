import { useEffect, useRef, useState } from 'react';
import { KeyRound, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LlmConfigForm } from '@/components/settings/LlmConfigForm';
import { QWEN_MODEL_PRESETS } from '@/config/llmModels';
import { llmConfigService, type LlmConfig } from '@/services/llmConfigService';

export function ApiManagementPanel() {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<LlmConfig | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    llmConfigService.getConfig().then((res) => {
      if (res.code === 200 && res.data) setConfig(res.data);
    }).catch(() => {/* badge fallback */});
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const keyConfigured = config?.api_key_configured ?? false;
  const navBadge = keyConfigured
    ? (config?.model || QWEN_MODEL_PRESETS[0])
    : '未配置';

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-bp text-sm font-medium border transition-colors',
          open
            ? 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30'
            : 'text-bp-muted border-transparent hover:text-bp-text hover:bg-bp-surface hover-accent-bottom',
        )}
        title="API 与模型配置"
      >
        <KeyRound className="w-4 h-4 shrink-0" />
        <span className="hidden md:inline">API 管理</span>
        {config && (
          <span className={cn(
            'hidden lg:inline text-xs px-1.5 py-0.5 rounded border max-w-[100px] truncate',
            keyConfigured
              ? 'bg-bp-green/10 text-bp-green border-bp-green/25'
              : 'bg-bp-yellow/10 text-bp-yellow border-bp-yellow/25',
          )}>
            {navBadge}
          </span>
        )}
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[min(100vw-2rem,22rem)] z-[60] rounded-bp border border-bp-border bg-bp-panel shadow-bp-glow-strong">
          <div className="px-4 py-3 border-b border-bp-border/80">
            <h3 className="text-sm font-semibold text-bp-text">API 配置</h3>
            <p className="text-xs text-bp-muted mt-0.5">
              Qwen 全模态模型，文本与视觉共用同一配置
            </p>
          </div>

          <div className="px-4 py-3 max-h-[65vh] overflow-y-auto">
            <LlmConfigForm
              idPrefix="nav-llm"
              onConfigChange={setConfig}
            />
          </div>
        </div>
      )}
    </div>
  );
}
