import { useCallback, useEffect, useState } from 'react';
import { Loader2, RotateCcw, Save } from 'lucide-react';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import promptService, { type PromptInfo } from '@/services/promptService';

interface PromptStageEditorProps {
  projectId: string;
  stage: string;
  stageLabel?: string;
  onSaved?: (info: PromptInfo) => void;
}

export function PromptStageEditor({
  projectId,
  stage,
  stageLabel,
  onSaved,
}: PromptStageEditorProps) {
  const [info, setInfo] = useState<PromptInfo | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    if (!projectId || !stage) return;
    setLoading(true);
    setError(null);
    try {
      const res = await promptService.getPrompt(projectId, stage);
      if (res.code === 200 && res.data) {
        setInfo(res.data);
        setDraft(res.data.effective_template);
        setDirty(false);
      } else {
        setError(res.message || '加载 Prompt 失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, stage]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await promptService.saveOverride(projectId, stage, draft);
      if (res.code === 200 && res.data) {
        setInfo(res.data);
        setDraft(res.data.effective_template);
        setDirty(false);
        onSaved?.(res.data);
      } else {
        setError(res.message || '保存失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleRestore = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await promptService.deleteOverride(projectId, stage);
      if (res.code === 200 && res.data) {
        setInfo(res.data);
        setDraft(res.data.effective_template);
        setDirty(false);
        onSaved?.(res.data);
      } else {
        setError(res.message || '恢复失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '恢复失败');
    } finally {
      setSaving(false);
    }
  };

  const title = stageLabel || stage;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-bp-text">{title}</h3>
          <p className="text-xs text-bp-muted mt-0.5 font-mono">{stage}</p>
        </div>
        <span
          className={
            info?.has_override
              ? 'text-[11px] px-2 py-0.5 rounded-bp border border-bp-yellow/30 bg-bp-yellow/10 text-bp-yellow'
              : 'text-[11px] px-2 py-0.5 rounded-bp border border-bp-border bg-bp-panel/50 text-bp-muted'
          }
        >
          {info?.has_override ? '项目级覆盖' : '系统默认'}
        </span>
      </div>

      {loading ? (
        <LoadingState message="加载 Prompt…" compact />
      ) : error && !draft ? (
        <ErrorState message={error} onRetry={load} compact />
      ) : (
        <>
          {error && (
            <p className="text-xs text-danger-400 mb-2">{error}</p>
          )}
          <textarea
            className="flex-1 min-h-[420px] w-full rounded-bp bg-bp-base border border-bp-border text-xs text-bp-text font-mono p-3 focus:outline-none focus:border-bp-cyan resize-y input-field"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setDirty(true);
            }}
            spellCheck={false}
          />
          <p className="text-[11px] text-bp-muted mt-2">
            支持 {'{{variable}}'} Jinja2 占位符。保存后，Pipeline 运行到该阶段时将使用覆盖模板；可从工作流「从此阶段重跑」生效。
            {info?.updated_at && (
              <span className="text-bp-muted"> · 上次更新 {new Date(info.updated_at).toLocaleString('zh-CN')}</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2 justify-end mt-3 pt-3 border-t border-bp-border">
            <Button variant="secondary" onClick={handleRestore} disabled={saving || !info?.has_override}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" /> 恢复默认
            </Button>
            <Button onClick={handleSave} disabled={saving || loading || !dirty}>
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Save className="w-3.5 h-3.5 mr-1" />}
              保存覆盖
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

export default PromptStageEditor;
