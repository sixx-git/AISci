import { useState, useEffect, useCallback } from 'react';
import {
  Search, FileSpreadsheet, Link2, Image, GitMerge, Download,
  Loader2, AlertCircle, Database, CheckCircle2, Map,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type DataFinderResult } from '@/services/dataFinderService';
import { FigureReviewPanel } from '@/components/FigureReviewPanel';

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
      <Card className="p-4 border-primary-500/20 bg-primary-500/5">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-primary-400" />
          多源科学数据查找与整合
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          从已导入 PDF/BibTeX、论文链接与开放数据平台查找数据，抽取表格并输出可下载 CSV（含 provenance）。
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
          <Button variant="primary" size="sm" icon={<Search className="w-4 h-4" />} onClick={runSearch} isLoading={loading && action === 'search'}>
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
          <p className="text-xs text-red-400 mt-2 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> {error}
          </p>
        )}
      </Card>

      {result?.data_requirements && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2">数据需求理解</h4>
          <p className="text-xs text-gray-400 mb-2">{result.data_requirements.data_need}</p>
          <div className="flex flex-wrap gap-1">
            {(result.data_requirements.expected_metrics || []).map((m) => (
              <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-dark-800 text-gray-400 border border-dark-700">{m}</span>
            ))}
          </div>
        </Card>
      )}

      {result?.paper_extractions && result.paper_extractions.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
            <Link2 className="w-4 h-4 text-blue-400" />
            论文数据链接 ({result.paper_extractions.length})
          </h4>
          <div className="space-y-3">
            {result.paper_extractions.map((pe) => (
              <div key={pe.paper_id} className="p-3 rounded-lg border border-dark-700 bg-dark-900/50 text-xs">
                <div className="text-gray-200 font-medium mb-1">{pe.source_title}</div>
                <div className="text-gray-500">
                  表格引用 {pe.tables_detected?.length || 0} · 图引用 {pe.figures_detected?.length || 0} ·
                  置信度 {(pe.confidence * 100).toFixed(0)}%
                </div>
                {pe.data_links?.length > 0 && (
                  <div className="mt-1 text-primary-300 truncate">{pe.data_links[0]}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.extracted_tables && result.extracted_tables.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
            <FileSpreadsheet className="w-4 h-4 text-green-400" />
            PDF 表格抽取 ({result.extracted_tables.length})
          </h4>
          <div className="space-y-2">
            {result.extracted_tables.map((t) => (
              <div key={t.table_id} className="p-3 rounded-lg border border-dark-700 text-xs text-gray-300">
                <div className="flex justify-between mb-1">
                  <span>{t.caption || t.table_id}</span>
                  <span className="text-green-400">质量 {(t.quality_score * 100).toFixed(0)}%</span>
                </div>
                <div className="text-gray-500">
                  {t.source_title} · 第 {t.page} 页 · {t.columns?.length || 0} 列
                  {t.needs_review && <span className="text-amber-400 ml-2">需复核</span>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {result?.alignments && result.alignments.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
            <Map className="w-4 h-4 text-purple-400" />
            字段映射
          </h4>
          {result.alignments.map((a) => (
            <div key={a.table_id} className="text-xs text-gray-400 mb-2">
              <span className="text-gray-300">{a.table_id}</span>: {a.standard_columns?.join(', ') || '无标准字段'}
              {a.unmatched_columns?.length > 0 && (
                <span className="text-amber-400"> · 未匹配: {a.unmatched_columns.join(', ')}</span>
              )}
            </div>
          ))}
        </Card>
      )}

      {result?.figures && result.figures.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
            <Image className="w-4 h-4 text-amber-400" />
            图像/图表元信息
          </h4>
          {result.figures.map((f, i) => (
            <div key={i} className="text-xs text-gray-400 mb-2 p-2 rounded border border-dark-700">
              Fig {String(f.figure_number)} · {String(f.chart_type)} · 置信度 {Number(f.extraction_confidence) * 100}%
              {Boolean(f.needs_manual_review) && <span className="text-amber-400 ml-2">需人工复核（未写入 CSV）</span>}
            </div>
          ))}
        </Card>
      )}

      {result?.provenance && result.provenance.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-semibold text-white mb-2">Provenance 来源说明</h4>
          <div className="space-y-1 text-xs text-gray-400">
            {result.provenance.map((p, i) => (
              <div key={i} className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0 mt-0.5" />
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
          </h4>
          <div className="flex flex-wrap gap-2 mb-2">
            {(result.coverage_report.domain_checklist || []).map((item) => (
              <span
                key={item.id}
                className={`text-[10px] px-2 py-0.5 rounded border ${
                  item.hit
                    ? 'border-green-500/30 bg-green-500/10 text-green-400'
                    : 'border-dark-600 bg-dark-900 text-gray-500'
                }`}
              >
                {item.label}
              </span>
            ))}
          </div>
          {(result.coverage_report.gaps || []).length > 0 && (
            <ul className="text-[10px] text-amber-400/90 list-disc list-inside">
              {result.coverage_report.gaps!.slice(0, 4).map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          )}
          {(result.coverage_report.external_import_succeeded ?? 0) > 0 && (
            <p className="text-[10px] text-emerald-400 mt-2">
              已自动入库外部数据集 {result.coverage_report.external_import_succeeded} 个
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
        <Card className="p-4 border-green-500/20 bg-green-500/5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h4 className="text-sm font-semibold text-green-300 flex items-center gap-1.5">
                <GitMerge className="w-4 h-4" />
                最终整合 CSV
              </h4>
              <p className="text-xs text-gray-400 mt-1">
                {result.merged.row_count} 行 · merge_id={result.merged.merge_id}
                {result.merged.cleaned_csv_path && (
                  <span className="text-emerald-400 ml-2">已清洗</span>
                )}
              </p>
              {result.merged.cleaning_report && (
                <p className="text-[10px] text-gray-500 mt-1">
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
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Download className="w-3.5 h-3.5" /> 含 schema / provenance / README
              </span>
            </div>
          </div>
        </Card>
      ) : null}

      {result?.warnings && result.warnings.length > 0 && (
        <div className="text-xs text-amber-400 space-y-1">
          {result.warnings.map((w, i) => (
            <p key={i}>⚠ {w}</p>
          ))}
        </div>
      )}

      {loading && !action && (
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> 处理中...
        </div>
      )}
    </div>
  );
}
