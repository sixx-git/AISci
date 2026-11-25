import { useEffect, useState } from 'react';
import { Radio } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import {
  emergencyCommService,
  type EmergencyCommState,
  type EmergencyScenario,
} from '@/services/emergencyCommService';

const STATUS_LABEL = {
  pass: '预检通过',
  fail: '预检未通过',
  partial: '部分解决，整体仍不满足',
} as const;

const ORIGIN_LABEL: Record<string, string> = {
  initial_template: '初始候选方案',
  confirmed_revision: '用户确认的规则修订',
  user_scenario_edit: '用户修改场景参数',
};

function statusClass(status: string) {
  if (status === 'pass') return 'badge bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
  if (status === 'partial') return 'badge bg-amber-500/15 text-amber-300 border border-amber-500/30';
  return 'badge-failed';
}

export function EmergencyCommPage({ projectId }: { projectId: string }) {
  const [state, setState] = useState<EmergencyCommState | null>(null);
  const [draft, setDraft] = useState<EmergencyScenario | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    emergencyCommService.get(projectId)
      .then((res) => {
        if (cancelled) return;
        setState(res.data);
        setDraft(res.data.scenario);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || '加载应急通信方案失败');
      });
    return () => { cancelled = true; };
  }, [projectId]);

  const active = state?.versions[state.versions.length - 1];

  const onNumber = (key: keyof EmergencyScenario, raw: string) => {
    if (!draft) return;
    const value = Number(raw);
    setDraft({ ...draft, [key]: Number.isFinite(value) ? value : 0 });
  };

  const saveScenario = async () => {
    if (!draft) return;
    setBusy(true);
    setError('');
    try {
      const res = await emergencyCommService.updateScenario(projectId, draft);
      setState(res.data);
      setDraft(res.data.scenario);
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新场景失败');
    } finally {
      setBusy(false);
    }
  };

  const confirmSuggestion = async (id: string) => {
    setBusy(true);
    setError('');
    try {
      const res = await emergencyCommService.confirm(projectId, id);
      setState(res.data);
      setDraft(res.data.scenario);
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认修订失败');
    } finally {
      setBusy(false);
    }
  };

  if (!state || !draft || !active) {
    return (
      <Card>
        <p className="text-sm text-bp-muted">{error || '正在加载应急通信方案…'}</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card
        title={state.app}
        subtitle="AI 辅助通信方案设计与可信预检，不是真实 6G 网络控制"
      >
        <p className="text-sm text-bp-muted leading-relaxed">{state.disclaimer}</p>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {['剩余地面网络', '无人机中继', '卫星回传'].map((name) => (
            <div key={name} className="rounded-bp border border-bp-border bg-bp-surface px-3 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-bp-text">
                <Radio className="w-4 h-4 text-bp-cyan" />
                {name}
              </div>
              <p className="text-xs text-bp-muted mt-1">
                {name === '卫星回传' && `上限 ${draft.satellite_backhaul_mbps} Mbps`}
                {name === '无人机中继' && `${draft.uav_count} 架 · 单架 ${draft.uav_endurance_min} 分钟`}
                {name === '剩余地面网络' && `计入回传 ${draft.ground_backhaul_mbps} Mbps`}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="场景参数" subtitle="模拟条件，可修改后重新检查">
          <div className="grid grid-cols-2 gap-3">
            <label className="col-span-2 text-xs text-bp-muted space-y-1">
              <span>应用地点</span>
              <input className="input-field text-sm" value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} />
            </label>
            <label className="col-span-2 text-xs text-bp-muted space-y-1">
              <span>灾害类型</span>
              <input className="input-field text-sm" value={draft.disaster} onChange={(e) => setDraft({ ...draft, disaster: e.target.value })} />
            </label>
            <Num label="通信终端" value={draft.terminals} onChange={(v) => onNumber('terminals', v)} />
            <Num label="救援优先终端" value={draft.priority_terminals} onChange={(v) => onNumber('priority_terminals', v)} />
            <Num label="单终端需求 Mbps" value={draft.demand_mbps_per_terminal} onChange={(v) => onNumber('demand_mbps_per_terminal', v)} step="0.1" />
            <Num label="卫星回传 Mbps" value={draft.satellite_backhaul_mbps} onChange={(v) => onNumber('satellite_backhaul_mbps', v)} step="0.1" />
            <Num label="地面剩余回传 Mbps" value={draft.ground_backhaul_mbps} onChange={(v) => onNumber('ground_backhaul_mbps', v)} step="0.1" />
            <Num label="无人机数量" value={draft.uav_count} onChange={(v) => onNumber('uav_count', v)} />
            <Num label="单架续航 分钟" value={draft.uav_endurance_min} onChange={(v) => onNumber('uav_endurance_min', v)} />
            <Num label="保障时长 分钟" value={draft.mission_duration_min} onChange={(v) => onNumber('mission_duration_min', v)} />
          </div>
          <div className="mt-4">
            <Button type="button" onClick={saveScenario} disabled={busy}>
              {busy ? '检查中…' : '按新参数重新检查'}
            </Button>
          </div>
        </Card>

        <Card title={`当前方案 · 版本 ${active.version}`} subtitle={ORIGIN_LABEL[active.origin] || active.origin}>
          <div className="flex items-center gap-2 mb-3">
            <span className={statusClass(active.status)}>{STATUS_LABEL[active.status]}</span>
            <span className="text-xs text-bp-muted">{active.check.engine}</span>
          </div>
          <p className="text-sm text-bp-text leading-relaxed">{active.summary}</p>
          <ul className="mt-3 space-y-1 text-sm text-bp-muted">
            <li>同时保障 {active.plan.serve_terminal_count} 台，每台 {active.plan.mbps_per_terminal} Mbps</li>
            <li>业务总需求 {active.check.demand_mbps} Mbps / 可用回传 {active.check.backhaul_mbps} Mbps</li>
            <li>无人机连续保障 {active.plan.uav_continuous_min} 分钟，使用 {active.plan.uav_used} 架</li>
            {active.plan.service_requirement_changed && (
              <li>保障范围已改为优先终端，这一变更经过用户确认</li>
            )}
          </ul>
          <p className="mt-3 text-xs text-bp-muted">{active.plan.source_note}</p>
          <div className="mt-4 space-y-2">
            {active.check.items.map((item) => (
              <div key={item.id} className="rounded-bp border border-bp-border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-bp-text">{item.title}</span>
                  <span className={item.passed ? 'text-xs text-emerald-300' : 'text-xs text-danger-400'}>
                    {item.passed ? '通过' : '未通过'}
                  </span>
                </div>
                <p className="text-xs text-bp-muted mt-1">{item.detail}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="大家长协调记录" subtitle="只记录反馈和版本，不自主判定方案能否部署">
        <p className="text-sm text-bp-text leading-relaxed">{active.coordinator.message}</p>
        <div className="mt-4 space-y-3">
          {state.pending_suggestions.length === 0 && (
            <p className="text-sm text-bp-muted">当前没有待确认的规则修订。</p>
          )}
          {state.pending_suggestions.map((item) => (
            <div key={item.id} className="rounded-bp border border-bp-border p-3">
              <p className="text-sm font-medium text-bp-text">{item.title}</p>
              <p className="text-xs text-bp-muted mt-1 leading-relaxed">{item.detail}</p>
              {item.applicable && item.requires_user_confirmation && (
                <div className="mt-3">
                  <Button type="button" variant="secondary" onClick={() => confirmSuggestion(item.id)} disabled={busy}>
                    确认此修订并重新检查
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-danger-400">{error}</p>}
      </Card>

      {active.comparison && (
        <Card title="修订前后对比" subtitle={`版本 ${active.comparison.from_version} → ${active.comparison.to_version}`}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <Compare label="业务需求 Mbps" before={active.comparison.demand_mbps.before} after={active.comparison.demand_mbps.after} />
            <Compare label="保障终端数" before={active.comparison.serve_terminal_count.before} after={active.comparison.serve_terminal_count.after} />
            <Compare label="无人机连续分钟" before={active.comparison.uav_continuous_min.before} after={active.comparison.uav_continuous_min.after} />
          </div>
          <p className="mt-3 text-xs text-bp-muted">
            新通过：{active.comparison.newly_passed.join('、') || '无'}
            {' · '}
            仍未通过：{active.comparison.still_failing.join('、') || '无'}
          </p>
        </Card>
      )}

      <Card title="版本记录" subtitle="同一次输入会得到相同的规则检查结果">
        <div className="space-y-2">
          {[...state.versions].reverse().map((version) => (
            <div key={version.version} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-bp-text">v{version.version}</span>
              <span className={statusClass(version.status)}>{STATUS_LABEL[version.status]}</span>
              <span className="text-bp-muted">{ORIGIN_LABEL[version.origin] || version.origin}</span>
              <span className="text-xs text-bp-muted">{version.created_at}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Num({
  label,
  value,
  onChange,
  step = '1',
}: {
  label: string;
  value: number;
  onChange: (raw: string) => void;
  step?: string;
}) {
  return (
    <label className="text-xs text-bp-muted space-y-1">
      <span>{label}</span>
      <input
        type="number"
        step={step}
        className="input-field text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function Compare({ label, before, after }: { label: string; before: number; after: number }) {
  return (
    <div className="rounded-bp border border-bp-border px-3 py-2">
      <p className="text-xs text-bp-muted">{label}</p>
      <p className="text-bp-text mt-1">{before} → {after}</p>
    </div>
  );
}
