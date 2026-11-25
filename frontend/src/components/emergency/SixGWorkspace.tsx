import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { EmergencyCommPage } from '@/components/emergency/EmergencyCommPage';
import {
  sixgService,
  type SixGParameter,
  type SixGProfile,
} from '@/services/sixgService';

export function SixGWorkspace({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<SixGProfile | null>(null);
  const [draftText, setDraftText] = useState('');
  const [parameters, setParameters] = useState<SixGParameter[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    sixgService.profile(projectId)
      .then((res) => {
        if (cancelled) return;
        setProfile(res.data);
        setDraftText(res.data.research_question || '');
        setParameters(res.data.custom_parse?.parameters || []);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || '加载 6G 专题失败');
      });
    return () => { cancelled = true; };
  }, [projectId]);

  const parseTask = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await sixgService.parse(projectId, draftText);
      setProfile(res.data);
      setParameters(res.data.custom_parse?.parameters || []);
      setNotice('解析完成。带数字的参数需要你核对，模型推测值不是设备实测。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '解析失败');
    } finally {
      setBusy(false);
    }
  };

  const saveParameters = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await sixgService.confirmParameters(
        projectId,
        parameters.map((item) => ({
          name: item.name,
          value: item.value,
          unit: item.unit,
          confirmed: item.confirmed,
        })),
      );
      setProfile(res.data);
      setParameters(res.data.custom_parse?.parameters || []);
      setNotice('已保存核对结果。这些参数仍不是设备实测，也不会自动变成仿真结论。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存参数失败');
    } finally {
      setBusy(false);
    }
  };

  const saveReport = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await sixgService.saveReport(projectId);
      setNotice(`已写入研究报告：${res.data.title}`);
      navigate(`/projects/${projectId}?tab=reports`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '写入报告失败');
    } finally {
      setBusy(false);
    }
  };

  if (!profile) {
    return <Card><p className="text-sm text-bp-muted">{error || '正在加载 6G 专题…'}</p></Card>;
  }

  const pending = profile.verification_status !== 'deterministic';

  return (
    <div className="space-y-6">
      <Card title={profile.topic.label} subtitle={profile.topic.domain}>
        <p className="text-sm text-bp-text leading-relaxed">{profile.coordinator_role}</p>
        <p className="mt-3 text-sm text-bp-muted leading-relaxed">
          {pending ? '待专业验证。' : '本专题已接入确定性预检。'}
          {profile.verification_note}
        </p>
        <p className="mt-2 text-xs text-bp-muted">
          执行方式：{profile.execution_mode === 'full' ? '完整科研分析' : '快速方案预检'}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate(`/projects/${projectId}?tab=workflow`)}>
            进入完整科研分析
          </Button>
          <Button type="button" variant="secondary" onClick={saveReport} disabled={busy}>
            将当前记录写入报告
          </Button>
        </div>
        {notice && <p className="mt-3 text-sm text-bp-text">{notice}</p>}
        {error && <p className="mt-3 text-sm text-danger-400">{error}</p>}
      </Card>

      {profile.emergency_tool_enabled ? (
        <EmergencyCommPage projectId={projectId} />
      ) : (
        <Card title="专题任务" subtitle="文献、假设和报告仍走原有科研工作流">
          <div className="space-y-3 text-sm text-bp-muted leading-relaxed">
            <p>{profile.topic.research_background || '请在下方填写自定义任务。'}</p>
            <p>研究目标：{profile.topic.research_goal || profile.custom_parse?.research_goal || '待填写'}</p>
            <p>约束：{profile.topic.constraints}</p>
          </div>
          {profile.topic.id === 'custom' && (
            <div className="mt-4 space-y-3">
              <textarea
                className="input-field min-h-[120px]"
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                placeholder="输入 6G 研究问题、场景和约束。不要依赖模型补造设备参数。"
              />
              <Button type="button" onClick={parseTask} disabled={busy || !draftText.trim()}>
                {busy ? '解析中…' : '用 Qwen 解析任务'}
              </Button>
              {parameters.length > 0 && (
                <div className="space-y-3">
                  {parameters.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="rounded-bp border border-bp-border p-3">
                      <p className="text-sm text-bp-text">{item.name}</p>
                      <p className="text-xs text-bp-muted mt-1">{item.note}</p>
                      <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <input
                          className="input-field text-sm"
                          value={item.value}
                          onChange={(e) => {
                            const next = [...parameters];
                            next[index] = { ...item, value: e.target.value, confirmed: false };
                            setParameters(next);
                          }}
                        />
                        <input
                          className="input-field text-sm"
                          value={item.unit}
                          onChange={(e) => {
                            const next = [...parameters];
                            next[index] = { ...item, unit: e.target.value };
                            setParameters(next);
                          }}
                        />
                        <label className="flex items-center gap-2 text-xs text-bp-muted">
                          <input
                            type="checkbox"
                            checked={item.confirmed}
                            onChange={(e) => {
                              const next = [...parameters];
                              next[index] = { ...item, confirmed: e.target.checked };
                              setParameters(next);
                            }}
                          />
                          我已核对，这不是实测值
                        </label>
                      </div>
                    </div>
                  ))}
                  <Button type="button" variant="secondary" onClick={saveParameters} disabled={busy}>
                    保存核对后的参数
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
