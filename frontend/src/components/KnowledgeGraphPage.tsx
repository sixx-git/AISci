import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import cytoscape, { type Core } from 'cytoscape';
import {
  Network, Search, RefreshCw, Loader2, AlertCircle, CheckCircle2,
  Trash2, ShieldCheck, Filter, BarChart3, X, BookOpen, GitBranch,
  ZoomIn, ZoomOut, Maximize2, Tag, Download, Layers,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import {
  NEO4J_BG,
  NEO4J_GREEN,
  NEO4J_BORDER,
  NODE_COLORS,
  TYPE_LABELS_ZH,
  ensureFcoseRegistered,
  getEducationViewPreset,
  applyViewPresetToGraph,
  buildGraphElements,
  getKgStylesheets,
  getKgLayout,
  syncGraphLabels,
  focusCommunityOnCanvas,
  exportGraphPng,
  type LabelDisplayMode,
} from '@/components/kgGraphConfig';
import knowledgeGraphService, {
  type KgEdge,
  type KgNode,
  type KnowledgeGraphData,
  type KgQueryResult,
  type EducationLevel,
  type RetrievalMode,
} from '@/services/knowledgeGraphService';

interface KnowledgeGraphPageProps {
  projectId: string;
  projectMode?: string;
  researchQuestion?: string;
  focusNodeId?: string | null;
}

export function KnowledgeGraphPage({
  projectId,
  projectMode,
  researchQuestion = '',
  focusNodeId,
}: KnowledgeGraphPageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [graph, setGraph] = useState<KnowledgeGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState<KgQueryResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<KgNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<KgEdge | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<Set<string>>(new Set());
  const [relationFilter, setRelationFilter] = useState<Set<string>>(new Set());
  const [showQuality, setShowQuality] = useState(true);
  const [educationLevel, setEducationLevel] = useState<EducationLevel>('undergraduate');
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>('hybrid');
  const [scenarioHint, setScenarioHint] = useState<string>('');
  const [labelMode, setLabelMode] = useState<LabelDisplayMode>('auto');
  const labelModeRef = useRef<LabelDisplayMode>('auto');
  const viewPresetRef = useRef(getEducationViewPreset('undergraduate'));

  const viewPreset = useMemo(
    () => getEducationViewPreset(educationLevel),
    [educationLevel],
  );

  useEffect(() => {
    labelModeRef.current = labelMode;
  }, [labelMode]);

  useEffect(() => {
    viewPresetRef.current = viewPreset;
  }, [viewPreset]);

  useEffect(() => {
    setLabelMode(viewPreset.defaultLabelMode);
  }, [viewPreset.mode]);

  useEffect(() => {
    knowledgeGraphService.getScenarios().then((res) => {
      if (res.code === 200 && res.data) {
        const key = projectMode === 'federated_learning' ? 'federated_learning' : 'general_science';
        const scenario = res.data.domain_scenarios[key];
        if (scenario) setScenarioHint(scenario.description);
      }
    }).catch(() => {});
  }, [projectMode]);

  const loadGraph = useCallback(async () => {
    try {
      const res = await knowledgeGraphService.getGraph(projectId);
      if (res.code === 200 && res.data) {
        setGraph(res.data);
        setNodeTypeFilter(new Set());
        setRelationFilter(new Set());
      }
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  const nodeTypes = useMemo(
    () => graph?.schema?.node_types || [...new Set((graph?.nodes || []).map((n) => n.type))],
    [graph],
  );
  const relationTypes = useMemo(
    () => graph?.schema?.relation_types || [...new Set((graph?.edges || []).map((e) => e.relation))],
    [graph],
  );

  const presetFiltered = useMemo(() => {
    if (!graph) return { nodes: [] as KgNode[], edges: [] as KgEdge[] };
    return applyViewPresetToGraph(graph.nodes, graph.edges, viewPreset);
  }, [graph, viewPreset]);

  const filteredElements = useMemo(() => {
    const nodes = presetFiltered.nodes.filter(
      (n) => nodeTypeFilter.size === 0 || nodeTypeFilter.has(n.type),
    );
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = presetFiltered.edges.filter(
      (e) =>
        nodeIds.has(e.source) &&
        nodeIds.has(e.target) &&
        (relationFilter.size === 0 || relationFilter.has(e.relation)),
    );
    return { nodes, edges };
  }, [presetFiltered, nodeTypeFilter, relationFilter]);

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    ensureFcoseRegistered();

    const elements = buildGraphElements(
      filteredElements.nodes,
      filteredElements.edges,
      graph.communities,
      viewPreset,
      educationLevel,
    );

    const hasCompounds = elements.some((el) => el.classes === 'community');

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getKgStylesheets(viewPreset),
      layout: getKgLayout(filteredElements.nodes.length, hasCompounds),
      minZoom: 0.15,
      maxZoom: 2.5,
      wheelSensitivity: 0.25,
    });

    const syncLabels = () => {
      syncGraphLabels(cy, labelModeRef.current, viewPresetRef.current.labelZoomThreshold);
    };

    const highlightNeighborhood = (nodeId: string | null) => {
      cy.elements().removeClass('dim highlight');
      if (!nodeId) return;
      const node = cy.getElementById(nodeId);
      if (!node.length) return;
      const hood = node.closedNeighborhood();
      cy.elements().not(hood).addClass('dim');
      hood.edges().addClass('highlight');
    };

    cy.on('mouseover', 'node', (evt) => {
      evt.target.addClass('hover');
      syncLabels();
    });
    cy.on('mouseout', 'node', (evt) => {
      evt.target.removeClass('hover');
      syncLabels();
    });
    cy.on('zoom pan', syncLabels);

    cy.on('tap', 'node', (evt) => {
      const nd = evt.target.data('nodeData') as KgNode;
      setSelectedNode(nd);
      setSelectedEdge(null);
      highlightNeighborhood(evt.target.id());
      syncLabels();
    });
    cy.on('tap', 'edge', (evt) => {
      const ed = evt.target.data('edgeData') as KgEdge;
      setSelectedEdge(ed);
      setSelectedNode(null);
      cy.elements().removeClass('dim highlight');
      evt.target.addClass('highlight');
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        setSelectedEdge(null);
        cy.elements().removeClass('dim highlight');
        syncLabels();
      }
    });

    if (focusNodeId) {
      const node = cy.getElementById(focusNodeId);
      if (node.length) {
        cy.animate({ center: { eles: node }, zoom: 1.2 }, { duration: 300 });
        node.select();
        highlightNeighborhood(focusNodeId);
      }
    }

    syncLabels();
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, filteredElements, focusNodeId, educationLevel, viewPreset]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    syncGraphLabels(cy, labelMode, viewPreset.labelZoomThreshold);
  }, [labelMode, viewPreset, graph, filteredElements]);

  const handleBuild = async () => {
    setLoading(true);
    setAction('build');
    setError(null);
    try {
      const res = await knowledgeGraphService.build({
        project_id: projectId,
        research_question: researchQuestion,
        project_mode: projectMode,
      });
      if (res.code === 200 && res.data) {
        setGraph(res.data);
      } else {
        setError(res.message || '构建失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '构建失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleRebuild = async () => {
    setLoading(true);
    setAction('rebuild');
    setError(null);
    try {
      const res = await knowledgeGraphService.rebuild({
        project_id: projectId,
        research_question: researchQuestion,
        project_mode: projectMode,
      });
      if (res.code === 200 && res.data) setGraph(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '重建失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    setLoading(true);
    setAction('query');
    setError(null);
    try {
      const res = await knowledgeGraphService.query(projectId, queryText.trim(), {
        education_level: educationLevel,
        retrieval_mode: retrievalMode,
      });
      if (res.code === 200 && res.data) setQueryResult(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询失败');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleVerifyEdge = async (edge: KgEdge) => {
    try {
      const res = await knowledgeGraphService.feedback({
        project_id: projectId,
        action: 'verify',
        target_type: 'edge',
        target_id: edge.id,
      });
      if (res.code === 200 && res.data?.graph) setGraph(res.data.graph);
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
    }
  };

  const handleDeleteEdge = async (edge: KgEdge) => {
    try {
      const res = await knowledgeGraphService.feedback({
        project_id: projectId,
        action: 'delete',
        target_type: 'edge',
        target_id: edge.id,
      });
      if (res.code === 200 && res.data?.graph) {
        setGraph(res.data.graph);
        setSelectedEdge(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const toggleNodeType = (t: string) => {
    setNodeTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const toggleRelation = (r: string) => {
    setRelationFilter((prev) => {
      const next = new Set(prev);
      if (next.has(r)) next.delete(r);
      else next.add(r);
      return next;
    });
  };

  const qr = graph?.quality_report;

  const handleFit = () => cyRef.current?.fit(undefined, 72);
  const handleZoomIn = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.2);
  };
  const handleZoomOut = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() / 1.2);
  };

  const cycleLabelMode = () => {
    setLabelMode((m) => (m === 'auto' ? 'always' : m === 'always' ? 'never' : 'auto'));
  };

  const handleExportPng = () => {
    if (!cyRef.current) return;
    exportGraphPng(cyRef.current, `kg-${projectId.slice(0, 8)}.png`);
  };

  const handleFocusCommunity = (communityId: string) => {
    if (!cyRef.current) return;
    focusCommunityOnCanvas(cyRef.current, communityId);
  };

  const visibleNodeHint =
    graph && presetFiltered.nodes.length < (graph.nodes?.length || 0)
      ? `视图已简化：显示 ${presetFiltered.nodes.length}/${graph.nodes.length} 节点`
      : null;

  const labelModeHint =
    labelMode === 'auto' ? '悬停/放大显示' : labelMode === 'always' ? '全部显示' : '全部隐藏';

  const legendTypes = useMemo(
    () => [...new Set((graph?.nodes || []).map((n) => n.type))].slice(0, 8),
    [graph],
  );

  return (
    <div className="space-y-4">
      {/* Neo4j 风格顶栏 */}
      <div
        className="rounded-xl border p-4 flex flex-wrap items-center justify-between gap-3"
        style={{ background: NEO4J_BG, borderColor: NEO4J_BORDER }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: `${NEO4J_GREEN}22`, border: `1px solid ${NEO4J_GREEN}55` }}
          >
            <Network className="w-5 h-5" style={{ color: NEO4J_GREEN }} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-bp-text">科研知识图谱</h2>
            <p className="text-xs text-bp-muted">
              GraphRAG · LightRAG · KAG 融合 — 查询 · 推理 · 溯源 · 解释
              {graph ? ` · ${graph.nodes?.length || 0} 节点 / ${graph.edges?.length || 0} 边` : ''}
              {graph?.communities?.length ? ` · ${graph.communities.length} 主题社区` : ''}
            </p>
            {scenarioHint && (
              <p className="text-[11px] text-bp-muted mt-1 max-w-xl">{scenarioHint}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleBuild}
            disabled={loading}
            className="border-0 text-black font-medium"
            style={{ background: NEO4J_GREEN }}
          >
            {loading && action === 'build' ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <Network className="w-4 h-4 mr-1" />
            )}
            构建图谱
          </Button>
          <Button variant="secondary" onClick={handleRebuild} disabled={loading || !graph}>
            {loading && action === 'rebuild' ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-1" />
            )}
            增量重建
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* 左侧筛选 + 查询 */}
        <div className="xl:col-span-1 space-y-4">
          <Card className="border-[#30363d] bg-[#161b22]">
            <div className="flex items-center gap-2 mb-3 text-sm font-medium text-[#00dc82]">
              <Search className="w-4 h-4" />
              图谱查询
            </div>
            <textarea
              className="w-full rounded-lg bg-[#0d1117] border border-[#30363d] text-sm text-bp-text p-2 min-h-[72px] focus:outline-none focus:border-[#00dc82]"
              placeholder="例如：哪些方法可以缓解 Non-IID？ / 该领域研究概览"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-2 mt-2">
              <select
                className="text-xs rounded-lg bg-[#0d1117] border border-[#30363d] text-bp-text p-2 col-span-2"
                value={educationLevel}
                onChange={(e) => setEducationLevel(e.target.value as EducationLevel)}
              >
                <option value="primary">科普 / 小学 · 简化视图</option>
                <option value="secondary">中学 · 简化视图</option>
                <option value="undergraduate">本科 · 标准视图</option>
                <option value="graduate">研究生 · 科研视图</option>
                <option value="researcher">科研工作者 · 科研视图</option>
              </select>
              <p className="col-span-2 text-[10px] text-bp-muted flex items-start gap-1">
                <Layers className="w-3 h-3 shrink-0 mt-0.5 text-[#00dc82]" />
                {viewPreset.label}：{viewPreset.hint}
              </p>
              <select
                className="text-xs rounded-lg bg-[#0d1117] border border-[#30363d] text-bp-text p-2"
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value as RetrievalMode)}
              >
                <option value="hybrid">Hybrid 融合</option>
                <option value="local">Local 实体邻域</option>
                <option value="global">Global 主题社区</option>
              </select>
            </div>
            <Button
              className="w-full mt-2 border-0 text-black"
              style={{ background: NEO4J_GREEN }}
              onClick={handleQuery}
              disabled={loading || !graph}
            >
              {loading && action === 'query' ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : null}
              执行推理
            </Button>
            {queryResult && (
              <div className="mt-3 text-xs text-bp-text space-y-2">
                <p className="text-[#00dc82] font-medium">{queryResult.answer}</p>
                {queryResult.retrieval_mode && (
                  <p className="text-bp-muted">
                    模式: {queryResult.retrieval_mode}
                    {queryResult.local_hit?.node_count != null && ` · 局部 ${queryResult.local_hit.node_count} 节点`}
                    {queryResult.global_hit?.community_count != null && ` · 全局 ${queryResult.global_hit.community_count} 社区`}
                  </p>
                )}
                {queryResult.reasoning_chain && queryResult.reasoning_chain.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-bp-muted flex items-center gap-1">
                      <GitBranch className="w-3 h-3" /> 推理链
                    </p>
                    {queryResult.reasoning_chain.slice(0, 4).map((step) => (
                      <div key={step.step} className="bg-[#0d1117] rounded p-2 border border-[#30363d]">
                        <span className="text-[#00dc82]">#{step.step}</span> {step.inference || step.content}
                        {step.source_title && (
                          <p className="text-bp-muted mt-0.5 flex items-center gap-1">
                            <BookOpen className="w-3 h-3" /> {step.source_title}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {queryResult.provenance?.citation_spans && queryResult.provenance.citation_spans.length > 0 && (
                  <div>
                    <p className="text-bp-muted mb-1">溯源 ({queryResult.provenance.source_count})</p>
                    {queryResult.provenance.citation_spans.slice(0, 3).map((c, i) => (
                      <p key={i} className="text-bp-muted truncate">· {c.source_title}</p>
                    ))}
                  </div>
                )}
                {queryResult.graph_paths?.slice(0, 3).map((p, i) => (
                  <div key={i} className="bg-[#0d1117] rounded p-2 border border-[#30363d]">
                    {Array.isArray(p) ? p.join(' → ') : String(p)}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="border-[#30363d] bg-[#161b22]">
            <div className="flex items-center gap-2 mb-3 text-sm font-medium text-bp-text">
              <Filter className="w-4 h-4 text-[#00dc82]" />
              节点类型
            </div>
            <div className="flex flex-wrap gap-1.5">
              {nodeTypes.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => toggleNodeType(t)}
                  className="text-xs px-2 py-1 rounded-full border transition-colors"
                  style={{
                    borderColor: nodeTypeFilter.has(t) ? NEO4J_GREEN : NEO4J_BORDER,
                    background: nodeTypeFilter.has(t) ? `${NEO4J_GREEN}22` : 'transparent',
                    color: nodeTypeFilter.has(t) ? NEO4J_GREEN : '#8b949e',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </Card>

          <Card className="border-[#30363d] bg-[#161b22]">
            <div className="flex items-center gap-2 mb-3 text-sm font-medium text-bp-text">
              <Filter className="w-4 h-4 text-[#00dc82]" />
              关系类型
            </div>
            <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto">
              {relationTypes.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => toggleRelation(r)}
                  className="text-xs px-2 py-1 rounded-full border transition-colors"
                  style={{
                    borderColor: relationFilter.has(r) ? NEO4J_GREEN : NEO4J_BORDER,
                    background: relationFilter.has(r) ? `${NEO4J_GREEN}22` : 'transparent',
                    color: relationFilter.has(r) ? NEO4J_GREEN : '#8b949e',
                  }}
                >
                  {r}
                </button>
              ))}
            </div>
          </Card>

          {showQuality && qr && (
            <Card className="border-[#30363d] bg-[#161b22]">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-sm font-medium text-bp-text">
                  <BarChart3 className="w-4 h-4 text-[#00dc82]" />
                  质量报告
                </div>
                <button type="button" onClick={() => setShowQuality(false)} className="text-bp-muted hover:text-bp-text">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="text-xs text-bp-muted space-y-1">
                <p>综合得分: <span className="text-[#00dc82]">{qr.overall_score ?? '-'}</span></p>
                <p>孤立节点: {qr.isolated_count ?? 0}</p>
                <p>低置信边: {qr.low_confidence_count ?? 0}</p>
                <p>缺失来源: {qr.missing_sources_count ?? 0}</p>
              </div>
              {(qr.isolated_nodes?.length ?? 0) > 0 && (
                <ul className="mt-2 text-xs text-amber-400/90 space-y-1 max-h-24 overflow-y-auto">
                  {qr.isolated_nodes?.slice(0, 5).map((n) => (
                    <li key={n.id}>· [{n.type}] {n.label}</li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {(graph?.communities?.length ?? 0) > 0 && (
            <Card className="border-[#30363d] bg-[#161b22]">
              <div className="text-sm font-medium text-bp-text mb-2">主题社区 (GraphRAG)</div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {graph!.communities!.slice(0, viewPreset.mode === 'research' ? 6 : 4).map((c) => (
                  <button
                    key={c.community_id}
                    type="button"
                    onClick={() => handleFocusCommunity(c.community_id)}
                    className="w-full text-left text-xs bg-[#0d1117] rounded p-2 border border-[#30363d] hover:border-[#00dc82]/50 transition-colors"
                  >
                    <span className="text-[#00dc82]">
                      {TYPE_LABELS_ZH[c.dominant_type] || c.dominant_type}
                    </span>
                    <span className="text-bp-muted ml-2">{c.node_count} 节点</span>
                    {viewPreset.mode === 'research' && (
                      <span className="text-bp-muted ml-2">· 点击定位</span>
                    )}
                    <p className="text-bp-muted mt-1 line-clamp-2">{c.summary}</p>
                  </button>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* 图谱 + 详情 */}
        <div className="xl:col-span-3 space-y-4">
          <div
            className="relative rounded-xl border overflow-hidden"
            style={{ background: NEO4J_BG, borderColor: NEO4J_BORDER, minHeight: 520 }}
          >
            {!graph && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-bp-muted z-10">
                <Network className="w-12 h-12 mb-3 opacity-40" style={{ color: NEO4J_GREEN }} />
                <p className="text-sm">上传文献后点击「构建图谱」</p>
              </div>
            )}
            {graph && (
              <>
                <div className="absolute top-3 left-3 z-20 flex flex-col gap-1 max-w-[55%]">
                  <span
                    className="inline-flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-md bg-[#161b22]/92 border border-[#30363d] text-[#00dc82]"
                  >
                    <Layers className="w-3 h-3" />
                    {viewPreset.label}
                  </span>
                  {visibleNodeHint && (
                    <span className="text-[10px] text-bp-muted px-1">{visibleNodeHint}</span>
                  )}
                </div>
                <div className="absolute top-3 right-3 z-20 flex gap-1.5">
                  <button
                    type="button"
                    title="适应画布"
                    onClick={handleFit}
                    className="p-1.5 rounded-md bg-[#161b22]/90 border border-[#30363d] text-bp-text hover:text-[#00dc82]"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                  <button type="button" title="放大" onClick={handleZoomIn} className="p-1.5 rounded-md bg-[#161b22]/90 border border-[#30363d] text-bp-text hover:text-[#00dc82]">
                    <ZoomIn className="w-4 h-4" />
                  </button>
                  <button type="button" title="缩小" onClick={handleZoomOut} className="p-1.5 rounded-md bg-[#161b22]/90 border border-[#30363d] text-bp-text hover:text-[#00dc82]">
                    <ZoomOut className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    title={`标签: ${labelModeHint}`}
                    onClick={cycleLabelMode}
                    className="px-2 py-1.5 rounded-md bg-[#161b22]/90 border border-[#30363d] text-[10px] text-bp-text hover:text-[#00dc82] flex items-center gap-1"
                  >
                    <Tag className="w-3.5 h-3.5" />
                    {labelMode === 'auto' ? '自动' : labelMode === 'always' ? '全显' : '隐藏'}
                  </button>
                  {viewPreset.mode === 'research' && (
                    <button
                      type="button"
                      title="导出 PNG"
                      onClick={handleExportPng}
                      className="p-1.5 rounded-md bg-[#161b22]/90 border border-[#30363d] text-bp-text hover:text-[#00dc82]"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  )}
                </div>
                {legendTypes.length > 0 && (
                  <div className="absolute bottom-3 left-3 z-20 flex flex-wrap gap-2 max-w-[70%]">
                    {legendTypes.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-full bg-[#161b22]/92 border border-[#30363d] text-bp-muted"
                      >
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ background: NODE_COLORS[t] || NODE_COLORS.default }}
                        />
                        {viewPreset.mode === 'simplified' || educationLevel === 'primary' || educationLevel === 'secondary'
                          ? (TYPE_LABELS_ZH[t] || t)
                          : t}
                      </span>
                    ))}
                  </div>
                )}
                <p className="absolute bottom-3 right-3 z-20 text-[10px] text-bp-muted">
                  {viewPreset.mode === 'simplified'
                    ? '点击节点查看详情 · 社区摘要见左侧'
                    : viewPreset.mode === 'research'
                      ? '选中边显示关系 · 侧栏社区可定位 · 可导出 PNG'
                      : '悬停节点查看名称 · 滚轮缩放 · 点击高亮邻域'}
                </p>
              </>
            )}
            <div ref={containerRef} className="w-full h-[520px]" />
          </div>

          {(selectedNode || selectedEdge) && (
            <Card className="border-[#30363d] bg-[#161b22]">
              {selectedNode && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-[#00dc82]">节点详情</h3>
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: `${NODE_COLORS[selectedNode.type] || NODE_COLORS.default}33` }}
                    >
                      {selectedNode.type}
                    </span>
                  </div>
                  <p className="text-bp-text font-medium">{selectedNode.label}</p>
                  {selectedNode.description && (
                    <p className="text-sm text-bp-muted">{selectedNode.description}</p>
                  )}
                  <p className="text-xs text-bp-muted">
                    来源: {(selectedNode.source_ids || []).join(', ') || '—'}
                  </p>
                  <p className="text-xs text-bp-muted">置信度: {selectedNode.confidence ?? '—'}</p>
                </div>
              )}
              {selectedEdge && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-[#00dc82]">边 / 证据</h3>
                    <span className="text-xs text-bp-muted">{selectedEdge.relation}</span>
                  </div>
                  <p className="text-sm text-bp-text">{selectedEdge.evidence || '—'}</p>
                  <p className="text-xs text-bp-muted">来源论文: {selectedEdge.source_title || '—'}</p>
                  {selectedEdge.page != null && (
                    <p className="text-xs text-bp-muted">页码: {selectedEdge.page}</p>
                  )}
                  <p className="text-xs text-bp-muted">
                    置信度: {selectedEdge.confidence ?? '—'}
                    {selectedEdge.human_verified && (
                      <span className="ml-2 text-[#00dc82] inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> 已人工确认
                      </span>
                    )}
                  </p>
                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="secondary"
                      className="text-xs"
                      onClick={() => handleVerifyEdge(selectedEdge)}
                    >
                      <ShieldCheck className="w-3 h-3 mr-1" />
                      确认
                    </Button>
                    <Button
                      variant="secondary"
                      className="text-xs text-red-400"
                      onClick={() => handleDeleteEdge(selectedEdge)}
                    >
                      <Trash2 className="w-3 h-3 mr-1" />
                      删除
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

export default KnowledgeGraphPage;
