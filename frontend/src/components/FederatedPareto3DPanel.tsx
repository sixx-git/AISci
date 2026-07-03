import { useMemo, useState } from 'react';

export interface Pareto3DPoint {
  method?: string;
  accuracy?: number;
  communication_cost?: number;
  privacy_risk?: number;
  simulated?: boolean;
}

export interface Pareto3DData {
  points?: Pareto3DPoint[];
  frontier_3d?: Pareto3DPoint[];
  best_tradeoff_method?: string;
  axes?: {
    x?: { label?: string; objective?: string };
    y?: { label?: string; objective?: string };
    z?: { label?: string; objective?: string };
  };
}

interface FederatedPareto3DPanelProps {
  data?: Pareto3DData | null;
}

/** 三维 Pareto 交互视图 — 投影视图 + 悬停详情 */
export function FederatedPareto3DPanel({ data }: FederatedPareto3DPanelProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [view, setView] = useState<'acc_comm' | 'acc_privacy' | 'comm_privacy'>('acc_comm');

  const points = data?.points || [];
  const frontier = new Set((data?.frontier_3d || []).map((p) => p.method));

  const bounds = useMemo(() => {
    if (!points.length) return null;
    const accs = points.map((p) => p.accuracy ?? 0);
    const comms = points.map((p) => p.communication_cost ?? 0);
    const privs = points.map((p) => p.privacy_risk ?? 0);
    return {
      minAcc: Math.min(...accs),
      maxAcc: Math.max(...accs),
      minComm: Math.min(...comms),
      maxComm: Math.max(...comms),
      minPriv: Math.min(...privs),
      maxPriv: Math.max(...privs),
    };
  }, [points]);

  if (!points.length || !bounds) return null;

  const norm = (v: number, lo: number, hi: number) =>
    hi - lo < 1e-9 ? 0.5 : (v - lo) / (hi - lo);

  const project = (p: Pareto3DPoint) => {
    const acc = p.accuracy ?? 0;
    const comm = p.communication_cost ?? 0;
    const priv = p.privacy_risk ?? 0;
    if (view === 'acc_privacy') {
      return {
        x: norm(acc, bounds.minAcc, bounds.maxAcc),
        y: 1 - norm(priv, bounds.minPriv, bounds.maxPriv),
      };
    }
    if (view === 'comm_privacy') {
      return {
        x: 1 - norm(comm, bounds.minComm, bounds.maxComm),
        y: 1 - norm(priv, bounds.minPriv, bounds.maxPriv),
      };
    }
    return {
      x: norm(acc, bounds.minAcc, bounds.maxAcc),
      y: 1 - norm(comm, bounds.minComm, bounds.maxComm),
    };
  };

  const viewLabels = {
    acc_comm: { x: 'Accuracy ↑', y: 'Communication ↓' },
    acc_privacy: { x: 'Accuracy ↑', y: 'Privacy Risk ↓' },
    comm_privacy: { x: 'Communication ↓', y: 'Privacy Risk ↓' },
  };

  const hoveredPoint = points.find((p) => p.method === hovered);

  return (
    <div className="mb-4 p-3 rounded border border-bp-border bg-bp-base/50">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <p className="text-xs text-bp-muted">三维 Pareto 交互投影</p>
        <div className="flex gap-1">
          {(Object.keys(viewLabels) as Array<keyof typeof viewLabels>).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setView(k)}
              className={`px-2 py-0.5 rounded text-xs ${
                view === k
                  ? 'bg-bp-purple/20 text-bp-purple border border-bp-purple/30'
                  : 'text-bp-muted border border-bp-border'
              }`}
            >
              {viewLabels[k].x.split(' ')[0]}/{viewLabels[k].y.split(' ')[0]}
            </button>
          ))}
        </div>
      </div>

      <div className="relative w-full h-48 bg-dark-950/80 rounded border border-dark-800">
        <svg viewBox="0 0 100 100" className="w-full h-full">
          {[20, 40, 60, 80].map((g) => (
            <line key={g} x1={g} y1={5} x2={g} y2={95} stroke="rgba(255,255,255,0.04)" />
          ))}
          {[20, 40, 60, 80].map((g) => (
            <line key={`h${g}`} x1={5} y1={g} x2={95} y2={g} stroke="rgba(255,255,255,0.04)" />
          ))}
          {points.map((p) => {
            const { x, y } = project(p);
            const cx = 8 + x * 84;
            const cy = 92 - y * 84;
            const onFront = frontier.has(p.method);
            return (
              <g key={p.method}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={onFront ? 4 : 3}
                  fill={onFront ? 'rgb(167,139,250)' : 'rgb(100,116,139)'}
                  stroke={hovered === p.method ? 'white' : 'transparent'}
                  strokeWidth={0.8}
                  onMouseEnter={() => setHovered(p.method || null)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer' }}
                />
                {onFront && (
                  <text x={cx + 5} y={cy + 1} fontSize={3} fill="rgb(196,181,253)">
                    {(p.method || '').slice(0, 12)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
        <div className="absolute bottom-1 left-2 text-xs text-bp-muted">
          {viewLabels[view].x} · {viewLabels[view].y}
        </div>
      </div>

      {hoveredPoint && (
        <div className="mt-2 p-2 rounded bg-bp-panel/80 text-xs text-bp-muted font-mono">
          <span className="text-bp-purple">{hoveredPoint.method}</span>
          {' · '}acc={hoveredPoint.accuracy?.toFixed(4)}
          {' · '}comm={hoveredPoint.communication_cost}
          {' · '}privacy={hoveredPoint.privacy_risk?.toFixed(4)}
          {frontier.has(hoveredPoint.method || '') && (
            <span className="text-bp-green ml-2">Pareto 前沿</span>
          )}
        </div>
      )}

      {data?.best_tradeoff_method && (
        <p className="text-xs text-bp-muted mt-1">
          三维推荐权衡点：<span className="text-bp-purple">{data.best_tradeoff_method}</span>
        </p>
      )}
    </div>
  );
}
