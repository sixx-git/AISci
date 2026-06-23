import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  KeyRound, ChevronDown, Loader2, AlertCircle, Eye, EyeOff, Settings2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/Button';
import { llmConfigService, type LlmConfig } from '@/services/llmConfigService';
import { getErrorMessage } from '@/lib/errors';
import {
  CUSTOM_MODEL_VALUE,
  QWEN_MODEL_GROUPS,
  QWEN_MODEL_PRESETS,
  formatModelOptionLabel,
} from '@/config/llmModels';

function applyModelFromConfig(c: LlmConfig): { select: string; custom: string } {
  const trimmed = (c.model_override || c.model).trim();
  if (!trimmed) {
    return { select: QWEN_MODEL_PRESETS[0], custom: '' };
  }
  const known = [...QWEN_MODEL_PRESETS, ...(c.available_models ?? [])];
  if (known.includes(trimmed)) {
    return { select: trimmed, custom: '' };
  }
  return { select: CUSTOM_MODEL_VALUE, custom: trimmed };
}

export function ApiManagementPanel() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<LlmConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [useEnvApiKey, setUseEnvApiKey] = useState(true);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [modelSelect, setModelSelect] = useState<string>(QWEN_MODEL_PRESETS[0]);
  const [customModel, setCustomModel] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [baseUrl, setBaseUrl] = useState('');

  const panelRef = useRef<HTMLDivElement>(null);

  const keyConfigured = config?.api_key_configured ?? false;

  const qwenModel = useMemo(
    () => (modelSelect === CUSTOM_MODEL_VALUE ? customModel.trim() : modelSelect),
    [modelSelect, customModel],
  );

  const syncFormFromConfig = useCallback((c: LlmConfig) => {
    setApiKeyInput('');
    setUseEnvApiKey(c.use_env_api_key);
    const { select, custom } = applyModelFromConfig(c);
    setModelSelect(select);
    setCustomModel(custom);
    setBaseUrl(c.base_url);
  }, []);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await llmConfigService.getConfig();
      if (res.code === 200 && res.data) {
        setConfig(res.data);
        syncFormFromConfig(res.data);
      } else {
        setError(res.message || '加载配置失败');
      }
    } catch (err) {
      setError(getErrorMessage(err, '加载配置失败'));
    } finally {
      setLoading(false);
    }
  }, [syncFormFromConfig]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

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

  const handleSave = async () => {
    if (!qwenModel) {
      setError('请选择或输入 Qwen 模型');
      return;
    }

    if (!useEnvApiKey) {
      const hasExistingCustom = config?.custom_api_key_configured && config.api_key_source === 'custom';
      if (!apiKeyInput.trim() && !hasExistingCustom) {
        setError('请输入自定义 API Key');
        return;
      }
    } else if (!config?.env_api_key_configured) {
      setError('当前 .env 未配置 QWEN_API_KEY，请切换到自定义密钥或先在 .env 中配置');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const payload: Parameters<typeof llmConfigService.updateConfig>[0] = {
        model: qwenModel,
        use_env_api_key: useEnvApiKey,
      };

      if (useEnvApiKey) {
        if (config?.api_key_source === 'custom' || config?.custom_api_key_configured) {
          payload.clear_custom_api_key = true;
        }
      } else if (apiKeyInput.trim()) {
        payload.api_key = apiKeyInput.trim();
      }

      if (showAdvanced) {
        payload.base_url = baseUrl || undefined;
      }

      const res = await llmConfigService.updateConfig(payload);
      if (res.code === 200 && res.data) {
        setConfig(res.data);
        syncFormFromConfig(res.data);
        setApiKeyInput('');
      } else {
        setError(res.message || '保存失败');
      }
    } catch (err) {
      setError(getErrorMessage(err, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const navBadge = keyConfigured
    ? (config?.model || QWEN_MODEL_PRESETS[0])
    : '未配置';

  const extraModels = useMemo(() => {
    const presetSet = new Set<string>(QWEN_MODEL_PRESETS);
    return (config?.available_models ?? []).filter((m) => !presetSet.has(m));
  }, [config?.available_models]);

  const envKeyHint = config?.env_api_key_configured
    ? '已在 backend/.env 中配置'
    : '未在 .env 中配置 QWEN_API_KEY';

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-colors',
          open
            ? 'bg-primary-600/20 text-primary-400 border-primary-600/30'
            : 'text-gray-400 border-transparent hover:text-gray-200 hover:bg-dark-700 hover:border-gray-600',
        )}
        title="API 与模型配置"
      >
        <KeyRound className="w-4 h-4 shrink-0" />
        <span className="hidden md:inline">API 管理</span>
        {config && (
          <span className={cn(
            'hidden lg:inline text-[11px] px-1.5 py-0.5 rounded border max-w-[100px] truncate',
            keyConfigured
              ? 'bg-green-500/10 text-green-400 border-green-500/25'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/25',
          )}>
            {navBadge}
          </span>
        )}
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[min(100vw-2rem,22rem)] z-[60] rounded-xl border border-gray-700 bg-dark-800 shadow-2xl shadow-black/40">
          <div className="px-4 py-3 border-b border-gray-700/80">
            <h3 className="text-sm font-semibold text-white">API 配置</h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Qwen 全模态模型，文本与视觉共用同一配置
            </p>
          </div>

          <div className="px-4 py-3 space-y-3 max-h-[65vh] overflow-y-auto">
            {loading && !config ? (
              <div className="flex items-center justify-center py-6 text-gray-500 text-sm gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中…
              </div>
            ) : (
              <>
                <div>
                  <p className="text-xs text-gray-500 mb-1.5">API Key 来源</p>
                  <div className="grid grid-cols-2 gap-1.5 p-0.5 rounded-lg bg-dark-900 border border-gray-700">
                    <button
                      type="button"
                      onClick={() => setUseEnvApiKey(true)}
                      className={cn(
                        'text-xs py-1.5 px-2 rounded-md transition-colors',
                        useEnvApiKey
                          ? 'bg-primary-600/25 text-primary-300 font-medium'
                          : 'text-gray-400 hover:text-gray-200',
                      )}
                    >
                      .env 环境变量
                    </button>
                    <button
                      type="button"
                      onClick={() => setUseEnvApiKey(false)}
                      className={cn(
                        'text-xs py-1.5 px-2 rounded-md transition-colors',
                        !useEnvApiKey
                          ? 'bg-primary-600/25 text-primary-300 font-medium'
                          : 'text-gray-400 hover:text-gray-200',
                      )}
                    >
                      自定义密钥
                    </button>
                  </div>

                  {useEnvApiKey ? (
                    <div className={cn(
                      'mt-2 text-xs px-2.5 py-2 rounded-lg border',
                      config?.env_api_key_configured
                        ? 'border-green-500/25 bg-green-500/10 text-green-400'
                        : 'border-amber-500/25 bg-amber-500/10 text-amber-400',
                    )}>
                      <p>{envKeyHint}</p>
                      {config?.env_api_key_configured && config.api_key_source === 'env' && config.api_key_masked && (
                        <p className="mt-1 font-mono text-[11px] text-green-300/80">{config.api_key_masked}</p>
                      )}
                    </div>
                  ) : (
                    <div className="mt-2 space-y-1.5">
                      {config?.custom_api_key_configured && config.api_key_source === 'custom' && !apiKeyInput && (
                        <p className="text-[11px] text-gray-500">
                          当前密钥：<span className="font-mono text-gray-400">{config.api_key_masked}</span>
                          <span className="text-gray-600"> · 留空则保持不变</span>
                        </p>
                      )}
                      <div className="relative">
                        <input
                          type={showKey ? 'text' : 'password'}
                          value={apiKeyInput}
                          onChange={(e) => setApiKeyInput(e.target.value)}
                          placeholder="输入 DashScope API Key（sk-...）"
                          className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 pr-9 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
                        />
                        <button
                          type="button"
                          onClick={() => setShowKey((v) => !v)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                          aria-label={showKey ? '隐藏密钥' : '显示密钥'}
                        >
                          {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                  )}

                  <div className={cn(
                    'mt-2 flex items-center gap-2 text-[11px] px-2 py-1 rounded border',
                    keyConfigured
                      ? 'border-green-500/20 text-green-400/90'
                      : 'border-amber-500/20 text-amber-400/90',
                  )}>
                    <span className={cn(
                      'w-1.5 h-1.5 rounded-full shrink-0',
                      keyConfigured ? 'bg-green-400' : 'bg-amber-400',
                    )} />
                    {keyConfigured ? '当前生效密钥已配置' : '当前无可用 API Key'}
                  </div>
                </div>

                <div>
                  <label className="text-xs text-gray-500 block mb-1" htmlFor="llm-qwen-model">
                    Qwen 模型
                  </label>
                  <select
                    id="llm-qwen-model"
                    value={modelSelect}
                    onChange={(e) => setModelSelect(e.target.value)}
                    className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-primary-500/50"
                  >
                    {QWEN_MODEL_GROUPS.map((group) => (
                      <optgroup key={group.label} label={group.label}>
                        {group.models.map((m) => (
                          <option key={m.id} value={m.id}>
                            {formatModelOptionLabel(m)}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                    {extraModels.length > 0 && (
                      <optgroup label="其他">
                        {extraModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </optgroup>
                    )}
                    <option value={CUSTOM_MODEL_VALUE}>自定义模型…</option>
                  </select>
                  {modelSelect === CUSTOM_MODEL_VALUE && (
                    <input
                      type="text"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="输入百炼模型 ID，如 qwen3.7-plus"
                      className="mt-1.5 w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
                    />
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300"
                >
                  <Settings2 className="w-3.5 h-3.5" />
                  {showAdvanced ? '收起高级设置' : '高级设置'}
                </button>
                {showAdvanced && (
                  <div className="space-y-3 pl-1 border-l border-gray-700/60 ml-1">
                    <div>
                      <label className="text-xs text-gray-500 block mb-1" htmlFor="llm-base-url">
                        API Base URL
                      </label>
                      <input
                        id="llm-base-url"
                        type="text"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={config?.env_base_url || 'https://dashscope.aliyuncs.com/compatible-mode/v1'}
                        className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
                      />
                    </div>
                  </div>
                )}

                {error && (
                  <p className="text-xs text-red-400 flex items-start gap-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    {error}
                  </p>
                )}
              </>
            )}
          </div>

          <div className="px-4 py-3 border-t border-gray-700/80">
            <Button
              size="sm"
              className="w-full"
              onClick={handleSave}
              isLoading={saving}
              disabled={loading}
            >
              保存
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
