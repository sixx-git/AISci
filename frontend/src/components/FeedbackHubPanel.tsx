import { useState, useEffect, useCallback } from 'react';
import { MessageSquarePlus, Loader2 } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import feedbackService, { type FeedbackEntry } from '@/services/feedbackService';

interface FeedbackHubPanelProps {
  projectId: string;
}

export function FeedbackHubPanel({ projectId }: FeedbackHubPanelProps) {
  const [message, setMessage] = useState('');
  const [source, setSource] = useState('user');
  const [target, setTarget] = useState('hypothesis');
  const [constraints, setConstraints] = useState<string[]>([]);
  const [entries, setEntries] = useState<FeedbackEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await feedbackService.getConstraints(projectId);
      if (res.code === 200 && res.data) {
        setConstraints(res.data.global_constraints || []);
        setEntries(res.data.recent_entries || []);
      }
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async () => {
    if (!message.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await feedbackService.submit({
        project_id: projectId,
        source,
        message: message.trim(),
        target,
        trigger_rerun: false,
      });
      if (res.code === 200) {
        setMessage('');
        await load();
      } else {
        setError(res.message || '提交失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-4 border-violet-500/20 bg-violet-500/5">
      <h4 className="text-sm font-semibold text-violet-300 mb-2 flex items-center gap-1.5">
        <MessageSquarePlus className="w-4 h-4" />
        统一反馈中心
      </h4>
      <p className="text-[10px] text-bp-muted mb-3">
        纠错/约束一处提交，自动写入 global_constraints 并影响下一轮 Pipeline
      </p>

      <div className="flex flex-wrap gap-2 mb-2">
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="text-xs bg-bp-base border border-bp-border rounded px-2 py-1 text-bp-text"
        >
          <option value="user">用户</option>
          <option value="provenance">Provenance</option>
          <option value="data_finder">Data Finder</option>
          <option value="kg">知识图谱</option>
          <option value="hitl">HITL</option>
        </select>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="text-xs bg-bp-base border border-bp-border rounded px-2 py-1 text-bp-text"
        >
          <option value="hypothesis">假设</option>
          <option value="data_finder">Data Finder</option>
          <option value="literature">文献</option>
          <option value="experiment">实验</option>
        </select>
      </div>

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="描述错误、修正建议或约束（将注入下一轮）"
        className="w-full text-xs input-field min-h-[72px] mb-2"
      />

      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      <Button
        variant="secondary"
        size="sm"
        onClick={handleSubmit}
        isLoading={loading}
        icon={loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : undefined}
      >
        提交反馈
      </Button>

      {constraints.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] text-bp-muted mb-1">活跃约束 ({constraints.length})</p>
          <ul className="text-[10px] text-bp-muted space-y-1 max-h-24 overflow-y-auto">
            {constraints.slice(-5).map((c) => (
              <li key={c} className="line-clamp-2">• {c}</li>
            ))}
          </ul>
        </div>
      )}

      {entries.length > 0 && (
        <div className="mt-2 text-[10px] text-bp-muted">
          最近 {entries.length} 条反馈已记录
        </div>
      )}
    </Card>
  );
}
