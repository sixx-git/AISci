import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from 'recharts';
import { cn } from '@/lib/utils';
import { predictService, type ImpactReport } from '@/services/predictService';
import {
  asArray,
  asRecord,
  dimBarColor,
  getDimensions,
  ratingBadgeClass,
  resolveCompositeScore,
  resolveImpactScore,
  str,
} from './predictHelpers';

interface ImpactDetailViewProps {
  jobId: string;
  report: ImpactReport;
  onBack: () => void;
}

function Collapsible({
  title,
  defaultOpen,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  return (
    <details
      className="mb-2 border border-[#e8e8e8] rounded-lg overflow-hidden"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="px-4 py-3 text-[0.88rem] font-semibold !text-[#1a1a1a] cursor-pointer bg-[#fafafa] list-none flex items-center gap-2 select-none [&::-webkit-details-marker]:hidden open:bg-[#f0f0f0]">
        <span className={cn('text-[0.65rem] !text-[#555] transition-transform', open && 'rotate-90')}>
          ▶
        </span>
        <span className="!text-[#1a1a1a]">{title}</span>
      </summary>
      {open && <div className="px-[18px] py-4 space-y-2.5 border-t border-[#e0e0e0]">{children}</div>}
    </details>
  );
}

function SectionLabel({ children, color }: { children: ReactNode; color?: string }) {
  return (
    <div
      className="text-[0.82rem] font-semibold mt-3 mb-1.5 pb-1 border-b border-[#eee]"
      style={{ color: color || '#333' }}
    >
      {children}
    </div>
  );
}

function InfoGrid({ items }: { items: { label: string; value: ReactNode }[] }) {
  if (items.length === 0) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 my-2.5">
      {items.map((it) => (
        <div key={it.label} className="px-3 py-2.5 rounded-md bg-[#f8f9fa]">
          <div className="text-[0.72rem] text-[#888] mb-0.5">{it.label}</div>
          <div className="text-[0.85rem] font-semibold text-[#1a1a1a] break-words">{it.value}</div>
        </div>
      ))}
    </div>
  );
}

function DCard({
  title,
  children,
  borderColor,
}: {
  title?: string;
  children: ReactNode;
  borderColor?: string;
}) {
  return (
    <div
      className="bg-[#fafafa] border border-[#eee] rounded-lg px-3.5 py-3 mb-2.5"
      style={borderColor ? { borderLeftWidth: 3, borderLeftColor: borderColor } : undefined}
    >
      {title && <div className="text-[0.8rem] font-semibold text-[#333] mb-1.5">{title}</div>}
      <div className="text-[0.78rem] text-[#555] leading-relaxed space-y-1">{children}</div>
    </div>
  );
}

function Tag({
  children,
  tone = 'gray',
}: {
  children: ReactNode;
  tone?: 'green' | 'red' | 'blue' | 'orange' | 'gray';
}) {
  const map = {
    green: 'bg-[#e8f5e9] text-[#2e7d32]',
    red: 'bg-[#fce4ec] text-[#c62828]',
    blue: 'bg-[#e3f2fd] text-[#1565c0]',
    orange: 'bg-[#fff3e0] text-[#e65100]',
    gray: 'bg-[#f5f5f5] text-[#666]',
  };
  return (
    <span className={cn('inline-block px-2 py-0.5 rounded text-[0.72rem] font-semibold', map[tone])}>
      {children}
    </span>
  );
}

export function ImpactDetailView({ jobId, report, onBack }: ImpactDetailViewProps) {
  const meta = asRecord(report.metadata);
  const impact = asRecord(report.impact);
  const rating = asRecord(report.rating);
  const biasExp = asRecord(report.bias_explanation);
  const cq = asRecord(report.content_quality);
  const analysis = asRecord(impact._analysis_data);
  const paperFeatures = asRecord(analysis.paper_features);
  const citationGraph = asRecord(analysis.citation_graph);
  const structure = asRecord(paperFeatures.structure);
  const innovation = asRecord(paperFeatures.innovation);
  const qualitySignals = asRecord(paperFeatures.quality_signals);
  const calibration = asRecord(
    (impact.calibration as Record<string, unknown>) || impact,
  );

  const [jobLogs, setJobLogs] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await predictService.getStatus(jobId);
        if (!cancelled && Array.isArray(st.logs)) setJobLogs(st.logs.map(String));
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const title = str(meta.title || report.title, '未知标题');
  const composite = resolveCompositeScore(rating, report.total_score);
  const impResolved = resolveImpactScore(impact);
  const dims = useMemo(() => getDimensions(impact), [impact]);

  const radarData = dims.map((d) => ({
    name: d.name.replace(/^D\d\s*/, ''),
    value: d.max > 0 ? Math.round((d.score / d.max) * 100) : 0,
    fullMark: 100,
  }));

  const keyFactors = asArray(impact.key_factors) as Array<Record<string, unknown>>;
  const factorChartData = keyFactors.slice(0, 8).map((f, i) => ({
    name: str(f.factor || f.description, `因子${i + 1}`).slice(0, 18),
    mag:
      /high|高/i.test(str(f.magnitude))
        ? 3
        : /low|低/i.test(str(f.magnitude))
          ? 1
          : 2,
    positive: f.impact === 'positive' || f.impact === 'pos',
  }));

  const cqPct =
    cq.best_pct != null
      ? Number(cq.best_pct)
      : rating.best_content_pct != null
        ? Number(rating.best_content_pct)
        : rating.content_quality != null
          ? Number(rating.content_quality)
          : null;

  const authors = asArray(meta.authors)
    .map((a) =>
      typeof a === 'object' && a && 'name' in a
        ? str((a as { name: unknown }).name)
        : str(a),
    )
    .filter(Boolean)
    .join(', ');

  const biasAnalysis = asRecord(biasExp.bias_analysis);
  const biasKeys = Object.keys(biasAnalysis);
  const fairness = asRecord(biasExp.fairness_assessment);
  const dataRel = asRecord(biasExp.data_reliability);

  const underest = asArray(biasExp.underestimation_bias) as Array<Record<string, unknown>>;
  const overest = asArray(biasExp.overestimation_bias) as Array<Record<string, unknown>>;
  const improvePath = asArray(
    biasExp.improvement_path ?? biasExp.improvement_paths,
  ) as Array<Record<string, unknown>>;
  const declineRisks = asArray(biasExp.decline_risks) as Array<Record<string, unknown>>;

  return (
    <div className="max-w-[860px] mx-auto text-[#1a1a1a]">
      {/* 顶栏 */}
      <div className="flex items-center gap-3 mb-5">
        <button
          type="button"
          onClick={onBack}
          className="shrink-0 px-3.5 py-1.5 rounded-md border border-[#ddd] bg-white text-[0.82rem] text-[#444] hover:bg-[#f5f5f5]"
        >
          ← 返回
        </button>
        <h2 className="flex-1 min-w-0 text-[1.15rem] font-semibold text-[#1a1a1a] leading-snug">
          {title}
        </h2>
        <a
          href={predictService.downloadUrl(jobId, 'impact')}
          download="impact_report.json"
          className="shrink-0 px-3.5 py-1.5 rounded-md bg-[#1a1a1a] text-white text-[0.78rem] hover:bg-[#333] no-underline"
        >
          下载报告
        </a>
      </div>

      {/* 评级摘要 */}
      <div className="flex flex-wrap items-center gap-4 mb-5 px-[18px] py-4 rounded-[10px] bg-[#fafafa] border border-[#eee]">
        <span
          className={cn(
            'inline-block px-3.5 py-1 rounded text-[1.3rem] font-bold leading-relaxed',
            ratingBadgeClass(str(rating.rating, 'N')),
          )}
        >
          {str(rating.rating, 'N/A')}
        </span>
        <div>
          <div className="text-[2rem] font-bold text-[#1a1a1a] leading-none">
            {composite != null ? composite.toFixed(1) : '—'}
          </div>
          <div className="text-[0.78rem] text-[#888] mt-1">综合得分</div>
        </div>
        {impResolved.score != null && (
          <div>
            <div className="text-[2rem] font-bold text-[#1a1a1a] leading-none">
              {impResolved.score}/{impResolved.max}
            </div>
            <div className="text-[0.78rem] text-[#888] mt-1">
              影响力得分{impact.impact_level ? ` (${str(impact.impact_level)})` : ''}
            </div>
          </div>
        )}
        {cqPct != null && Number.isFinite(cqPct) && (
          <div>
            <div className="text-[2rem] font-bold text-[#1a1a1a] leading-none">
              {cqPct.toFixed(1)}%
            </div>
            <div className="text-[0.78rem] text-[#888] mt-1">内容质量（最高项）</div>
          </div>
        )}
        {rating.rating_label != null && (
          <div className="text-[0.82rem] text-[#666] ml-1">{str(rating.rating_label)}</div>
        )}
      </div>

      {/* 元信息 chips */}
      <div className="flex flex-wrap gap-3 mb-5 text-[0.8rem] text-[#666]">
        {Boolean(meta.host_venue || meta.venue) && (
          <span className="bg-[#f5f5f5] px-2.5 py-0.5 rounded">{str(meta.host_venue || meta.venue)}</span>
        )}
        {Boolean(meta.publication_year || meta.year) && (
          <span className="bg-[#f5f5f5] px-2.5 py-0.5 rounded">
            {str(meta.publication_year || meta.year)} 年
          </span>
        )}
        {meta.cited_by_count != null && (
          <span className="bg-[#f5f5f5] px-2.5 py-0.5 rounded">被引 {str(meta.cited_by_count)} 次</span>
        )}
        {Boolean(report.doi || meta.doi) && (
          <span className="bg-[#f5f5f5] px-2.5 py-0.5 rounded">DOI: {str(report.doi || meta.doi)}</span>
        )}
        {authors && (
          <span className="basis-full text-[0.75rem] text-[#999]">{authors}</span>
        )}
      </div>

      {/* 面板 1 */}
      <Collapsible title="预测结果与核心判据 (Result & Drivers)" defaultOpen>
        {dims.length > 0 && (
          <>
            <SectionLabel>四维度得分</SectionLabel>
            <div className="space-y-2 mb-2">
              {dims.map((d, i) => {
                const pct = d.max > 0 ? (d.score / d.max) * 100 : 0;
                return (
                  <div key={d.name} className="flex items-center gap-2">
                    <label className="min-w-[100px] text-[0.78rem] font-medium text-[#444] m-0">
                      {d.name}
                    </label>
                    <div className="flex-1 h-2 bg-[#e5e5e5] rounded overflow-hidden">
                      <div
                        className="h-full rounded transition-all"
                        style={{ width: `${pct}%`, background: dimBarColor(i) }}
                      />
                    </div>
                    <span className="min-w-[60px] text-right text-[0.78rem] font-semibold">
                      {d.score}/{d.max}
                    </span>
                  </div>
                );
              })}
            </div>
            {radarData.length >= 3 && (
              <div className="w-full h-[280px] my-2.5">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#ddd" />
                    <PolarAngleAxis dataKey="name" tick={{ fill: '#555', fontSize: 12 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar dataKey="value" stroke="#1a1a1a" fill="#1a1a1a" fillOpacity={0.2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}

        {(calibration.raw_reputation_component != null
          || calibration.raw_quality_component != null) && (
          <>
            <SectionLabel>校准公式分量</SectionLabel>
            <DCard>
              {calibration.raw_reputation_component != null && (
                <p>
                  声誉分量:{' '}
                  <strong>{Number(calibration.raw_reputation_component).toFixed(1)}</strong>
                  {calibration.reputation_adjustment != null
                    && Number(calibration.reputation_adjustment) !== 0
                    && ` (调整 ${Number(calibration.reputation_adjustment).toFixed(1)})`}
                </p>
              )}
              {calibration.raw_quality_component != null && (
                <p>
                  质量分量:{' '}
                  <strong>{Number(calibration.raw_quality_component).toFixed(1)}</strong>
                  {calibration.quality_adjustment != null
                    && Number(calibration.quality_adjustment) !== 0
                    && ` (调整 ${Number(calibration.quality_adjustment).toFixed(1)})`}
                </p>
              )}
              {calibration.bias_mitigation_summary != null && (
                <p className="text-[#666] mt-1">{str(calibration.bias_mitigation_summary)}</p>
              )}
            </DCard>
          </>
        )}

        {keyFactors.length > 0 && (
          <>
            <SectionLabel>关键影响因子</SectionLabel>
            <DCard>
              {keyFactors.map((f, i) => {
                const pos = f.impact === 'positive' || f.impact === 'pos';
                return (
                  <div
                    key={i}
                    className="flex items-start gap-2 py-1.5 border-b border-[#f0f0f0] last:border-0 text-[0.78rem]"
                  >
                    <span
                      className={cn(
                        'font-semibold whitespace-nowrap min-w-[48px] text-[0.72rem] px-1.5 py-0.5 rounded text-white',
                        pos ? 'bg-[#4caf50]' : 'bg-[#f44336]',
                      )}
                    >
                      {pos ? '正面' : '负面'}
                    </span>
                    <span className="text-[0.72rem] text-[#888] min-w-[40px]">
                      {str(f.magnitude)}
                    </span>
                    <span>{str(f.factor || f.description)}</span>
                  </div>
                );
              })}
            </DCard>
            {factorChartData.length > 0 && (
              <div className="w-full h-[280px] my-2.5">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={factorChartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" domain={[0, 3]} hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={110}
                      tick={{ fill: '#555', fontSize: 11 }}
                    />
                    <Tooltip />
                    <Bar dataKey="mag" radius={[0, 4, 4, 0]}>
                      {factorChartData.map((entry, i) => (
                        <Cell key={i} fill={entry.positive ? '#4caf50' : '#f44336'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}

        {asArray(cq.details).length > 0 && (
          <>
            <SectionLabel>内容质量来源</SectionLabel>
            <DCard>
              {(asArray(cq.details) as Array<Record<string, unknown>>).map((dd, i) => {
                const isBest = dd.score_percentage === cq.best_pct;
                return (
                  <div
                    key={i}
                    className={cn(
                      'flex justify-between py-1 text-[0.78rem]',
                      isBest && 'text-[#1565c0] font-semibold',
                    )}
                  >
                    <span>
                      {isBest ? '* ' : ''}
                      {str(dd.label || dd.task_type)}
                    </span>
                    <span>
                      {str(dd.raw_score)}/{str(dd.total_score)} ({str(dd.score_percentage)}%)
                    </span>
                  </div>
                );
              })}
            </DCard>
          </>
        )}

        <SectionLabel>影响力来源</SectionLabel>
        <InfoGrid
          items={[
            citationGraph.citation_velocity != null
              ? { label: '引用速度', value: `${Number(citationGraph.citation_velocity).toFixed(1)} 次/月` }
              : null,
            citationGraph.field_percentile != null
              ? { label: '领域百分位', value: `${Number(citationGraph.field_percentile).toFixed(1)}%` }
              : null,
            asRecord(citationGraph.network_size).total != null
              ? { label: '引用网络规模', value: str(asRecord(citationGraph.network_size).total) }
              : null,
            meta.cited_by_count != null
              ? { label: '总引用次数', value: str(meta.cited_by_count) }
              : null,
            impact.impact_level
              ? { label: '影响力等级', value: str(impact.impact_level) }
              : null,
          ].filter(Boolean) as { label: string; value: ReactNode }[]}
        />

        {impact.overall_assessment != null && (
          <>
            <SectionLabel>综合评语</SectionLabel>
            <DCard>{str(impact.overall_assessment)}</DCard>
          </>
        )}
      </Collapsible>

      {/* 面板 2 */}
      <Collapsible title="可解释性分析 (Interpretability)">
        {(structure.sections_found
          || structure.has_abstract != null
          || paperFeatures.overall_quality_score != null) && (
          <>
            <SectionLabel>论文文本特征</SectionLabel>
            <InfoGrid
              items={[
                paperFeatures.overall_quality_score != null
                  ? {
                      label: '整体质量评分',
                      value: Number(paperFeatures.overall_quality_score).toFixed(0),
                    }
                  : null,
                structure.has_abstract != null
                  || structure.has_methodology != null
                  || asArray(structure.sections_found).length > 0
                  ? {
                      label: '结构完整性',
                      value: [
                        structure.has_abstract != null
                          ? (structure.has_abstract ? '有摘要' : '无摘要')
                          : null,
                        structure.has_methodology ? '有方法' : null,
                        structure.has_results ? '有结果' : null,
                        structure.has_conclusion ? '有结论' : null,
                        asArray(structure.sections_found).length
                          ? `章节: ${asArray(structure.sections_found).join(', ')}`
                          : null,
                      ]
                        .filter(Boolean)
                        .join(', '),
                    }
                  : null,
                structure.methodology_depth != null
                  ? { label: '方法论深度', value: str(structure.methodology_depth) }
                  : null,
                innovation.novelty_density != null
                  ? { label: '创新密度', value: str(innovation.novelty_density) }
                  : null,
                innovation.novelty_claims_count != null
                  ? { label: '新颖性声明数', value: str(innovation.novelty_claims_count) }
                  : null,
                qualitySignals.experiment_rigor != null
                  ? { label: '实验严谨度', value: str(qualitySignals.experiment_rigor) }
                  : null,
                qualitySignals.reproducibility_signals != null
                  ? { label: '可复现信号', value: str(qualitySignals.reproducibility_signals) }
                  : null,
              ].filter(Boolean) as { label: string; value: ReactNode }[]}
            />
          </>
        )}

        {asArray(meta.concepts).length > 0 && (
          <>
            <SectionLabel>跨领域标签</SectionLabel>
            <DCard>
              <div className="flex flex-wrap gap-1.5">
                {asArray(meta.concepts).map((c, i) => (
                  <Tag key={i} tone="blue">
                    {typeof c === 'object' && c && 'display_name' in c
                      ? str((c as { display_name: unknown }).display_name)
                      : str(c)}
                  </Tag>
                ))}
              </div>
            </DCard>
          </>
        )}

        {(citationGraph.diversity != null
          || citationGraph.high_impact_ratio != null
          || citationGraph.connectivity != null) && (
          <>
            <SectionLabel>引用网络数据</SectionLabel>
            <InfoGrid
              items={[
                citationGraph.diversity != null
                  ? { label: '引用多样性', value: str(citationGraph.diversity) }
                  : null,
                citationGraph.high_impact_ratio != null
                  ? {
                      label: '高影响力引用比例',
                      value: Number(citationGraph.high_impact_ratio).toFixed(2),
                    }
                  : null,
                citationGraph.connectivity != null
                  ? { label: '网络连通性', value: str(citationGraph.connectivity) }
                  : null,
                citationGraph.avg_citation_age != null
                  ? {
                      label: '平均引用年龄',
                      value: `${Number(citationGraph.avg_citation_age).toFixed(1)} 年`,
                    }
                  : null,
              ].filter(Boolean) as { label: string; value: ReactNode }[]}
            />
          </>
        )}

        {asArray(impact.corrections).length > 0 && (
          <>
            <SectionLabel>元数据修正记录</SectionLabel>
            <DCard>
              {(asArray(impact.corrections) as Array<Record<string, unknown>>).map((cr, i) => (
                <div key={i} className="mb-2 last:mb-0">
                  <p>
                    <strong>{str(cr.field)}</strong>: {str(cr.raw)} → <strong>{str(cr.corrected)}</strong>
                  </p>
                  {cr.reason != null && (
                    <p className="text-[0.73rem] text-[#888]">{str(cr.reason)}</p>
                  )}
                </div>
              ))}
            </DCard>
          </>
        )}

        {dims.some((d) => d.rationale) && (
          <>
            <SectionLabel>各维度判据说明</SectionLabel>
            {dims
              .filter((d) => d.rationale)
              .map((d) => (
                <DCard key={d.name} title={`${d.name} (${d.score}/${d.max})`}>
                  {d.rationale}
                </DCard>
              ))}
          </>
        )}

        {!structure.has_abstract
          && !dims.some((d) => d.rationale)
          && asArray(meta.concepts).length === 0
          && paperFeatures.overall_quality_score == null && (
            <p className="text-[#aaa] text-[0.8rem] italic py-2">
              无可解释性数据（文本特征和引用网络数据在当前版本中未完整提取）
            </p>
          )}
      </Collapsible>

      {/* 面板 3 */}
      <Collapsible title="偏差识别与公平性 (Bias & Fairness)">
        {biasKeys.length > 0 && (
          <>
            <SectionLabel>偏差维度分析</SectionLabel>
            {biasKeys.map((k) => {
              const dim = asRecord(biasAnalysis[k]);
              const detected = Boolean(dim.detected);
              return (
                <div
                  key={k}
                  className={cn(
                    'border-l-[3px] pl-3 pr-3 py-2 mb-2 bg-white rounded-r-md',
                    detected ? 'border-l-[#f44336]' : 'border-l-[#4caf50]',
                  )}
                >
                  <div className="text-[0.78rem] font-semibold mb-1 flex flex-wrap items-center gap-1.5">
                    <span>{k.replace(/_/g, ' ')}</span>
                    {dim.direction != null && (
                      <Tag tone={dim.direction === 'positive' ? 'green' : 'red'}>
                        {str(dim.direction)}
                      </Tag>
                    )}
                    <Tag tone={detected ? 'red' : 'green'}>
                      {detected ? '已检测到' : '未检测到'}
                    </Tag>
                  </div>
                  <div className="text-[0.75rem] text-[#555] leading-relaxed space-y-0.5">
                    {dim.estimated_impact != null && (
                      <p>
                        估计影响:{' '}
                        <strong>{Number(dim.estimated_impact).toFixed(2)}</strong>
                      </p>
                    )}
                    {dim.description != null && <p>{str(dim.description)}</p>}
                    {dim.assessment != null && <p>{str(dim.assessment)}</p>}
                    {dim.evidence != null && <p>{str(dim.evidence)}</p>}
                    {dim.mitigation != null && (
                      <p className="text-[#2e7d32]">缓解措施: {str(dim.mitigation)}</p>
                    )}
                    {dim.score != null && <p className="font-mono">score: {str(dim.score)}</p>}
                  </div>
                </div>
              );
            })}
          </>
        )}

        {biasExp.current_assessment != null && (
          <>
            <SectionLabel>评估总述</SectionLabel>
            <DCard>{str(biasExp.current_assessment)}</DCard>
          </>
        )}

        {(fairness.overall_fairness_score != null || fairness.confidence) && (
          <>
            <SectionLabel>公平性评估</SectionLabel>
            <InfoGrid
              items={[
                fairness.overall_fairness_score != null
                  ? {
                      label: '公平性总评',
                      value: `${Number(fairness.overall_fairness_score).toFixed(1)}/${str(fairness.max ?? 10)}`,
                    }
                  : null,
                fairness.confidence
                  ? { label: '置信度', value: str(fairness.confidence) }
                  : null,
              ].filter(Boolean) as { label: string; value: ReactNode }[]}
            />
            {asArray(fairness.key_concerns).length > 0 && (
              <DCard title="关键关注点">
                {asArray(fairness.key_concerns).map((c, i) => (
                  <p key={i}>{str(c)}</p>
                ))}
              </DCard>
            )}
            {asArray(fairness.recommendations).length > 0 && (
              <DCard title="建议">
                {asArray(fairness.recommendations).map((c, i) => (
                  <p key={i}>{str(c)}</p>
                ))}
              </DCard>
            )}
          </>
        )}

        {underest.length > 0 && (
          <>
            <SectionLabel color="#1565c0">偏低误差 — 得分可能低估</SectionLabel>
            {underest.map((item, i) => (
              <DCard key={i} borderColor="#1565c0">
                <p>
                  <strong>{str(item.dimension)}</strong> ({str(item.current_score)})
                </p>
                <p>{str(item.score_may_be_low_because)}</p>
                {item.evidence != null && (
                  <p className="text-[0.73rem] text-[#888]">证据: {str(item.evidence)}</p>
                )}
                {item.estimated_true_range != null && (
                  <p className="text-[0.73rem] text-[#1565c0]">
                    估计范围: {str(item.estimated_true_range)}
                  </p>
                )}
              </DCard>
            ))}
          </>
        )}

        {overest.length > 0 && (
          <>
            <SectionLabel color="#c62828">偏高误差 — 得分可能高估</SectionLabel>
            {overest.map((item, i) => (
              <DCard key={i} borderColor="#c62828">
                <p>
                  <strong>{str(item.dimension)}</strong> ({str(item.current_score)}){' '}
                  <Tag tone="red">风险: {str(item.risk_level || 'Medium')}</Tag>
                </p>
                <p>{str(item.score_may_be_high_because)}</p>
                {item.evidence != null && (
                  <p className="text-[0.73rem] text-[#888]">证据: {str(item.evidence)}</p>
                )}
              </DCard>
            ))}
          </>
        )}

        {improvePath.length > 0 && (
          <>
            <SectionLabel color="#2e7d32">提升路径</SectionLabel>
            {improvePath.map((item, i) => (
              <DCard key={i} borderColor="#2e7d32">
                <p>
                  <strong>{str(item.dimension)}</strong> ({str(item.current_score)})
                </p>
                {(item.gap_to_close || item.suggestion || item.description) != null && (
                  <p>{str(item.gap_to_close || item.suggestion || item.description)}</p>
                )}
                {item.realistic != null && (
                  <p className="text-[#2e7d32]">
                    可行性: {item.realistic ? '可行' : '不确定'}
                  </p>
                )}
              </DCard>
            ))}
          </>
        )}

        {declineRisks.length > 0 && (
          <>
            <SectionLabel color="#c62828">下降风险</SectionLabel>
            {declineRisks.map((item, i) => (
              <DCard key={i} borderColor="#c62828">
                <p>
                  <strong>{str(item.dimension)}</strong>{' '}
                  <Tag tone="red">风险: {str(item.severity || 'Medium')}</Tag>
                </p>
                {item.trigger != null && <p>触发条件: {str(item.trigger)}</p>}
                {item.risk_drop_to_tier != null && (
                  <p>可能跌至: {str(item.risk_drop_to_tier)}</p>
                )}
              </DCard>
            ))}
          </>
        )}

        {(asArray(dataRel.verified_claims).length > 0
          || asArray(dataRel.inferred_claims).length > 0
          || asArray(dataRel.missing_data).length > 0) && (
          <>
            <SectionLabel>依据声明</SectionLabel>
            <DCard>
              {asArray(dataRel.verified_claims).length > 0 && (
                <div className="mb-2">
                  <p className="text-[#2e7d32] font-semibold">已验证</p>
                  {asArray(dataRel.verified_claims).map((c, i) => (
                    <p key={i}>✓ {str(c)}</p>
                  ))}
                </div>
              )}
              {asArray(dataRel.inferred_claims).length > 0 && (
                <div className="mb-2">
                  <p className="text-[#e65100] font-semibold">推断</p>
                  {asArray(dataRel.inferred_claims).map((c, i) => (
                    <p key={i}>~ {str(c)}</p>
                  ))}
                </div>
              )}
              {asArray(dataRel.missing_data).length > 0 && (
                <div>
                  <p className="text-[#999] font-semibold">缺失</p>
                  {asArray(dataRel.missing_data).map((c, i) => (
                    <p key={i}>? {str(c)}</p>
                  ))}
                </div>
              )}
            </DCard>
          </>
        )}

        {biasKeys.length === 0
          && underest.length === 0
          && overest.length === 0
          && improvePath.length === 0
          && !biasExp.current_assessment
          && fairness.overall_fairness_score == null && (
            <p className="text-[#aaa] text-[0.8rem] italic py-2">无偏差分析数据</p>
          )}
      </Collapsible>

      {/* 面板 4 */}
      <Collapsible title="复现性与过程回溯 (Reproducibility)">
        <SectionLabel>数据获取痕迹</SectionLabel>
        <DCard>
          <p>
            <strong>DOI</strong>: {str(report.doi || meta.doi, '未提取到')}
          </p>
          <p>
            <strong>标题提取</strong>: {str(report.title || meta.title, '未提取')}
            {meta.title && report.title && meta.title !== report.title && (
              <span className="text-[#e65100]"> (元数据修正: {str(meta.title)})</span>
            )}
          </p>
          {meta.openalex_id != null && (
            <p>
              <strong>OpenAlex ID</strong>: {str(meta.openalex_id)}
            </p>
          )}
          {meta.type != null && (
            <p>
              <strong>文献类型</strong>: {str(meta.type)}
            </p>
          )}
          {meta.publication_date != null && (
            <p>
              <strong>出版日期</strong>: {str(meta.publication_date)}
            </p>
          )}
          {meta.open_access != null && (
            <p>
              <strong>开放获取</strong>: {meta.open_access ? '是' : '否'}
            </p>
          )}
          {meta.referenced_works_count != null && (
            <p>
              <strong>参考文献数</strong>: {str(meta.referenced_works_count)}
            </p>
          )}
          <p>
            <strong>Job ID</strong>: {jobId}
          </p>
        </DCard>

        <SectionLabel>PDF 处理</SectionLabel>
        <DCard>
          <p>
            <strong>文件</strong>: {str(report.pdf_file, '未知')}
          </p>
          <p>
            <strong>元数据来源</strong>: OpenAlex API (按 DOI 查询)
          </p>
        </DCard>

        <SectionLabel>引用网络数据来源</SectionLabel>
        <DCard>
          <p>引用次数: 来自 OpenAlex cited_by_count</p>
          {citationGraph.data_source != null && (
            <p>网络数据: {str(citationGraph.data_source)}</p>
          )}
          {asRecord(citationGraph.network_size).source != null && (
            <p>网络规模: {str(asRecord(citationGraph.network_size).source)}</p>
          )}
        </DCard>

        {dims.length > 0 && (
          <>
            <SectionLabel>评分维度固定参数</SectionLabel>
            <DCard>
              {dims.map((d) => (
                <p key={d.name}>
                  {d.name}: max = {d.max}
                </p>
              ))}
            </DCard>
          </>
        )}

        <SectionLabel>处理日志摘要</SectionLabel>
        <DCard>
          {jobLogs.length === 0 ? (
            <span className="text-[#aaa] italic">暂无日志</span>
          ) : (
            <div className="max-h-48 overflow-y-auto font-mono text-[0.7rem] space-y-0.5">
              {jobLogs.slice(-50).map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          )}
        </DCard>

        <p className="text-[0.75rem] text-[#888] pt-1">
          完整原始数据可通过「下载报告」获取 impact_report.json。
        </p>
      </Collapsible>
    </div>
  );
}
