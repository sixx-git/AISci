import { useCallback, useEffect, useState } from 'react';
import { Download, Eye, FileDown, FileText, GitBranch, Layers, Bot } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { ContextEngineeringDrawer } from '@/components/overview/ContextEngineeringDrawer';
import { RunFeedbackDrawer } from '@/components/overview/RunFeedbackDrawer';
import { StageOutputsDrawer } from '@/components/overview/StageOutputsDrawer';
import type { PipelineProgressNode } from '@/components/PipelineProgress';
import { pipelineService } from '@/services/pipelineService';
import { reportService } from '@/services/reportService';
import { iterativeExperimentService } from '@/services/iterativeExperimentService';
import { literatureService } from '@/services/literatureService';
import { triggerBlobDownload, triggerJsonDownload } from '@/lib/downloadBlob';
import { buildReportDownloadFilename } from '@/lib/reportExport';
import {
  appendAuxiliaryWhitelist,
  buildContextSnapshot,
  buildRunFeedbackSnapshot,
  buildStageOutputSnapshots,
  collectLiteratureDocumentIds,
  isExperimentStageKey,
  type SnapshotItem,
  type StageOutputSnapshot,
} from '@/lib/overviewSubmission';
import {
  buildIterationHistoryExport,
  collectChartRefs,
  iterationChartHref,
  safeDownloadName,
  type ChartDownloadRef,
} from '@/lib/iterationExport';
import { mapStageExecutionStatus } from '@/lib/pipelineProgressNodes';
import { getErrorMessage } from '@/lib/errors';
import { useToast } from '@/hooks/useToast';
import type { PipelineRunDetail, ProjectOverview, ReportData } from '@/types';
import type { IterativeExperiment } from '@/types/iterativeExperiment';

interface OverviewSubmissionCardProps {
  project: ProjectOverview;
  researchQuestion: string;
  latestRunId: string | null;
  latestRunStatus?: string | null;
  pipelineNodes: PipelineProgressNode[];
  onGoWorkflow: () => void;
}

function StatusPill({ ready, readyLabel, idleLabel }: {
  ready: boolean;
  readyLabel: string;
  idleLabel: string;
}) {
  return (
    <span
      className={
        ready
          ? 'text-xs px-1.5 py-0.5 rounded-bp bg-bp-green/15 text-bp-green'
          : 'text-xs px-1.5 py-0.5 rounded-bp bg-bp-panel text-bp-muted'
      }
    >
      {ready ? readyLabel : idleLabel}
    </span>
  );
}

function runStatusLabel(status?: string | null): { ready: boolean; label: string } {
  const key = (status || '').toLowerCase();
  if (key === 'completed' || key === 'success') return { ready: true, label: '已完成' };
  if (key === 'running' || key === 'processing') return { ready: true, label: '运行中' };
  if (key === 'failed' || key === 'error') return { ready: true, label: '已失败' };
  return { ready: false, label: '未开始' };
}

export function OverviewSubmissionCard({
  project,
  researchQuestion,
  latestRunId,
  latestRunStatus,
  pipelineNodes,
  onGoWorkflow,
}: OverviewSubmissionCardProps) {
  const { message: alertMsg, showAlert } = useToast();
  const [drawer, setDrawer] = useState<'context' | 'run' | 'stages' | null>(null);
  const [stageFocus, setStageFocus] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<PipelineRunDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [report, setReport] = useState<ReportData | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<IterativeExperiment[]>([]);
  const [chunkExtras, setChunkExtras] = useState<SnapshotItem[]>([]);

  const hasRun = Boolean(latestRunId);
  const pdfReady = Boolean(report?.id && report.pdfSuccess);
  const runLabel = runStatusLabel(latestRunStatus);

  useEffect(() => {
    setRunDetail(null);
  }, [latestRunId]);

  useEffect(() => {
    if (!latestRunId) return undefined;
    let cancelled = false;
    pipelineService.getRunDetail(latestRunId).then((res) => {
      if (cancelled) return;
      if (res.code === 200 && res.data) setRunDetail(res.data);
    }).catch(() => {
      /* 预取失败时保留空态，点击预览会再试 */
    });
    return () => { cancelled = true; };
  }, [latestRunId]);

  useEffect(() => {
    let cancelled = false;
    reportService.getLatest(project.id).then((data) => {
      if (!cancelled) setReport(data);
    }).catch(() => {
      if (!cancelled) setReport(null);
    });
    return () => { cancelled = true; };
  }, [project.id, latestRunId]);

  useEffect(() => {
    let cancelled = false;
    iterativeExperimentService.list(project.id).then((res) => {
      if (!cancelled) setExperiments(res.experiments || []);
    }).catch(() => {
      if (!cancelled) setExperiments([]);
    });
    return () => { cancelled = true; };
  }, [project.id, latestRunId]);

  const ensureRunDetail = useCallback(async (): Promise<PipelineRunDetail | null> => {
    if (!latestRunId) return null;
    if (runDetail?.run_id === latestRunId) return runDetail;
    setLoadingDetail(true);
    try {
      const res = await pipelineService.getRunDetail(latestRunId);
      if (res.code === 200 && res.data) {
        setRunDetail(res.data);
        return res.data;
      }
      showAlert(res.message || '加载运行详情失败');
      return null;
    } catch (e) {
      showAlert(getErrorMessage(e, '加载运行详情失败'));
      return null;
    } finally {
      setLoadingDetail(false);
    }
  }, [latestRunId, runDetail, showAlert]);

  const fetchChunkExtras = useCallback(async (detail: PipelineRunDetail | null): Promise<SnapshotItem[]> => {
    let docIds = collectLiteratureDocumentIds(detail);
    if (docIds.length === 0) {
      try {
        const lit = await literatureService.getProjectLiterature(project.id, undefined, 1, 6);
        if (lit.code === 200) {
          docIds = (lit.data?.items || []).map((d) => d.id).filter(Boolean);
        }
      } catch {
        /* 文献列表失败时仍尝试已有 citation_map */
      }
    }
    const extras: SnapshotItem[] = [];
    for (const docId of docIds.slice(0, 6)) {
      try {
        const res = await literatureService.getDocumentChunks(docId, 1, 8);
        const items = res.code === 200 ? (res.data?.items || []) : [];
        for (const raw of items) {
          const rec = (raw && typeof raw === 'object') ? raw as Record<string, unknown> : null;
          if (!rec) continue;
          const title = String(rec.content || rec.content_preview || '').trim();
          if (!title) continue;
          extras.push({
            title,
            source: '检索 chunk',
            detail: `document_id=${docId} · chunk=${String(rec.id || rec.chunk_index || '')}`,
            id: String(rec.id || ''),
            tier: 'auxiliary',
          });
        }
      } catch {
        /* 单篇文档切片失败不影响其余 */
      }
    }
    setChunkExtras(extras);
    return extras;
  }, [project.id]);

  const openDrawer = async (kind: 'context' | 'run' | 'stages', focus?: string) => {
    if (!hasRun) {
      showAlert('请先在智能体工作流中运行 Pipeline');
      return;
    }
    setStageFocus(focus || null);
    setDrawer(kind);
    const detail = await ensureRunDetail();
    if (kind === 'context') {
      await fetchChunkExtras(detail);
    }
  };

  const handleDownloadContext = async () => {
    if (!hasRun) {
      showAlert('请先运行 Pipeline 后再下载上下文');
      return;
    }
    setBusy('context');
    try {
      const detail = await ensureRunDetail();
      const extras = await fetchChunkExtras(detail);
      const snapshot = appendAuxiliaryWhitelist(
        buildContextSnapshot(project, detail, researchQuestion),
        extras,
      );
      triggerJsonDownload(snapshot, `context_bundle_${project.id.slice(0, 8)}.json`);
      showAlert('上下文工程 JSON 已下载');
    } catch (e) {
      showAlert(getErrorMessage(e, '下载失败'));
    } finally {
      setBusy(null);
    }
  };

  const handleDownloadAudit = async () => {
    if (!latestRunId) {
      showAlert('请先运行 Pipeline 后再下载审计包');
      return;
    }
    setBusy('audit');
    try {
      const res = await pipelineService.exportAuditChain(latestRunId);
      if (res.code === 200 && res.data) {
        triggerJsonDownload(res.data, `audit_${latestRunId.slice(0, 8)}.json`);
        showAlert('审计包已下载');
      } else {
        showAlert(res.message || '审计包导出失败');
      }
    } catch (e) {
      showAlert(getErrorMessage(e, '审计包导出失败'));
    } finally {
      setBusy(null);
    }
  };

  const handleDownloadPdf = async () => {
    if (!report?.id || !pdfReady) {
      showAlert('暂无可用的报告 PDF');
      return;
    }
    setBusy('pdf');
    try {
      const blob = await reportService.download(report.id, 'pdf');
      triggerBlobDownload(blob, buildReportDownloadFilename(report.title, 'pdf'));
      showAlert('报告 PDF 已下载');
    } catch (e) {
      showAlert(getErrorMessage(e, 'PDF 下载失败'));
    } finally {
      setBusy(null);
    }
  };

  const handleDownloadStage = (stage: { key: string; label: string; output: Record<string, unknown> }) => {
    triggerJsonDownload(
      {
        project_id: project.id,
        run_id: latestRunId,
        stage: stage.key,
        label: stage.label,
        output: stage.output,
      },
      `stage_${stage.key}_${project.id.slice(0, 8)}.json`,
    );
    showAlert(`${stage.label} JSON 已下载`);
  };

  const handleDownloadAllStages = async () => {
    if (!hasRun) {
      showAlert('请先运行 Pipeline 后再下载');
      return;
    }
    setBusy('stages');
    try {
      const detail = await ensureRunDetail();
      const snapshots = buildStageOutputSnapshots(detail).filter((s) => !isExperimentStageKey(s.key));
      triggerJsonDownload(
        {
          project_id: project.id,
          run_id: latestRunId,
          generated_at: new Date().toISOString(),
          stages: snapshots.map((s) => ({
            key: s.key,
            label: s.label,
            status: s.status,
            model: s.model,
            token_count: s.token_count,
            highlights: s.highlights,
            output: s.output,
          })),
        },
        `stage_outputs_${project.id.slice(0, 8)}.json`,
      );
      showAlert('全部阶段产出已下载');
    } catch (e) {
      showAlert(getErrorMessage(e, '下载失败'));
    } finally {
      setBusy(null);
    }
  };

  const handleDownloadIterationHistory = () => {
    if (experiments.length === 0) {
      showAlert('当前项目还没有迭代实验记录');
      return;
    }
    const payload = {
      project_id: project.id,
      ...buildIterationHistoryExport(experiments),
    };
    triggerJsonDownload(payload, `iteration_history_${project.id.slice(0, 8)}.json`);
    showAlert('迭代历史已下载（含实验方案、脚本、结果与分析报告）');
  };

  const handleDownloadIterationCharts = async (refs?: ChartDownloadRef[]) => {
    const list = refs && refs.length > 0 ? refs : collectChartRefs(experiments);
    if (list.length === 0) {
      showAlert('暂无可下载的可视化图片');
      return;
    }
    setBusy('charts');
    try {
      let ok = 0;
      for (const chart of list) {
        try {
          const blob = await iterativeExperimentService.downloadChart(chart.path);
          triggerBlobDownload(
            blob,
            `${safeDownloadName(chart.experimentTitle)}_iter${chart.iteration}_${safeDownloadName(chart.name)}`,
          );
          ok += 1;
          await new Promise((r) => window.setTimeout(r, 250));
        } catch {
          /* 单张图片失败继续其余 */
        }
      }
      showAlert(ok > 0 ? `已下载 ${ok} 张可视化图片` : '可视化图片下载失败');
    } finally {
      setBusy(null);
    }
  };

  const contextSnapshot = runDetail
    ? appendAuxiliaryWhitelist(
      buildContextSnapshot(project, runDetail, researchQuestion),
      chunkExtras,
    )
    : null;
  const runSnapshot = runDetail
    ? buildRunFeedbackSnapshot(project, runDetail)
    : null;
  const stageSnapshots = runDetail
    ? buildStageOutputSnapshots(runDetail).filter((s) => !isExperimentStageKey(s.key))
    : [];
  const agentPlaceholders: StageOutputSnapshot[] = [
    { key: 'problem_understanding', label: '问题理解', status: 'pending', highlights: [], output: {} },
    { key: 'literature_mining', label: '文献挖掘', status: 'pending', highlights: [], output: {} },
    { key: 'knowledge_gap', label: '知识缺口', status: 'pending', highlights: [], output: {} },
    { key: 'hypothesis_generation', label: '假设生成', status: 'pending', highlights: [], output: {} },
    { key: 'hypothesis_review', label: '假设评估', status: 'pending', highlights: [], output: {} },
    { key: 'report_generation', label: '报告生成', status: 'pending', highlights: [], output: {} },
  ];
  const agentRows = hasRun ? stageSnapshots : agentPlaceholders;
  const iterationCount = experiments.reduce((n, e) => n + (e.iterations?.length || 0), 0);
  const chartRefs = collectChartRefs(experiments);
  const shownCharts = chartRefs.slice(0, 4);

  return (
    <>
      <Card
        title="提交材料快捷入口"
        subtitle="对照赛道一模板 P7 上下文工程、P12 完整运行与反馈"
      >
        {!hasRun && (
          <p className="text-xs text-bp-muted mb-4">
            当前项目尚未运行 Pipeline。
            <button
              type="button"
              onClick={onGoWorkflow}
              className="text-bp-cyan hover:underline ml-1"
            >
              进入智能体工作流
            </button>
          </p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-bp border border-bp-border bg-bp-base/40 p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2 min-w-0">
                <Layers className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-bp-text">上下文工程</p>
                  <p className="text-xs text-bp-muted mt-1 leading-relaxed">
                    科学问题、证据白名单、反对证据、约束与反馈如何进入 Qwen
                  </p>
                </div>
              </div>
              <StatusPill ready={hasRun} readyLabel="已就绪" idleLabel="尚未运行" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Eye className="w-3.5 h-3.5" />}
                disabled={!hasRun}
                onClick={() => void openDrawer('context')}
              >
                预览
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Download className="w-3.5 h-3.5" />}
                disabled={!hasRun || busy === 'context'}
                isLoading={busy === 'context'}
                onClick={() => void handleDownloadContext()}
              >
                下载 JSON
              </Button>
            </div>
          </div>

          <div className="rounded-bp border border-bp-border bg-bp-base/40 p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2 min-w-0">
                <GitBranch className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-bp-text">运行与反馈</p>
                  <p className="text-xs text-bp-muted mt-1 leading-relaxed">
                    七阶段流程、反馈回流、自动/人工处理及审计记录
                  </p>
                </div>
              </div>
              <StatusPill ready={runLabel.ready} readyLabel={runLabel.label} idleLabel="未开始" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Eye className="w-3.5 h-3.5" />}
                disabled={!hasRun}
                onClick={() => void openDrawer('run')}
              >
                预览
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<FileDown className="w-3.5 h-3.5" />}
                disabled={!hasRun || busy === 'audit'}
                isLoading={busy === 'audit'}
                onClick={() => void handleDownloadAudit()}
              >
                下载审计包
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<FileText className="w-3.5 h-3.5" />}
                disabled={!pdfReady || busy === 'pdf'}
                isLoading={busy === 'pdf'}
                onClick={() => void handleDownloadPdf()}
                title={pdfReady ? '下载最新报告 PDF' : '暂无可用 PDF'}
              >
                下载 PDF
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-5 pt-5 border-t border-bp-border">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2 min-w-0">
              <Bot className="w-4 h-4 text-bp-cyan shrink-0" />
              <div>
                <p className="text-sm font-medium text-bp-text">各阶段智能体产出</p>
                <p className="text-xs text-bp-muted mt-0.5">
                  问题理解、文献挖掘、知识缺口、假设、评审与报告的结构化结果；迭代实验单独提供历史下载
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Eye className="w-3.5 h-3.5" />}
                disabled={!hasRun}
                onClick={() => void openDrawer('stages')}
              >
                预览全部
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Download className="w-3.5 h-3.5" />}
                disabled={!hasRun || busy === 'stages'}
                isLoading={busy === 'stages'}
                onClick={() => void handleDownloadAllStages()}
              >
                下载全部 JSON
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {hasRun && stageSnapshots.length === 0 && (
              <p className="text-xs text-bp-muted py-2">正在读取各阶段输出…</p>
            )}
            {agentRows.map((stage) => {
              const mapped = mapStageExecutionStatus(stage.status);
              const ready = mapped === 'completed' || mapped === 'error';
              return (
                <div
                  key={stage.key}
                  className="flex flex-wrap items-center gap-2 rounded-bp border border-bp-border bg-bp-base/40 px-3 py-2"
                >
                  <span className="text-sm text-bp-text flex-1 min-w-[8rem]">{stage.label}</span>
                  <span className="text-xs text-bp-muted">
                    {mapped === 'completed' ? '已完成' : mapped === 'running' ? '运行中' : mapped === 'error' ? '失败' : '未开始'}
                    {stage.highlights.length > 0 ? ` · ${stage.highlights.length} 条要点` : ''}
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon={<Eye className="w-3.5 h-3.5" />}
                    disabled={!hasRun}
                    onClick={() => void openDrawer('stages', stage.key)}
                  >
                    预览
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon={<Download className="w-3.5 h-3.5" />}
                    disabled={!ready || Object.keys(stage.output).length === 0}
                    onClick={() => handleDownloadStage(stage)}
                  >
                    下载
                  </Button>
                </div>
              );
            })}
            <div className="rounded-bp border border-bp-border bg-bp-base/40 px-3 py-2 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-bp-text flex-1 min-w-[8rem]">迭代实验</span>
                <span className="text-xs text-bp-muted">
                  {experiments.length === 0
                    ? '未开始'
                    : `${experiments.length} 组 · ${iterationCount} 轮`}
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  icon={<Download className="w-3.5 h-3.5" />}
                  disabled={experiments.length === 0}
                  onClick={handleDownloadIterationHistory}
                >
                  下载迭代历史
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  icon={<FileDown className="w-3.5 h-3.5" />}
                  disabled={chartRefs.length === 0 || busy === 'charts'}
                  isLoading={busy === 'charts'}
                  onClick={() => void handleDownloadIterationCharts()}
                >
                  下载全部图片{chartRefs.length > 0 ? `（${chartRefs.length}）` : ''}
                </Button>
              </div>
              {shownCharts.length > 0 && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span className="text-bp-muted">可视化图片：</span>
                  {shownCharts.map((chart) => (
                    <a
                      key={`${chart.experimentId}-${chart.iteration}-${chart.path}`}
                      href={iterationChartHref({ path: chart.path, name: chart.name })}
                      download={safeDownloadName(chart.name)}
                      className="text-bp-cyan hover:underline truncate max-w-[14rem]"
                      title={`第 ${chart.iteration} 轮 · ${chart.name}`}
                    >
                      {`第${chart.iteration}轮 ${chart.name}`}
                    </a>
                  ))}
                  {chartRefs.length > shownCharts.length && (
                    <button
                      type="button"
                      className="text-bp-cyan hover:underline"
                      onClick={() => void handleDownloadIterationCharts(chartRefs.slice(shownCharts.length))}
                    >
                      其余 {chartRefs.length - shownCharts.length} 张一并下载
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>

      <ContextEngineeringDrawer
        open={drawer === 'context'}
        loading={loadingDetail && !contextSnapshot}
        snapshot={contextSnapshot}
        onClose={() => setDrawer(null)}
      />
      <RunFeedbackDrawer
        open={drawer === 'run'}
        loading={loadingDetail && !runSnapshot}
        snapshot={runSnapshot}
        pipelineNodes={pipelineNodes}
        onClose={() => setDrawer(null)}
      />
      <StageOutputsDrawer
        open={drawer === 'stages'}
        loading={loadingDetail && stageSnapshots.length === 0}
        stages={stageSnapshots}
        focusKey={stageFocus}
        onClose={() => setDrawer(null)}
        onDownloadStage={handleDownloadStage}
      />

      {alertMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-lg bg-bp-panel border border-bp-border text-sm text-bp-text shadow-lg animate-fade-in z-50">
          {alertMsg}
        </div>
      )}
    </>
  );
}
