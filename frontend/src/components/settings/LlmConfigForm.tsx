import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Loader2, AlertCircle, Eye, EyeOff, Settings2,
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

interface LlmConfigFormProps {
  onConfigChange?: (config: LlmConfig | null) => void;
  showFooter?: boolean;
  idPrefix?: string;
  className?: string;
}

export function LlmConfigForm({
  onConfigChange,
  showFooter = true,
  idPrefix = 'llm',
  className,
}: LlmConfigFormProps) {
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
        onConfigChange?.(res.data);
      } else {
        setError(res.message || '加载配置失败');
        onConfigChange?.(null);
      }
    } catch (err) {
      setError(getErrorMessage(err, '加载配置失败'));
      onConfigChange?.(null);
    } finally {
      setLoading(false);
    }
  }, [syncFormFromConfig, onConfigChange]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

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
        onConfigChange?.(res.data);
      } else {
        setError(res.message || '保存失败');
      }
    } catch (err) {
      setError(getErrorMessage(err, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const extraModels = useMemo(() => {
    const presetSet = new Set<string>(QWEN_MODEL_PRESETS);
    return (config?.available_models ?? []).filter((m) => !presetSet.has(m));
  }, [config?.available_models]);

  const envKeyHint = config?.env_api_key_configured
    ? '已在 backend/.env 中配置'
    : '未在 .env 中配置 QWEN_API_KEY';

  if (loading && !config) {
    return (
      <div className={cn('flex items-center justify-center py-10 text-bp-muted text-sm gap-2', className)}>
        <Loader2 className="w-5 h-5 animate-spin text-bp-cyan" />
        加载配置中…
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div>
        <p className="text-xs text-bp-muted mb-1.5">API Key 来源</p>
        <div className="grid grid-cols-2 gap-1.5 p-0.5 rounded-bp bg-bp-base border border-bp-border">
          <button
            type="button"
            onClick={() => setUseEnvApiKey(true)}
            className={cn(
              'text-xs py-1.5 px-2 rounded-md transition-colors',
              useEnvApiKey
                ? 'bg-bp-cyan-tint text-bp-cyan font-medium'
                : 'text-bp-muted hover:text-bp-text',
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
                ? 'bg-bp-cyan-tint text-bp-cyan font-medium'
                : 'text-bp-muted hover:text-bp-text',
            )}
          >
            自定义密钥
          </button>
        </div>

        {useEnvApiKey ? (
          <div className={cn(
            'mt-2 text-xs px-2.5 py-2 rounded-bp border',
            config?.env_api_key_configured
              ? 'border-bp-green/25 bg-bp-green/10 text-bp-green'
              : 'border-bp-yellow/25 bg-bp-yellow/10 text-bp-yellow',
          )}>
            <p>{envKeyHint}</p>
            {config?.env_api_key_configured && config.api_key_source === 'env' && config.api_key_masked && (
              <p className="mt-1 font-mono text-[11px] text-bp-green/80">{config.api_key_masked}</p>
            )}
          </div>
        ) : (
          <div className="mt-2 space-y-1.5">
            {config?.custom_api_key_configured && config.api_key_source === 'custom' && !apiKeyInput && (
              <p className="text-[11px] text-bp-muted">
                当前密钥：<span className="font-mono text-bp-text">{config.api_key_masked}</span>
                <span className="text-bp-muted/70"> · 留空则保持不变</span>
              </p>
            )}
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="输入 DashScope API Key（sk-...）"
                className="input-field py-2 pr-9 text-sm"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-bp-muted hover:text-bp-text"
                aria-label={showKey ? '隐藏密钥' : '显示密钥'}
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        <div className={cn(
          'mt-2 flex items-center gap-2 text-[11px] px-2 py-1 rounded-bp border',
          keyConfigured
            ? 'border-bp-green/20 text-bp-green/90'
            : 'border-bp-yellow/20 text-bp-yellow/90',
        )}>
          <span className={cn(
            'w-1.5 h-1.5 rounded-full shrink-0',
            keyConfigured ? 'bg-bp-green' : 'bg-bp-yellow',
          )} />
          {keyConfigured ? '当前生效密钥已配置' : '当前无可用 API Key'}
        </div>
      </div>

      <div>
        <label className="text-xs text-bp-muted block mb-1" htmlFor={`${idPrefix}-qwen-model`}>
          Qwen 模型
        </label>
        <select
          id={`${idPrefix}-qwen-model`}
          value={modelSelect}
          onChange={(e) => setModelSelect(e.target.value)}
          className="input-field py-2 text-sm"
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
            className="mt-1.5 input-field py-2 text-sm"
          />
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowAdvanced((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-bp-muted hover:text-bp-text"
      >
        <Settings2 className="w-3.5 h-3.5" />
        {showAdvanced ? '收起高级设置' : '高级设置'}
      </button>
      {showAdvanced && (
        <div className="space-y-3 pl-1 border-l border-bp-border/60 ml-1">
          <div>
            <label className="text-xs text-bp-muted block mb-1" htmlFor={`${idPrefix}-base-url`}>
              API Base URL
            </label>
            <input
              id={`${idPrefix}-base-url`}
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={config?.env_base_url || 'https://dashscope.aliyuncs.com/compatible-mode/v1'}
              className="input-field py-2 text-sm"
            />
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs text-danger-400 flex items-start gap-1">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          {error}
        </p>
      )}

      {showFooter && (
        <Button
          size="sm"
          className="w-full sm:w-auto"
          onClick={handleSave}
          isLoading={saving}
          disabled={loading}
        >
          保存配置
        </Button>
      )}
    </div>
  );
}
