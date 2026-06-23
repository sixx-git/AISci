import { useCallback, useEffect, useState } from 'react';
import { Loader2, RotateCcw, Save } from 'lucide-react';
import { Button } from '@/components/Button';
import promptService, { type PromptInfo } from '@/services/promptService';

interface PromptStageEditorProps {
  projectId: string;
  stage: string;
  stageLabel?: string;
  /** 父组件保存成功后回调，用于刷新覆盖状态列表 */
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
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">{stage}</p>
        </div>
        <span
          className={
            info?.has_override
              ? 'text-[11px] px-2 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-300'
              : 'text-[11px] px-2 py-0.5 rounded border border-gray-600 bg-gray-800/50 text-gray-400'
          }
        >
          {info?.has_override ? '项目级覆盖' : '系统默认'}
        </span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-gray-400 text-sm py-12 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> 加载 Prompt…
        </div>
      ) : (
        <>
          {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
          <textarea
            className="flex-1 min-h-[420px] w-full rounded-lg bg-[#0d1117] border border-gray-700 text-xs text-gray-200 font-mono p-3 focus:outline-none focus:border-emerald-500 resize-y"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setDirty(true);
            }}
            spellCheck={false}
          />
          <p className="text-[11px] text-gray-500 mt-2">
            支持 {'{{variable}}'} Jinja2 占位符。保存后，Pipeline 运行到该阶段时将使用覆盖模板；可从工作流「从此阶段重跑」生效。
            {info?.updated_at && (
              <span className="text-gray-600"> · 上次更新 {new Date(info.updated_at).toLocaleString('zh-CN')}</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2 justify-end mt-3 pt-3 border-t border-gray-800">
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
