import { useCallback, useEffect, useRef, useState } from 'react';
import {
  KeyRound, ChevronDown, Loader2, CheckCircle2, AlertCircle,
  Sparkles, Eye, EyeOff, RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/Button';
import { llmConfigService, type LlmConfig } from '@/services/llmConfigService';
import { getErrorMessage } from '@/lib/errors';

export function ApiManagementPanel() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [config, setConfig] = useState<LlmConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [useEnvKey, setUseEnvKey] = useState(true);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [model, setModel] = useState('');
  const [customModel, setCustomModel] = useState('');
  const [vlModel, setVlModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [useMock, setUseMock] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);

  const syncFormFromConfig = useCallback((c: LlmConfig) => {
    setUseEnvKey(c.use_env_api_key);
    setApiKeyInput('');
    const activeModel = c.model_override || c.model;
    if (c.available_models.includes(activeModel)) {
      setModel(activeModel);
      setCustomModel('');
    } else {
      setModel('__custom__');
      setCustomModel(activeModel);
    }
    setVlModel(c.vl_model);
    setBaseUrl(c.base_url);
    setUseMock(c.use_mock_llm);
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

  const resolvedModel = model === '__custom__' ? customModel.trim() : model;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setTestMsg(null);
    try {
      const payload: Parameters<typeof llmConfigService.updateConfig>[0] = {
        use_env_api_key: useEnvKey,
        model: resolvedModel || undefined,
        vl_model: vlModel || undefined,
        base_url: baseUrl || undefined,
        use_mock_llm: useMock,
      };
      if (!useEnvKey && apiKeyInput.trim()) {
        payload.api_key = apiKeyInput.trim();
      }
      if (useEnvKey) {
        payload.clear_custom_api_key = true;
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

  const handleTest = async () => {
    setTesting(true);
    setTestMsg(null);
    try {
      const res = await llmConfigService.testConnection();
      if (res.code === 200 && res.data) {
        setTestMsg({
          ok: res.data.ok,
          text: res.data.latency_ms != null
            ? `${res.data.message}（${res.data.latency_ms}ms）`
            : res.data.message,
        });
      } else {
        setTestMsg({ ok: false, text: res.message || '测试失败' });
      }
    } catch (err) {
      setTestMsg({ ok: false, text: getErrorMessage(err, '测试失败') });
    } finally {
      setTesting(false);
    }
  };

  const statusLabel = config?.use_mock_llm
    ? 'Mock'
    : config?.api_key_configured
      ? config.model
      : '未配置';

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
            'hidden lg:inline text-[11px] px-1.5 py-0.5 rounded border max-w-[120px] truncate',
            config.api_key_configured || config.use_mock_llm
              ? 'bg-green-500/10 text-green-400 border-green-500/25'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/25',
          )}>
            {statusLabel}
          </span>
        )}
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[min(100vw-2rem,22rem)] z-[60] rounded-xl border border-gray-700 bg-dark-800 shadow-2xl shadow-black/40">
          <div className="px-4 py-3 border-b border-gray-700/80">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary-400" />
              API 管理
            </h3>
            <p className="text-[11px] text-gray-500 mt-1">
              切换密钥与模型，保存后立即生效（重启服务后恢复 .env）
            </p>
          </div>

          <div className="px-4 py-3 space-y-3 max-h-[70vh] overflow-y-auto">
            {loading && !config ? (
              <div className="flex items-center justify-center py-8 text-gray-500 text-sm gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                加载中…
              </div>
            ) : (
              <>
                {/* Mock 模式 */}
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useMock}
                    onChange={(e) => setUseMock(e.target.checked)}
                    className="rounded border-gray-600 bg-dark-900 text-primary-500"
                  />
                  Mock LLM（无需真实 API Key）
                </label>

                {!useMock && (
                  <>
                    {/* 密钥来源 */}
                    <div>
                      <p className="text-xs text-gray-500 mb-1.5">API 密钥来源</p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setUseEnvKey(true)}
                          className={cn(
                            'flex-1 text-xs py-1.5 rounded-lg border',
                            useEnvKey
                              ? 'border-primary-500/40 bg-primary-500/10 text-primary-300'
                              : 'border-gray-700 text-gray-400 hover:border-gray-600',
                          )}
                        >
                          环境变量 (.env)
                        </button>
                        <button
                          type="button"
                          onClick={() => setUseEnvKey(false)}
                          className={cn(
                            'flex-1 text-xs py-1.5 rounded-lg border',
                            !useEnvKey
                              ? 'border-primary-500/40 bg-primary-500/10 text-primary-300'
                              : 'border-gray-700 text-gray-400 hover:border-gray-600',
                          )}
                        >
                          自定义密钥
                        </button>
                      </div>
                      {useEnvKey && config && (
                        <p className="text-[11px] text-gray-500 mt-1.5">
                          {config.env_api_key_configured
                            ? `已配置：${config.api_key_masked || '****'}`
                            : '未在 .env 中检测到 QWEN_API_KEY'}
                        </p>
                      )}
                    </div>

                    {!useEnvKey && (
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">自定义 API Key</label>
                        <div className="relative">
                          <input
                            type={showKey ? 'text' : 'password'}
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder={config?.custom_api_key_configured ? '留空保留当前密钥' : '输入 DashScope API Key'}
                            className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 pr-9 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
                          />
                          <button
                            type="button"
                            onClick={() => setShowKey((v) => !v)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                          >
                            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                        {config?.custom_api_key_configured && !apiKeyInput && (
                          <p className="text-[11px] text-gray-500 mt-1">当前：{config.api_key_masked}</p>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* 文本模型 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">文本模型</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    disabled={useMock}
                    className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-primary-500/50 disabled:opacity-50"
                  >
                    {(config?.available_models ?? []).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    <option value="__custom__">自定义…</option>
                  </select>
                  {model === '__custom__' && (
                    <input
                      type="text"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="输入模型名称"
                      className="mt-1.5 w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
                    />
                  )}
                </div>

                {/* 视觉模型 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">视觉模型（多模态）</label>
                  <select
                    value={vlModel}
                    onChange={(e) => setVlModel(e.target.value)}
                    disabled={useMock}
                    className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-primary-500/50 disabled:opacity-50"
                  >
                    {(config?.available_vl_models ?? []).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                {/* 高级 */}
                <button
                  type="button"
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  {showAdvanced ? '收起高级选项' : '高级选项（Base URL）'}
                </button>
                {showAdvanced && (
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">API Base URL</label>
                    <input
                      type="text"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      disabled={useMock}
                      className="w-full bg-dark-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-primary-500/50 disabled:opacity-50"
                    />
                  </div>
                )}

                {error && (
                  <p className="text-xs text-red-400 flex items-start gap-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    {error}
                  </p>
                )}
                {testMsg && (
                  <p className={cn(
                    'text-xs flex items-start gap-1',
                    testMsg.ok ? 'text-green-400' : 'text-amber-400',
                  )}>
                    {testMsg.ok
                      ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      : <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
                    {testMsg.text}
                  </p>
                )}
              </>
            )}
          </div>

          <div className="px-4 py-3 border-t border-gray-700/80 flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="flex-1"
              onClick={handleTest}
              isLoading={testing}
              disabled={loading || saving}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              测试
            </Button>
            <Button
              size="sm"
              className="flex-1"
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
