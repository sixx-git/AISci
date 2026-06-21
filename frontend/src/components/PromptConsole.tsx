import { useEffect, useState } from 'react';
import { Loader2, RotateCcw, Save } from 'lucide-react';
import { Button } from '@/components/Button';
import promptService, { type PromptInfo } from '@/services/promptService';

interface PromptConsoleProps {
  projectId: string;
  stage: string;
  open: boolean;
  onClose: () => void;
}

export function PromptConsole({ projectId, stage, open, onClose }: PromptConsoleProps) {
  const [info, setInfo] = useState<PromptInfo | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !projectId || !stage) return;
    setLoading(true);
    setError(null);
    promptService.getPrompt(projectId, stage)
      .then((res) => {
        if (res.code === 200 && res.data) {
          setInfo(res.data);
          setDraft(res.data.effective_template);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  }, [open, projectId, stage]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await promptService.saveOverride(projectId, stage, draft);
      if (res.code === 200 && res.data) {
        setInfo(res.data);
        setDraft(res.data.effective_template);
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
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '恢复失败');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="w-full max-w-3xl max-h-[85vh] overflow-hidden rounded-xl border border-gray-700 bg-[#161b22] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <div>
            <h3 className="text-sm font-semibold text-white">Prompt 编辑 — {stage}</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {info?.has_override ? '当前使用项目级覆盖' : '当前使用默认模板'}
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white text-sm">关闭</button>
        </div>
        <div className="p-4 flex-1 overflow-y-auto space-y-3">
          {loading ? (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> 加载中…
            </div>
          ) : (
            <>
              {error && <p className="text-xs text-red-400">{error}</p>}
              <textarea
                className="w-full min-h-[360px] rounded-lg bg-[#0d1117] border border-gray-700 text-xs text-gray-200 font-mono p-3 focus:outline-none focus:border-emerald-500"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <p className="text-[11px] text-gray-500">
                支持 {'{{variable}}'} 占位符。保存后，从此阶段重新运行时将使用覆盖 Prompt，并记录在 run 日志中。
              </p>
            </>
          )}
        </div>
        <div className="px-4 py-3 border-t border-gray-800 flex gap-2 justify-end">
          <Button variant="secondary" onClick={handleRestore} disabled={saving || !info?.has_override}>
            <RotateCcw className="w-3.5 h-3.5 mr-1" /> 恢复默认
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Save className="w-3.5 h-3.5 mr-1" />}
            保存覆盖
          </Button>
        </div>
      </div>
    </div>
  );
}

export default PromptConsole;
