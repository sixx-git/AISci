import { useCallback, useEffect, useMemo, useState } from 'react';
import { LayoutTemplate, Loader2, Layers, Eye } from 'lucide-react';
import { Button } from '@/components/Button';
import promptService, { type PromptPresetCatalog, type PromptPresetPack } from '@/services/promptService';

interface PromptPresetBarProps {
  projectId: string;
  stage: string;
  presetLocked?: boolean;
  onApplied?: () => void;
}

export function PromptPresetBar({
  projectId,
  stage,
  presetLocked = false,
  onApplied,
}: PromptPresetBarProps) {
  const [catalog, setCatalog] = useState<PromptPresetCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [packId, setPackId] = useState('pack_c');
  const [variantId, setVariantId] = useState('');
  const [preview, setPreview] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const res = await promptService.getPresetCatalog(projectId);
      if (res.code === 200 && res.data) {
        setCatalog(res.data);
        const defaultPack = res.data.packs.find((p) => p.id === res.data.default_pack_id) || res.data.packs[0];
        if (defaultPack) setPackId(defaultPack.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载范式库失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const selectedPack: PromptPresetPack | undefined = catalog?.packs.find((p) => p.id === packId);
  const stageVariants = selectedPack?.stages[stage] ?? [];

  useEffect(() => {
    if (stageVariants.length > 0) {
      setVariantId((prev) => (stageVariants.some((v) => v.id === prev) ? prev : stageVariants[0].id));
    } else {
      setVariantId('');
    }
    setPreview(null);
  }, [packId, stage, stageVariants]);

  const selectedVariant = stageVariants.find((v) => v.id === variantId);
  const packStagesCount = selectedPack ? Object.keys(selectedPack.stages).length : 0;

  const handlePreview = async () => {
    if (!variantId || presetLocked) return;
    setBusy('preview');
    setError(null);
    try {
      const res = await promptService.getPresetContent(packId, stage, variantId);
      if (res.code === 200 && res.data) {
        setPreview(res.data.content);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '预览失败');
    } finally {
      setBusy(null);
    }
  };

  const handleApplyStage = async () => {
    if (!variantId || presetLocked) return;
    setBusy('apply');
    setError(null);
    try {
      const res = await promptService.applyPreset(projectId, packId, { stage, variantId });
      if (res.code === 200) onApplied?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '应用失败');
    } finally {
      setBusy(null);
    }
  };

  const handleApplyAll = async () => {
    if (!selectedPack || presetLocked) return;
    if (!window.confirm(`将「${selectedPack.label}」应用到该包内全部 ${packStagesCount} 个阶段（每阶段使用其默认变体）？`)) {
      return;
    }
    setBusy('applyAll');
    setError(null);
    try {
      const res = await promptService.applyPreset(projectId, packId, { applyAllStages: true });
      if (res.code === 200) onApplied?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '批量应用失败');
    } finally {
      setBusy(null);
    }
  };

  const hint = useMemo(() => {
    if (presetLocked) {
      return catalog?.excluded_reason || '报告生成使用固定章节模板，不提供范式预设。';
    }
    if (!selectedPack) return '';
    if (stageVariants.length === 0) {
      return `当前范式包不包含「${stage}」阶段预设。`;
    }
    return selectedVariant?.description || selectedPack.description;
  }, [presetLocked, catalog, selectedPack, stageVariants, stage, selectedVariant]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-bp-muted py-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> 加载范式模板库…
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-bp-border bg-bp-base/40 p-3 space-y-3">
      <div className="flex items-center gap-2 text-xs font-medium text-bp-text">
        <LayoutTemplate className="w-4 h-4 text-bp-purple" />
        范式模板库
        <span className="text-bp-muted font-normal">（AISci v1 / v2 / 默认{selectedPack?.requires_federated ? '' : '；联邦包仅联邦项目可见'}）</span>
      </div>

      {presetLocked ? (
        <p className="text-xs text-bp-yellow/90 bg-bp-yellow/5 border border-bp-yellow/20 rounded px-3 py-2">
          {hint}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            <label className="block">
              <span className="text-xs text-bp-muted mb-1 block">范式包</span>
              <select
                value={packId}
                onChange={(e) => setPackId(e.target.value)}
                className="w-full px-2 py-1.5 bg-bp-base border border-bp-border rounded text-xs text-bp-text"
              >
                {(catalog?.packs ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="text-xs text-bp-muted mb-1 block">当前阶段变体</span>
              <select
                value={variantId}
                onChange={(e) => setVariantId(e.target.value)}
                disabled={stageVariants.length === 0}
                className="w-full px-2 py-1.5 bg-bp-base border border-bp-border rounded text-xs text-bp-text disabled:opacity-50"
              >
                {stageVariants.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end gap-1">
              <Button
                size="sm"
                variant="secondary"
                className="text-xs flex-1"
                disabled={!variantId || busy !== null}
                onClick={handlePreview}
              >
                {busy === 'preview' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
                预览
              </Button>
            </div>
          </div>

          {selectedPack?.reference && (
            <p className="text-xs text-bp-muted">
              参考：{selectedPack.reference}
              {selectedPack.recommended_pipeline_mode && (
                <span> · 推荐运行模式 {selectedPack.recommended_pipeline_mode}</span>
              )}
            </p>
          )}

          {hint && <p className="text-xs text-bp-muted leading-relaxed">{hint}</p>}

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={!variantId || busy !== null || stageVariants.length === 0}
              onClick={handleApplyStage}
            >
              {busy === 'apply' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
              应用到本阶段
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy !== null || packStagesCount === 0}
              onClick={handleApplyAll}
            >
              {busy === 'applyAll' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Layers className="w-3.5 h-3.5 mr-1" />}
              应用整套（{packStagesCount} 阶段）
            </Button>
          </div>

          {preview && (
            <pre className="text-xs text-bp-muted font-mono bg-dark-950 border border-bp-border rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
              {preview.slice(0, 2000)}{preview.length > 2000 ? '\n…' : ''}
            </pre>
          )}
        </>
      )}

      {error && <p className="text-xs text-danger-400">{error}</p>}
    </div>
  );
}

export default PromptPresetBar;
