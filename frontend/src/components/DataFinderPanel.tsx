import { useState, useEffect, useCallback } from 'react';
import {
  Search, FileSpreadsheet, Link2, Image, GitMerge, Download,
  Loader2, AlertCircle, Database, CheckCircle2, Map, Workflow, RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type DataFinderResult } from '@/services/dataFinderService';
import { FigureReviewPanel } from '@/components/FigureReviewPanel';
import { ExternalCandidateTodoPanel } from '@/components/ExternalCandidateTodoPanel';

interface DataFinderPanelProps {
  projectId: string;
  projectMode?: string;
  researchQuestion?: string;
  onImported?: () => void;
}

export function DataFinderPanel({
  projectId,
  projectMode,
  researchQuestion = '',
  onImported,
}: DataFinderPanelProps) {
  const [result, setResult] = useState<DataFinderResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hypothesis, setHypothesis] = useState('');

  const loadResults = useCallback(async () => {
    try {
      const res = await dataFinderService.getResults(projectId);
      if (res.code === 200 && res.data) {
        setResult(res.data);
      }
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const runGapEnrich = async () => {
    setLoading(true);
    setAction('gap');
    setError(null);
    try {
      const res = await dataFinderService.gapEnrich(projectId);
      if (res.code === 200 && res.data?.results) {
        setResult(res.data.results);
      } else {
        setError(res.message || 'Gap 补搜失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Gap 补搜失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const runAcquire = async () => {
    setLoading(true);
    setAction('acquire');
    setError(null);
    try {
      const res = await dataFinderService.acquire({
        project_id: projectId,
        research_question: researchQuestion,
        selected_hypothesis: hypothesis,
        project_mode: projectMode,
        auto_import: true,
      });
      if (res.code === 200 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '采集失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '采集失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const runSearch = async () => {
    setLoading(true);
    setAction('search');
    setError(null);
    try {
      const res = await dataFinderService.search({
        project_id: projectId,
        research_question: researchQuestion,
        selected_hypothesis: hypothesis,
        project_mode: projectMode,
      });
      if (res.code === 200 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '搜索失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '搜索失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const runExtract = async () => {
    setLoading(true);
    setAction('extract');
    setError(null);
    try {
      const res = await dataFinderService.extractTables(projectId);
      if (res.code === 200 && res.data) {
        setResult(res.data);
        await dataFinderService.alignSchema(projectId);
        const merged = await dataFinderService.merge(projectId);
        if (merged.code === 200 && merged.data) setResult(merged.data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '抽取失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleImport = async () => {
    setLoading(true);
    setAction('import');
    try {
      const res = await dataFinderService.importToDataset(projectId, result?.merged?.merge_id);
      if (res.code === 200) {
        onImported?.();
      } else {
        setError(res.message || '导入失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '导入失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleDownloadBundle = async () => {
    setLoading(true);
    setAction('bundle');
    setError(null);
    try {
      const blob = await dataFinderService.downloadBundle(projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_bundle_${projectId.slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bundle 下载失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="p-4 border-bp-cyan/20 bg-bp-cyan-tint">
        <h3 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-bp-cyan" />
          多源科学数据查找与整合
        </h3>
        <p className="text-xs text-bp-muted mb-3">
          从已导入 PDF、论文链接与开放数据平台查找数据，抽取表格并输出可下载 CSV（含 provenance）。
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          <input
            type="text"
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            placeholder="可选：当前假设（用于细化数据需求）"
            className="flex-1 min-w-[200px] input-field text-sm"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" size="sm" icon={<Workflow className="w-4 h-4" />} onClick={runAcquire} isLoading={loading && action === 'acquire'}>
            一键多源采集
          </Button>
          <Button variant="secondary" size="sm" icon={<RefreshCw className="w-4 h-4" />} onClick={runGapEnrich} isLoading={loading && action === 'gap'} disabled={!result?.coverage_report?.gap_enrichment_recommended && !result?.coverage_report}>
            Gap 补搜
          </Button>
          <Button variant="secondary" size="sm" icon={<Search className="w-4 h-4" />} onClick={runSearch} isLoading={loading && action === 'search'}>
            查找数据源
          </Button>
          <Button variant="secondary" size="sm" icon={<FileSpreadsheet className="w-4 h-4" />} onClick={runExtract} isLoading={loading && action === 'extract'}>
            抽取 PDF 表格
          </Button>
          {result?.merged?.merged_csv_path && (
            <>
              <Button variant="secondary" size="sm" icon={<Database className="w-4 h-4" />} onClick={handleImport} isLoading={loading && action === 'import'}>
                加入项目数据集
              </Button>
            </>
          )}
        </div>
        {error && (
          <p className="text-xs text-danger-400 mt-2 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> {error}
          </p>
        )}
      </Card>

      {result?.data_acquisition?.steps && result.data_acquisition.steps.length > 0 && (
        <Card className="p-4 border-teal-500/20 bg-teal-500/5">
          <h4 className="text-sm font-semibold text-teal-200 mb-3 flex items-center gap-1.5">
            <Workflow className="w-4 h-4" />
            采集流水线进度
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {result.data_acquisition.steps.map((step) => {
              const detail = result.data_acquisition?.step_details?.[step];
              const skipped = detail?.skipped;
              const labelMap: Record<string, string> = {
                discover: '发现',
                fetch_supplementary: '补充材料',
                fetch_external: '外部数据',
                extract: '抽取',
                align: '对齐',
                merge: '合并',
              };
              return (
                <div
                  key={step}
                  className={`text-xs p-2 rounded border ${
                    skipped
                      ? 'border-bp-border bg-bp-base/50 text-bp-muted'
                      : 'border-teal-500/30 bg-teal-500/10 text-teal-200'
                  }`}
                >
                  <div className="font-medium">{labelMap[step] || step}</div>
                  {skipped ? (
                    <span className="text-[10px] text-bp-muted">已跳过</span>
                  ) : (
                    <span className="text-[10px] text-bp-muted">
                      {detail?.tables != null && `表 ${detail.tables}`}
                      {detail?.rows != null && ` · 行 ${detail.rows}`}
                      {detail?.imported != null && ` · 导入 ${detail.imported}`}
                      {detail?.candidates != null && ` · 候选 ${detail.candidates}`}
                      {detail?.duration_ms != null && ` · ${detail.duration_ms}ms`}
                      {detail?.error_code && (
                        <span className="text-danger-400"> · {detail.error_code}</span>
                      )}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          {result.data_acquisition.stats && (
            <p className="text-[10px] text-bp-muted mt-2">
              外部候选 {result.data_acquisition.stats.external_candidates ?? 0} ·
              表格 {result.data_acquisition.stats.tables ?? 0} ·
              合并行 {result.data_acquisition.stats.merged_rows ?? '—'}
              {result.data_acquisition.stats.total_duration_ms != null && (
                <span> · 耗时 {result.data_acquisition.stats.total_duration_ms}ms</span>
              )}
              {result.data_acquisition.stats.release_gate_passed != null && (
                <span className={result.data_acquisition.stats.release_gate_passed ? ' text-bp-green' : ' text-bp-yellow'}>
                  {' '}· Release Gate {result.data_acquisition.stats.release_gate_passed ? '通过' : '未通过'}
                </span>
              )}
            </p>
          )}
        </Card>
      )}

      {result?.data_spec && (
        <Card className="p-4 border-indigo-500/20 bg-indigo-500/5">
          <h4 className="text-sm font-semibold text-indigo-200 mb-2">DataSpec · 数据需求</h4>
          <p className="text-xs text-bp-muted mb-2">
            场景 {result.data_spec.scenario || 'general'}
            {result.data_spec.merge_strategy_hint && (
              <span className="text-bp-muted"> · 合并策略 {result.data_spec.merge_strategy_hint}</span>
            )}
          </p>
          {(result.data_spec.entities_of_interest?.length ?? 0) > 0 && (
            <p className="text-[10px] text-bp-muted mb-1">
              实体字段: {result.data_spec.entities_of_interest!.join(', ')}
            </p>
          )}
          <div className="flex flex-wrap gap-1">
            {(result.data_spec.target_variables || result.data_requirements?.expected_metrics || []).map((m) => (
              <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-bp-panel text-bp-muted border border-bp-border">{m}</span>
            ))}
          </div>
        </Card>
      )}

      {result?.data_requirements && !result?.data_spec && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2">数据需求理解</h4>
          <p className="text-xs text-bp-muted mb-2">{result.data_requirements.data_need}</p>
          <div className="flex flex-wrap gap-1">
            {(result.data_requirements.expected_metrics || []).map((m) => (
              <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-bp-panel text-bp-muted border border-bp-border">{m}</span>
            ))}
          </div>
        </Card>
      )}

      {result?.text_facts && result.text_facts.length > 0 && (
        <Card className="p-4 border-bp-purple/20 bg-bp-purple/5">
          <h4 className="text-sm font-semibold text-bp-purple mb-2">正文数值事实 L1 ({result.text_facts.length})</h4>
          <p className="text-[10px] text-bp-muted mb-2">来自 Methods/Results，供假设与实验设计引用（不进 merge CSV）</p>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {result.text_facts.slice(0, 6).map((fact) => (
              <div key={String(fact.fact_id)} className="text-xs text-bp-muted p-2 rounded border border-bp-border">
                <span className="text-bp-purple/80 text-[10px]">{String(fact.section)}</span>
                <p className="line-clamp-2 mt-0.5">{String(fact.sentence)}</p>
                {(fact.matched_targets as string[] | undefined)?.length ? (
                  <p className="text-[10px] text-bp-muted mt-1">
                    命中: {(fact.matched_targets as string[]).join(', ')}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.literature_discovery && (result.literature_discovery.imported ?? 0) > 0 && (
        <Card className="p-4 border-bp-cyan/20 bg-bp-cyan/5">
          <h4 className="text-sm font-semibold text-bp-cyan mb-1 flex items-center gap-1.5">
            <Link2 className="w-4 h-4" />
            自动文献发现
          </h4>
          <p className="text-xs text-bp-muted">
            导入 {result.literature_discovery.imported} 篇 · 来源 {result.literature_discovery.fallback_source}
            {result.literature_discovery.pdf_downloaded != null && (
              <span> · PDF {result.literature_discovery.pdf_downloaded}</span>
            )}
          </p>
        </Card>
      )}

      <ExternalCandidateTodoPanel
        projectId={projectId}
        candidates={result?.external_candidates}
        onUpdated={loadResults}
      />

      {result?.paper_extractions && result.paper_extractions.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
            <Link2 className="w-4 h-4 text-bp-cyan" />
            论文数据链接 ({result.paper_extractions.length})
          </h4>
          <div className="space-y-3">
            {result.paper_extractions.map((pe) => (
              <div key={pe.paper_id} className="p-3 rounded-lg border border-bp-border bg-bp-base/50 text-xs">
                <div className="text-bp-text font-medium mb-1">{pe.source_title}</div>
                <div className="text-bp-muted">
                  表格引用 {pe.tables_detected?.length || 0} · 图引用 {pe.figures_detected?.length || 0} ·
                  置信度 {(pe.confidence * 100).toFixed(0)}%
                </div>
                {pe.data_links?.length > 0 && (
                  <div className="mt-1 text-bp-cyan truncate">{pe.data_links[0]}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.extracted_tables && result.extracted_tables.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
            <FileSpreadsheet className="w-4 h-4 text-bp-green" />
            PDF 表格抽取 ({result.extracted_tables.length})
          </h4>
          <div className="space-y-2">
            {result.extracted_tables.map((t) => (
              <div key={t.table_id} className="p-3 rounded-lg border border-bp-border text-xs text-bp-text">
                <div className="flex justify-between mb-1">
                  <span>{t.caption || t.table_id}</span>
                  <span className="text-bp-green">质量 {(t.quality_score * 100).toFixed(0)}%</span>
                </div>
                <div className="text-bp-muted">
                  {t.source_title} · 第 {t.page} 页 · {t.columns?.length || 0} 列
                  {t.needs_review && <span className="text-bp-yellow ml-2">需复核</span>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.alignments && result.alignments.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
            <Map className="w-4 h-4 text-bp-purple" />
            字段映射
          </h4>
          {result.alignments.map((a) => (
            <div key={a.table_id} className="text-xs text-bp-muted mb-2">
              <span className="text-bp-text">{a.table_id}</span>: {a.standard_columns?.join(', ') || '无标准字段'}
              {a.merge_strategy && (
                <span className="text-indigo-400/80 ml-1">[{a.merge_strategy}]</span>
              )}
              {a.unmatched_columns?.length > 0 && (
                <span className="text-bp-yellow"> · 未匹配: {a.unmatched_columns.join(', ')}</span>
              )}
            </div>
          ))}
        </Card>
      )}

      {result?.figures && result.figures.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
            <Image className="w-4 h-4 text-bp-yellow" />
            图像/图表元信息
          </h4>
          {result.figures.map((f, i) => (
            <div key={i} className="text-xs text-bp-muted mb-2 p-2 rounded border border-bp-border">
              Fig {String(f.figure_number)} · {String(f.chart_type)} · 置信度 {Number(f.extraction_confidence) * 100}%
              {Boolean(f.needs_manual_review) && <span className="text-bp-yellow ml-2">需人工复核（未写入 CSV）</span>}
            </div>
          ))}
        </Card>
      )}

      {result?.provenance && result.provenance.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-bp-text mb-2">Provenance 来源说明</h4>
          <div className="space-y-1 text-xs text-bp-muted">
            {result.provenance.map((p, i) => (
              <div key={i} className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-bp-green shrink-0 mt-0.5" />
                <span>
                  [{p.source_type}] {p.source_title} · page {p.page} · {p.table_or_figure} · {p.extraction_method}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.figures && result.figures.length > 0 && (
        <FigureReviewPanel
          projectId={projectId}
          figures={result.figures}
          onUpdated={loadResults}
        />
      )}

      {result?.coverage_report && (
        <Card className="p-4 border-cyan-500/20 bg-cyan-500/5">
          <h4 className="text-sm font-semibold text-cyan-300 mb-2 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" />
            数据发现完备性 · {result.coverage_report.completeness_score ?? '—'}/100
            {result.coverage_report.data_spec_coverage?.data_spec_score != null && (
              <span className="text-indigo-300 font-normal">
                · DataSpec {result.coverage_report.data_spec_coverage.data_spec_score}/100
              </span>
            )}
          </h4>
          {(result.coverage_report.data_spec_coverage?.checklist || []).length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {result.coverage_report.data_spec_coverage!.checklist!.map((item) => (
                <span
                  key={item.field || item.label}
                  className={`text-[10px] px-2 py-0.5 rounded border ${
                    item.hit
                      ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
                      : 'border-bp-border bg-bp-base text-bp-muted'
                  }`}
                >
                  {item.label || item.field}
                </span>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2 mb-2">
            {(result.coverage_report.domain_checklist || []).map((item) => (
              <span
                key={item.id}
                className={`text-[10px] px-2 py-0.5 rounded border ${
                  item.hit
                    ? 'border-bp-green/30 bg-bp-green/10 text-bp-green'
                    : 'border-bp-border bg-bp-base text-bp-muted'
                }`}
              >
                {item.label}
              </span>
            ))}
          </div>
          {(result.coverage_report.gaps || []).length > 0 && (
            <ul className="text-[10px] text-bp-yellow/90 list-disc list-inside">
              {result.coverage_report.gaps!.slice(0, 4).map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          )}
          {(result.coverage_report.external_import_succeeded ?? 0) > 0 && (
            <p className="text-[10px] text-bp-green mt-2">
              已自动入库外部数据集 {result.coverage_report.external_import_succeeded} 个
            </p>
          )}
          {(result.coverage_report.gap_enrichment_recommended ?? false) && (
            <p className="text-[10px] text-bp-yellow/90 mt-2">
              建议执行 Gap 补搜（完备性 &lt; {result.coverage_report.threshold ?? 70}% 或 DataSpec &lt; {result.coverage_report.data_spec_threshold ?? 60}%）
            </p>
          )}
          {result.gap_enrichment && !result.gap_enrichment.skipped && (
            <p className="text-[10px] text-bp-green mt-2">
              最近 Gap 补搜：{result.gap_enrichment.score_before ?? '—'}→{result.gap_enrichment.score_after ?? '—'} 分
              {result.gap_enrichment.data_spec_score_after != null && (
                <span> · DataSpec {result.gap_enrichment.data_spec_score_after}/100</span>
              )}
            </p>
          )}
          {result.entity_alignment && !result.entity_alignment.skipped && result.entity_alignment.match_rate != null && (
            <p className="text-[10px] text-indigo-400/90 mt-2">
              Entity 跨表匹配率: {(Number(result.entity_alignment.match_rate) * 100).toFixed(0)}%
            </p>
          )}
        </Card>
      )}

      {result?.merged?.row_count ? (
        <Card className="p-4 border-bp-green/20 bg-bp-green/5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h4 className="text-sm font-semibold text-bp-green flex items-center gap-1.5">
                <GitMerge className="w-4 h-4" />
                最终整合 CSV
              </h4>
              <p className="text-xs text-bp-muted mt-1">
                {result.merged.row_count} 行 · merge_id={result.merged.merge_id}
                {result.merged.cleaned_csv_path && (
                  <span className="text-bp-green ml-2">已清洗</span>
                )}
              </p>
              {result.merged.cleaning_report && (
                <p className="text-[10px] text-bp-muted mt-1">
                  清洗: 行 {String(result.merged.cleaning_report.rows_before)}→
                  {String(result.merged.cleaning_report.rows_after)} · 缺失{' '}
                  {String(result.merged.cleaning_report.missing_cells_before)}→
                  {String(result.merged.cleaning_report.missing_cells_after)}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {result.analysis_bundle?.ready && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Download className="w-3.5 h-3.5" />}
                  onClick={handleDownloadBundle}
                  isLoading={loading && action === 'bundle'}
                >
                  下载 Analysis Bundle
                </Button>
              )}
              <span className="text-xs text-bp-muted flex items-center gap-1">
                <Download className="w-3.5 h-3.5" /> 含 data_spec / manifest / provenance
              </span>
            </div>
          </div>
        </Card>
      ) : null}

      {result?.warnings && result.warnings.length > 0 && (
        <div className="text-xs text-bp-yellow space-y-1">
          {result.warnings.map((w, i) => (
            <p key={i}>⚠ {w}</p>
          ))}
        </div>
      )}

      {loading && !action && (
        <div className="flex items-center gap-2 text-bp-muted text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> 处理中...
        </div>
      )}
    </div>
  );
}
