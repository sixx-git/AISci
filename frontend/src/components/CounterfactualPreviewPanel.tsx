import { FlaskConical, AlertTriangle, ArrowRightLeft, CheckCircle2 } from 'lucide-react';
import type { CounterfactualPreviewData } from '@/types';

interface CounterfactualPreviewPanelProps {
  data: CounterfactualPreviewData;
}

const RISK_STYLE: Record<string, string> = {
  low: 'text-bp-green border-bp-green/30 bg-bp-green/5',
  medium: 'text-bp-yellow border-bp-yellow/30 bg-bp-yellow/5',
  high: 'text-danger-400 border-danger-400/30 bg-danger-400/5',
};

export function CounterfactualPreviewPanel({ data }: CounterfactualPreviewPanelProps) {
  const scenarios = data.scenarios ?? [];
  const failures = data.failure_predictions ?? [];
  const pivots = data.recommended_pivots ?? [];

  return (
    <div className="space-y-4">
      {data.summary && (
        <p className="text-xs text-bp-muted leading-relaxed">{data.summary}</p>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="px-2 py-0.5 rounded border border-bp-border text-bp-muted">
          L0 定性预演
        </span>
        {data.proceed_to_experiment_design === false ? (
          <span className="px-2 py-0.5 rounded border border-danger-400/40 text-danger-400 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            建议加强对照后再设计实验
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded border border-bp-green/40 text-bp-green flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            可进入实验设计
          </span>
        )}
      </div>

      {scenarios.length > 0 && (
        <section>
          <h4 className="text-xs font-medium text-bp-cyan mb-2 flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5" />
            反事实场景 · {scenarios.length}
          </h4>
          <div className="space-y-2">
            {scenarios.map((sc) => {
              const risk = sc.failure_risk ?? 'medium';
              const riskClass = RISK_STYLE[risk] ?? RISK_STYLE.medium;
              return (
                <div
                  key={sc.scenario_id ?? sc.question}
                  className="p-2.5 rounded border border-bp-border/60 bg-bp-base/40 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-bp-text">{sc.intervention}</span>
                    <span className={`shrink-0 px-1.5 py-0.5 rounded border text-[10px] ${riskClass}`}>
                      风险 {risk}
                    </span>
                  </div>
                  <p className="text-bp-muted">{sc.question}</p>
                  <p className="text-bp-text/90">预期: {sc.predicted_outcome}</p>
                  {sc.cheap_test && (
                    <p className="text-bp-cyan/90">廉价验证: {sc.cheap_test}</p>
                  )}
                  {(sc.evidence_fact_ids?.length ?? 0) > 0 && (
                    <p className="text-bp-muted/70 text-[10px]">
                      依据: {sc.evidence_fact_ids!.join(', ')}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {failures.length > 0 && (
        <section>
          <h4 className="text-xs font-medium text-danger-400 mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            失败模式预测
          </h4>
          <ul className="space-y-1">
            {failures.map((f, i) => (
              <li key={i} className="text-xs text-bp-muted flex gap-1.5">
                <span className="text-danger-400/70">•</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {pivots.length > 0 && (
        <section>
          <h4 className="text-xs font-medium text-bp-muted mb-2 flex items-center gap-1.5">
            <ArrowRightLeft className="w-3.5 h-3.5" />
            转向建议
          </h4>
          <ul className="space-y-1">
            {pivots.map((p, i) => (
              <li key={i} className="text-xs text-bp-muted">{p}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
