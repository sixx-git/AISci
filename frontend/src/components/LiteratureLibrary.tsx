import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookOpen, Upload, FileText,
  Database, Eye, Sparkles, Trash2,
  FileSearch, Loader2, CheckCircle, Clock, AlertCircle, Plus,
  Layers, BrainCircuit,
  XCircle, ArrowUp, Search, Download, ExternalLink,
  Info,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import type { LiteratureItem, LiteratureStats } from '@/types';
import { cn } from '@/lib/utils';
import { documentService, vectorService, literatureService } from '@/services';
import dataFinderService from '@/services/dataFinderService';
import type { DocumentInfo } from '@/services/documentService';
import type { ArxivPaper, ImportedDocument, ImportArxivResult, ParseIndexResult } from '@/services/literatureService';
import { useStatusToast, type StatusToastMessage } from '@/hooks/useToast';
import { getErrorMessage } from '@/lib/errors';
import { formatFileSize } from '@/lib/format';

// ============ MIME / 扩展名 → 文献类型 ============
function inferDocType(info: DocumentInfo): LiteratureItem['type'] {
  const ext = info.file_type?.toLowerCase();
  if (ext === 'pdf') return '论文';
  if (ext === 'txt' || ext === 'md') return '预印本';
  return '论文';
}

// ============ 后端 parse_status → LiteratureItem.parseStatus ============
function mapStatus(status: DocumentInfo['status']): LiteratureItem['parseStatus'] {
  switch (status) {
    case 'uploaded': return 'pending';
    case 'processing': return 'parsing';
    case 'processed': return 'completed';
    case 'failed': return 'error';
    default: return 'pending';
  }
}

// ============ DocumentInfo → LiteratureItem ============
function docInfoToLiterature(doc: DocumentInfo): LiteratureItem {
  const year = doc.created_at ? new Date(doc.created_at).getFullYear() : new Date().getFullYear();
  return {
    id: doc.id,
    title: doc.title || doc.filename.replace(/\.\w+$/, ''),
    authors: doc.authors || '—',
    year,
    type: inferDocType(doc),
    parseStatus: mapStatus(doc.status),
    snippetCount: doc.chunk_count ?? 0,
    factCount: 0,
    fileSize: formatFileSize(doc.file_size),
    uploadDate: doc.created_at ? doc.created_at.slice(0, 10) : '—',
  };
}

// ============ 类型标签映射 ============
const typeConfig: Record<LiteratureItem['type'], { label: string; className: string }> = {
  '论文':   { label: '论文',   className: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/25' },
  '综述':   { label: '综述',   className: 'bg-bp-purple/15 text-bp-purple border-bp-purple/25' },
  '会议':   { label: '会议',   className: 'bg-bp-yellow/15 text-bp-yellow border-bp-yellow/25' },
  '预印本': { label: '预印本', className: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/25' },
};

// ============ 解析状态映射 ============
const parseStatusConfig: Record<LiteratureItem['parseStatus'], { label: string; className: string }> = {
  pending:   { label: '待解析', className: 'bg-bp-panel text-bp-muted border-bp-border' },
  parsing:   { label: '解析中', className: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/25' },
  completed: { label: '已解析', className: 'bg-bp-green/15 text-bp-green border-bp-green/25' },
  error:     { label: '失败',   className: 'bg-danger-500/15 text-danger-400 border-danger-500/25' },
};

// ============ source_type 标签映射 ============
const sourceTypeConfig: Record<string, { label: string; className: string }> = {
  upload:                { label: 'PDF上传', className: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/25' },
  arxiv:                 { label: 'arXiv',   className: 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/25' },
  bibtex:                { label: 'BibTeX',  className: 'bg-bp-purple/15 text-bp-purple border-bp-purple/25' },
  google_scholar_import: { label: 'Scholar', className: 'bg-bp-yellow/15 text-bp-yellow border-bp-yellow/25' },
  manual:                { label: '手动',   className: 'bg-bp-yellow/15 text-bp-yellow border-bp-yellow/25' },
};

// ============ import_status 标签映射 ============
const importStatusConfig: Record<string, { label: string; className: string }> = {
  discovered:      { label: '已发现', className: 'bg-bp-panel text-bp-muted border-bp-border' },
  imported:        { label: '已导入', className: 'bg-green-500/15 text-green-400 border-green-500/25' },
  pdf_downloaded:  { label: 'PDF已下载', className: 'bg-blue-500/15 text-blue-400 border-blue-500/25' },
  parsed:          { label: '已解析', className: 'bg-green-500/15 text-green-400 border-green-500/25' },
  indexed:         { label: '已索引', className: 'bg-purple-500/15 text-purple-400 border-purple-500/25' },
  failed:          { label: '失败', className: 'bg-red-500/15 text-red-400 border-red-500/25' },
};

// ============ 表格列定义 ============
const TABLE_COLUMNS = [
  { key: 'title', label: '论文标题', className: 'text-left' },
  { key: 'authors', label: '作者', className: 'text-left' },
  { key: 'year', label: '年份', className: 'text-center' },
  { key: 'type', label: '类型', className: 'text-center' },
  { key: 'parseStatus', label: '解析状态', className: 'text-center' },
  { key: 'snippetCount', label: '切片', className: 'text-center' },
  { key: 'factCount', label: '事实', className: 'text-center' },
  { key: 'dataFinder', label: 'Data Finder', className: 'text-center' },
  { key: 'actions', label: '操作', className: 'text-right' },
] as const;

// ============ 统计计算 ============
function computeStats(items: LiteratureItem[]): LiteratureStats {
  return {
    uploaded: items.length,
    parsed: items.filter((i) => i.parseStatus === 'completed').length,
    snippets: items.reduce((s, i) => s + i.snippetCount, 0),
    facts: items.reduce((s, i) => s + i.factCount, 0),
  };
}

// ============ Props ============
interface LiteratureLibraryProps {
  projectId?: string;
  compact?: boolean;
}

export function LiteratureLibrary({ projectId = 'default', compact: _compact = false }: LiteratureLibraryProps) {
  const navigate = useNavigate();
  // ========== Tab 状态 ==========
  const [activeTab, setActiveTab] = useState<'upload' | 'arxiv' | 'library'>('upload');

  // ========== 上传 PDF 状态 ==========
  const [literature, setLiterature] = useState<LiteratureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [buildingIndex, setBuildingIndex] = useState(false);
  const [search, setSearch] = useState('');
  const [extractionStats, setExtractionStats] = useState<
    Record<string, { tables: number; figures_confirmed: number; figures_pending: number }>
  >({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ========== arXiv 检索状态 ==========
  const [arxivQuery, setArxivQuery] = useState('');
  const [arxivMaxResults, setArxivMaxResults] = useState(10);
  const [arxivResults, setArxivResults] = useState<ArxivPaper[]>([]);
  const [arxivSearching, setArxivSearching] = useState(false);
  const [arxivImporting, setArxivImporting] = useState<Record<string, boolean>>({});
  const [arxivImported, setArxivImported] = useState<Record<string, boolean>>({});
  const [arxivSearched, setArxivSearched] = useState(false);
  const [arxivFallback, setArxivFallback] = useState(false);

  // ========== 研究问题推荐状态 ==========
  const [researchQuestion, setResearchQuestion] = useState('');
  const [recommendSearching, setRecommendSearching] = useState(false);
  const [recommendInfo, setRecommendInfo] = useState<{ query_mode: string; keywords: string[]; search_query: string } | null>(null);

  // ========== 已入库文献状态 ==========
  const [importedDocs, setImportedDocs] = useState<ImportedDocument[]>([]);
  const [importedLoading, setImportedLoading] = useState(false);

  // ========== 操作状态：下载 / 解析 / Chunk ==========
  const [downloadingDoc, setDownloadingDoc] = useState<string | null>(null);
  const [parsingDoc, setParsingDoc] = useState<string | null>(null);
  const [chunkViewer, setChunkViewer] = useState<{ docId: string; title: string } | null>(null);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkList, setChunkList] = useState<any[]>([]);

  const { statusMsg, showStatus } = useStatusToast();

  const stats: LiteratureStats = useMemo(() => computeStats(literature), [literature]);

  // ========== 数据加载 ==========
  const loadDocuments = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await documentService.getDocuments(projectId);
      if (res.code === 200) {
        const items = (res.data?.items ?? []).map(docInfoToLiterature);
        setLiterature(items);
      }
    } catch (err: unknown) {
      const message = getErrorMessage(err, '未知错误');
      if (import.meta.env.DEV) console.error('获取文献列表失败:', err);
      showStatus({ type: 'error', text: `文献列表加载失败: ${message}` });
    } finally {
      setLoading(false);
    }
  }, [projectId, showStatus]);

  const loadExtractionStats = useCallback(async () => {
    if (!projectId || projectId === 'default') return;
    try {
      const res = await dataFinderService.getPaperExtractionStats(projectId);
      if (res.code === 200 && res.data?.by_paper) {
        setExtractionStats(res.data.by_paper);
      }
    } catch {
      /* ignore */
    }
  }, [projectId]);

  const openDataFinder = useCallback(() => {
    if (projectId && projectId !== 'default') {
      navigate(`/projects/${projectId}?tab=datasets&subtab=data-finder`);
    }
  }, [navigate, projectId]);

  const loadImportedDocs = useCallback(async () => {
    if (!projectId) return;
    setImportedLoading(true);
    try {
      const res = await literatureService.getProjectLiterature(projectId);
      if (res.code === 200) {
        setImportedDocs(res.data?.items ?? []);
      }
    } catch (err: unknown) {
      const message = getErrorMessage(err, '未知错误');
      if (import.meta.env.DEV) console.error('获取已入库文献失败:', err);
      showStatus({ type: 'error', text: `已入库文献加载失败: ${message}` });
    } finally {
      setImportedLoading(false);
    }
  }, [projectId, showStatus]);

  useEffect(() => {
    loadDocuments();
    loadImportedDocs();
    loadExtractionStats();
  }, [loadDocuments, loadImportedDocs, loadExtractionStats]);

  // ========== 上传 PDF ==========
  const handlePdfUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (fileInputRef.current) fileInputRef.current.value = '';

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showStatus({ type: 'error', text: '仅支持 PDF 文件' });
      return;
    }

    setUploading(true);
    showStatus({ type: 'loading', text: `正在上传并解析 ${file.name}…` });

    try {
      const res = await documentService.uploadDocument(projectId, file);
      if (res.code === 200) {
        const uploadedDoc = res.data?.document;
        const chunks = res.data?.chunks_count ?? 0;
        showStatus({ type: 'success', text: `"${uploadedDoc?.filename ?? file.name}" 上传成功，已生成 ${chunks} 个切片` });
        await loadDocuments();
        await loadImportedDocs();
      } else {
        showStatus({ type: 'error', text: res.message || '上传失败' });
      }
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `上传失败: ${detail}` });
    } finally {
      setUploading(false);
    }
  }, [projectId, loadDocuments, loadImportedDocs, showStatus]);

  // ========== 删除 ==========
  const handleDelete = useCallback(async (id: string) => {
    setDeleting(id);
    try {
      const res = await documentService.deleteDocument(id);
      if (res.code === 200) {
        showStatus({ type: 'success', text: '文献已删除' });
        await loadDocuments();
        await loadImportedDocs();
      } else {
        showStatus({ type: 'error', text: res.message || '删除失败' });
      }
    } catch (err: any) {
      showStatus({ type: 'error', text: `删除失败: ${getErrorMessage(err)}` });
    } finally {
      setDeleting(null);
    }
  }, [loadDocuments, loadImportedDocs, showStatus]);

  // ========== 构建向量索引 ==========
  const handleBuildIndex = useCallback(async () => {
    setBuildingIndex(true);
    showStatus({ type: 'loading', text: '正在构建向量索引…' });
    try {
      const res = await vectorService.buildIndex(projectId);
      if (res.code === 200) {
        const added = (res.data as any)?.added_count ?? 0;
        const total = (res.data as any)?.total_count ?? added;
        showStatus({ type: 'success', text: `向量索引构建成功，新增 ${added} 条，共 ${total} 条切片` });
      } else {
        showStatus({ type: 'error', text: res.message || '构建索引失败' });
      }
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `构建索引失败: ${detail}` });
    } finally {
      setBuildingIndex(false);
    }
  }, [projectId, showStatus]);

  // ========== arXiv 搜索 ==========
  const handleArxivSearch = useCallback(async () => {
    const q = arxivQuery.trim();
    if (!q) return;

    setArxivSearching(true);
    setArxivSearched(true);
    setArxivResults([]);
    setArxivFallback(false);

    try {
      const res = await literatureService.searchArxiv(q, arxivMaxResults);
      if (res.code === 200) {
        setArxivResults(res.data?.results ?? []);
        setArxivFallback(!!res.data?.fallback);
        if (!res.data?.results?.length) {
          showStatus({ type: 'error', text: '未找到匹配的 arXiv 论文' });
        } else if (res.data?.fallback) {
          showStatus({ type: 'error', text: res.data.warning || 'arXiv API 不可访问，请稍后重试。' });
        }
      } else {
        showStatus({ type: 'error', text: res.message || '搜索失败' });
      }
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `arXiv 搜索失败: ${detail}。请尝试其他关键词。` });
    } finally {
      setArxivSearching(false);
    }
  }, [arxivQuery, arxivMaxResults, showStatus]);

  // ========== 从研究问题推荐 arXiv ==========
  const handleRecommendArxiv = useCallback(async () => {
    const q = researchQuestion.trim();
    if (!q) return;

    setRecommendSearching(true);
    setArxivSearched(true);
    setArxivResults([]);
    setArxivFallback(false);
    setRecommendInfo(null);

    try {
      const res = await literatureService.recommendArxiv(projectId, q, arxivMaxResults);
      if (res.code === 200 && res.data) {
        const d = res.data;
        setArxivResults(d.results ?? []);
        setArxivFallback(!!d.fallback);
        setRecommendInfo({
          query_mode: d.query_mode,
          keywords: d.keywords,
          search_query: d.search_query,
        });
        if (!d.results?.length) {
          showStatus({ type: 'error', text: '未找到匹配的 arXiv 论文，请尝试其他研究问题' });
        } else if (d.fallback) {
          showStatus({ type: 'error', text: d.warning || 'arXiv API 不可访问，请稍后重试。' });
        } else {
          showStatus({
            type: 'success',
            text: d.query_mode === 'keyword'
              ? `已提取关键词 [${d.keywords.join(', ')}]，返回 ${d.total} 条结果`
              : `已搜索研究问题，返回 ${d.total} 条结果`,
          });
        }
      } else {
        showStatus({ type: 'error', text: res.message || '推荐失败' });
      }
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `arXiv 推荐失败: ${detail}。请尝试手动搜索其他关键词。` });
    } finally {
      setRecommendSearching(false);
    }
  }, [researchQuestion, arxivMaxResults, projectId, showStatus]);

  // ========== arXiv 导入 ==========
  const handleImportArxiv = useCallback(async (paper: ArxivPaper) => {
    setArxivImporting((prev) => ({ ...prev, [paper.external_id]: true }));

    try {
      const res = await literatureService.importArxiv(projectId, [paper], arxivFallback);
      if (res.code === 200) {
        const result = res.data as ImportArxivResult;
        if (result.imported > 0) {
          setArxivImported((prev) => ({ ...prev, [paper.external_id]: true }));
          showStatus({ type: 'success', text: `"${paper.title.slice(0, 60)}..." 已导入文献库` });
          await loadImportedDocs();
        } else if (result.duplicates > 0) {
          setArxivImported((prev) => ({ ...prev, [paper.external_id]: true }));
          showStatus({ type: 'success', text: '该文献已存在，跳过导入' });
        } else {
          showStatus({ type: 'error', text: '导入失败' });
        }
      } else {
        showStatus({ type: 'error', text: res.message || '导入失败' });
      }
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `导入失败: ${detail}` });
    } finally {
      setArxivImporting((prev) => ({ ...prev, [paper.external_id]: false }));
    }
  }, [projectId, loadImportedDocs, showStatus]);

  // ========== 下载 PDF ==========
  const handleDownloadPdf = useCallback(async (docId: string, docTitle: string) => {
    setDownloadingDoc(docId);
    try {
      await literatureService.downloadPdf(projectId, docId);
      showStatus({ type: 'success', text: `PDF 下载完成: ${docTitle.slice(0, 40)}` });
      await loadImportedDocs();
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `PDF 下载失败: ${detail}` });
    } finally {
      setDownloadingDoc(null);
    }
  }, [projectId, loadImportedDocs, showStatus]);

  // ========== 解析 + 索引 ==========
  const handleParseAndIndex = useCallback(async (docId: string, _docTitle: string) => {
    setParsingDoc(docId);
    try {
      const res = await literatureService.parseAndIndex(projectId, docId, true);
      const r = res.data as ParseIndexResult;
      const idxInfo = r.index_added != null ? `，索引 +${r.index_added}` : '';
      showStatus({ type: 'success', text: `解析完成: ${r.chunk_count} chunks${idxInfo}` });
      await loadImportedDocs();
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `解析失败: ${detail}` });
    } finally {
      setParsingDoc(null);
    }
  }, [projectId, loadImportedDocs, showStatus]);

  // ========== 查看 Chunk ==========
  const handleViewChunks = useCallback(async (docId: string, docTitle: string) => {
    setChunkViewer({ docId, title: docTitle });
    setChunkLoading(true);
    try {
      const res = await literatureService.getDocumentChunks(docId, 1, 50);
      setChunkList(res.data.items || []);
    } catch (err: any) {
      const detail = getErrorMessage(err);
      showStatus({ type: 'error', text: `获取切片失败: ${detail}` });
      setChunkList([]);
    } finally {
      setChunkLoading(false);
    }
  }, [showStatus]);

  // ========== 搜索（已有上传文献） ==========
  const filtered = useMemo(() => {
    if (!search.trim()) return literature;
    const kw = search.trim().toLowerCase();
    return literature.filter(
      (l) => l.title.toLowerCase().includes(kw) || l.authors.toLowerCase().includes(kw),
    );
  }, [literature, search]);

  // ========== 截断文本 ==========
  const truncate = (text: string, maxLen: number) =>
    text.length > maxLen ? text.slice(0, maxLen) + '…' : text;

  // ========== Tab 配置 ==========
  const tabs = [
    { key: 'upload' as const, label: '上传 PDF', icon: Upload },
    { key: 'arxiv' as const, label: 'arXiv 检索', icon: Search },
    { key: 'library' as const, label: '已入库文献', icon: Database },
  ];

  // ============ 加载中 ============
  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <StatusBar msg={statusMsg} />
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-bp-text mb-2">科研文献库</h1>
          <p className="text-bp-muted">上传论文 PDF 或通过 arXiv 检索导入文献，系统将进行文本解析、切片与科学事实提取。</p>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-bp-muted">
          <Loader2 className="w-8 h-8 animate-spin mb-4 text-bp-cyan" />
          <p className="text-sm">正在加载文献库...</p>
        </div>
      </div>
    );
  }

  // ============ 空状态（首次加载且无数据） ============
  if (!loading && literature.length === 0) {
    return (
      <div className="max-w-7xl mx-auto">
        <StatusBar msg={statusMsg} />

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-bp-text mb-2">科研文献库</h1>
          <p className="text-bp-muted">上传论文 PDF 或通过 arXiv 检索导入文献，系统将进行文本解析、切片与科学事实提取。</p>
        </div>

        {/* Tabs */}
        <TabBar tabs={tabs} active={activeTab} onChange={(k) => setActiveTab(k as typeof activeTab)} />

        <div className="mt-6">
          {activeTab === 'upload' && <UploadTabEmpty fileInputRef={fileInputRef} uploading={uploading} onUpload={handlePdfUpload} />}
          {activeTab === 'arxiv' && (
            <ArxivTabContent
              query={arxivQuery}
              onQueryChange={setArxivQuery}
              maxResults={arxivMaxResults}
              onMaxResultsChange={setArxivMaxResults}
              onSearch={handleArxivSearch}
              searching={arxivSearching}
              results={arxivResults}
              searched={arxivSearched}
              importing={arxivImporting}
              imported={arxivImported}
              onImport={handleImportArxiv}
              truncate={truncate}
              researchQuestion={researchQuestion}
              onResearchQuestionChange={setResearchQuestion}
              recommendSearching={recommendSearching}
              recommendInfo={recommendInfo}
              onRecommend={handleRecommendArxiv}
            />
          )}
          {activeTab === 'library' && <LibraryTabEmpty />}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <StatusBar msg={statusMsg} />

      {/* ========== 头部 ========== */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-bp-text mb-2">科研文献库</h1>
        <p className="text-bp-muted">上传论文 PDF 或通过 arXiv 检索导入文献，系统将进行文本解析、切片与科学事实提取。</p>
      </div>

      {/* ========== Tabs ========== */}
      <TabBar tabs={tabs} active={activeTab} onChange={(k) => setActiveTab(k as typeof activeTab)} />

      {/* ========== Tab 内容 ========== */}
      <div className="mt-6">
        {/* TAB 1: 上传 PDF */}
        {activeTab === 'upload' && (
          <div>
            {/* 上传区域 */}
            <Card className="mb-6">
              <div className="flex items-center gap-2 mb-4">
                <FileSearch className="w-4 h-4 text-bp-cyan" />
                <h3 className="text-sm font-semibold text-bp-text">数据导入与处理</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <input ref={fileInputRef} type="file" accept=".pdf" onChange={handlePdfUpload} className="hidden" />
                <button
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                  className={cn(
                    'flex items-start gap-3 p-4 rounded-lg border text-left transition-all duration-200',
                    uploading ? 'border-bp-cyan bg-bp-cyan-tint' : 'border-bp-border bg-bp-panel/40 hover:border-bp-cyan/40 hover:bg-bp-panel',
                  )}
                >
                  <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', uploading ? 'bg-bp-cyan-tint' : 'bg-bp-surface')}>
                    {uploading ? <Loader2 className="w-4 h-4 text-bp-cyan animate-spin" /> : <Upload className="w-4 h-4 text-bp-text" />}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-bp-text">{uploading ? '解析中…' : '上传 PDF'}</div>
                    <div className="text-xs text-bp-muted mt-0.5">上传论文 PDF，自动解析文本</div>
                  </div>
                </button>

                <button disabled className="flex items-start gap-3 p-4 rounded-lg border border-bp-border bg-bp-panel/40 opacity-60 text-left">
                  <div className="w-9 h-9 rounded-lg bg-bp-surface flex items-center justify-center shrink-0"><ArrowUp className="w-4 h-4 text-bp-muted" /></div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-bp-muted">导入 CSV 数据</div>
                    <div className="text-xs text-bp-muted mt-0.5">导入结构化科研数据</div>
                  </div>
                </button>

                <button
                  disabled={buildingIndex}
                  onClick={handleBuildIndex}
                  className={cn(
                    'flex items-start gap-3 p-4 rounded-lg border text-left transition-all duration-200',
                    buildingIndex ? 'border-bp-cyan bg-bp-cyan-tint' : 'border-bp-border bg-bp-panel/40 hover:border-bp-cyan/40 hover:bg-bp-panel',
                  )}
                >
                  <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', buildingIndex ? 'bg-bp-cyan-tint' : 'bg-bp-surface')}>
                    {buildingIndex ? <Loader2 className="w-4 h-4 text-bp-cyan animate-spin" /> : <BrainCircuit className="w-4 h-4 text-bp-text" />}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-bp-text">{buildingIndex ? '构建中…' : '构建向量索引'}</div>
                    <div className="text-xs text-bp-muted mt-0.5">为文献构建语义检索索引</div>
                  </div>
                </button>
              </div>
            </Card>

            {/* 统计卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <StatCard label="已上传文献" value={stats.uploaded} icon={<Database className="w-5 h-5" />} colorClass="text-bp-cyan" />
              <StatCard label="已解析文献" value={stats.parsed} icon={<FileText className="w-5 h-5" />} colorClass="text-bp-green" />
              <StatCard label="知识片段" value={stats.snippets} icon={<Layers className="w-5 h-5" />} colorClass="text-bp-purple" />
              <StatCard label="已提取事实" value={stats.facts} icon={<Sparkles className="w-5 h-5" />} colorClass="text-bp-yellow" />
            </div>

            {/* 搜索 + 结果 */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
              <div className="relative flex-1 max-w-sm">
                <FileSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bp-muted" />
                <input
                  type="text" placeholder="搜索论文标题或作者…" value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 input-field"
                />
              </div>
              <span className="text-sm text-bp-muted">{loading ? '加载中…' : `共 ${filtered.length} 篇文献`}</span>
            </div>

            {/* 文献表格 */}
            <LiteratureTable
              items={filtered}
              loading={loading}
              deleting={deleting}
              onDelete={handleDelete}
              extractionStats={extractionStats}
              onOpenDataFinder={openDataFinder}
            />
          </div>
        )}

        {/* TAB 2: arXiv 检索 */}
        {activeTab === 'arxiv' && (
          <ArxivTabContent
            query={arxivQuery}
            onQueryChange={setArxivQuery}
            maxResults={arxivMaxResults}
            onMaxResultsChange={setArxivMaxResults}
            onSearch={handleArxivSearch}
            searching={arxivSearching}
            results={arxivResults}
            searched={arxivSearched}
            importing={arxivImporting}
            imported={arxivImported}
            onImport={handleImportArxiv}
            truncate={truncate}
            researchQuestion={researchQuestion}
            onResearchQuestionChange={setResearchQuestion}
            recommendSearching={recommendSearching}
            recommendInfo={recommendInfo}
            onRecommend={handleRecommendArxiv}
          />
        )}

        {/* TAB 3: 已入库文献 */}
        {activeTab === 'library' && (
          <LibraryTabContent
            docs={importedDocs}
            loading={importedLoading}
            downloadingDoc={downloadingDoc}
            parsingDoc={parsingDoc}
            onDownloadPdf={handleDownloadPdf}
            onParseAndIndex={handleParseAndIndex}
            onViewChunks={handleViewChunks}
            chunkViewer={chunkViewer}
            chunkLoading={chunkLoading}
            chunkList={chunkList}
            onCloseChunks={() => setChunkViewer(null)}
          />
        )}
      </div>
    </div>
  );
}

// ==================== 子组件 ====================

// ---------- TabBar ----------
function TabBar({ tabs, active, onChange }: {
  tabs: Array<{ key: string; label: string; icon: React.ComponentType<{ className?: string }> }>;
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="bp-tab-nav">
      <nav className="flex gap-1 overflow-x-auto -mb-px">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={cn('bp-tab', isActive && 'bp-tab-active')}
          >
            <Icon className="w-4 h-4 shrink-0" />
            {tab.label}
          </button>
        );
      })}
      </nav>
    </div>
  );
}

// ---------- 空状态：上传 PDF ----------
function UploadTabEmpty({ fileInputRef, uploading, onUpload }: {
  fileInputRef: React.RefObject<HTMLInputElement>;
  uploading: boolean;
  onUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <Card className="text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-bp-surface flex items-center justify-center mx-auto mb-5">
        <BookOpen className="w-8 h-8 text-bp-muted" />
      </div>
      <h3 className="text-lg font-medium text-bp-text mb-2">还没有上传科研文献</h3>
      <p className="text-bp-muted max-w-md mx-auto mb-6 text-sm">
        上传论文 PDF 后，系统将自动完成文本解析、文献切片、向量索引构建和科学事实提取。
      </p>
      <input ref={fileInputRef} type="file" accept=".pdf" onChange={onUpload} className="hidden" />
      <Button
        icon={uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        disabled={uploading}
        onClick={() => fileInputRef.current?.click()}
      >
        {uploading ? '解析中…' : '上传第一篇论文'}
      </Button>
    </Card>
  );
}

// ---------- arXiv 检索 Tab 内容 ----------
function ArxivTabContent({
  query, onQueryChange, maxResults, onMaxResultsChange, onSearch, searching,
  results, searched, importing, imported, onImport, truncate,
  researchQuestion, onResearchQuestionChange, recommendSearching, recommendInfo, onRecommend,
}: {
  query: string;
  onQueryChange: (v: string) => void;
  maxResults: number;
  onMaxResultsChange: (v: number) => void;
  onSearch: () => void;
  searching: boolean;
  results: ArxivPaper[];
  searched: boolean;
  importing: Record<string, boolean>;
  imported: Record<string, boolean>;
  onImport: (paper: ArxivPaper) => void;
  truncate: (text: string, maxLen: number) => string;
  // 研究问题推荐
  researchQuestion: string;
  onResearchQuestionChange: (v: string) => void;
  recommendSearching: boolean;
  recommendInfo: { query_mode: string; keywords: string[]; search_query: string } | null;
  onRecommend: () => void;
}) {
  return (
    <div>
      {/* 研究问题推荐区 */}
      <Card className="mb-4 border-bp-cyan/15 bg-bp-cyan-tint">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-bp-cyan" />
          <h3 className="text-sm font-semibold text-bp-text">从研究问题检索 arXiv 文献</h3>
        </div>
        <p className="text-xs text-bp-muted mb-3">
          输入完整的研究问题，AI 将自动提取关键词后搜索 arXiv，推荐最相关的文献
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <textarea
              placeholder="输入你的研究问题，如：如何利用机器学习提高医学影像诊断的准确率？Transformer 模型的长序列处理效率如何优化？"
              value={researchQuestion}
              onChange={(e) => onResearchQuestionChange(e.target.value)}
              rows={3}
              className="w-full px-4 py-2.5 bg-bp-base border border-bp-border rounded-lg text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan transition-colors resize-none"
            />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <Button
              icon={recommendSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              disabled={recommendSearching || !researchQuestion.trim()}
              onClick={onRecommend}
              variant="primary"
            >
              {recommendSearching ? '检索中…' : '从问题检索 arXiv'}
            </Button>
          </div>
        </div>
        {/* 推荐关键词展示 */}
        {recommendInfo && (
          <div className="mt-3 p-3 rounded-lg bg-bp-panel/60 border border-bp-border/50">
            <div className="flex items-center gap-2 mb-1.5">
              <BrainCircuit className="w-3.5 h-3.5 text-bp-cyan" />
              <span className="text-xs font-medium text-bp-muted">
                {recommendInfo.query_mode === 'keyword' ? '已提取关键词' : '直接搜索'}
              </span>
            </div>
            {recommendInfo.query_mode === 'keyword' && (
              <div className="flex flex-wrap gap-1.5 mb-1.5">
                {recommendInfo.keywords.map((kw, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded text-[11px] bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/25"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[10px] text-bp-muted font-mono truncate">
              arXiv Query: {recommendInfo.search_query}
            </p>
          </div>
        )}
      </Card>

      {/* 手动搜索栏 */}
      <Card className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-bp-muted" />
          <h3 className="text-sm font-semibold text-bp-text">手动搜索 arXiv</h3>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-bp-muted mb-1.5">搜索关键词</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bp-muted" />
              <input
                type="text"
                placeholder="输入研究主题或关键词"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onSearch()}
                className="w-full pl-10 pr-4 py-2.5 bg-bp-base border border-bp-border rounded-lg text-sm text-bp-text placeholder:text-bp-muted focus:outline-none focus:border-bp-cyan transition-colors"
              />
            </div>
          </div>
          <div className="w-28">
            <label className="block text-xs font-medium text-bp-muted mb-1.5">结果数</label>
            <select
              value={maxResults}
              onChange={(e) => onMaxResultsChange(Number(e.target.value))}
              className="w-full px-3 py-2.5 bg-bp-base border border-bp-border rounded-lg text-sm text-bp-text focus:outline-none focus:border-bp-cyan"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="flex items-end">
            <Button
              icon={searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              disabled={searching || !query.trim()}
              onClick={onSearch}
            >
              {searching ? '搜索中…' : '搜索 arXiv'}
            </Button>
          </div>
        </div>
      </Card>

      {/* 搜索结果 */}
      {searching && (
        <div className="py-16 text-center text-bp-muted">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" />
          <p className="text-sm">正在搜索 arXiv…</p>
        </div>
      )}

      {!searching && searched && results.length === 0 && (
        <Card className="text-center py-12">
          <Search className="w-10 h-10 text-bp-muted mx-auto mb-3" />
          <p className="text-bp-muted text-sm">未找到匹配的 arXiv 论文，请尝试其他关键词</p>
        </Card>
      )}

      {!searching && results.length > 0 && (
        <div className="space-y-4">
          <div className="text-sm text-bp-muted mb-2">共 {results.length} 条结果</div>
          {results.map((paper) => {
            const isImporting = importing[paper.external_id];
            const isImported = imported[paper.external_id];

            return (
              <Card key={paper.external_id} className={cn(isImported && 'border-green-500/20')}>
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {/* 标题 + arXiv ID */}
                    <div className="flex items-start gap-2 mb-1">
                      <h4 className="text-base font-semibold text-bp-text leading-snug">{paper.title}</h4>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/25 font-mono">
                        {paper.external_id}
                      </span>
                      {paper.categories && paper.categories.split(',').map((cat) => (
                        <span key={cat} className="text-xs px-1.5 py-0.5 rounded bg-bp-surface/50 text-bp-muted border border-bp-border">
                          {cat.trim()}
                        </span>
                      ))}
                    </div>

                    {/* 作者 */}
                    <p className="text-sm text-bp-muted mb-2">{truncate(paper.authors, 120)}</p>

                    {/* 摘要 */}
                    <p className="text-sm text-bp-muted leading-relaxed mb-3 line-clamp-3">
                      {paper.abstract}
                    </p>

                    {/* 链接 */}
                    <div className="flex items-center gap-3 text-xs">
                      <a href={paper.source_url} target="_blank" rel="noopener noreferrer"
                         className="flex items-center gap-1 text-bp-cyan hover:text-bp-cyan transition-colors">
                        <ExternalLink className="w-3 h-3" /> arXiv 详情
                      </a>
                      {paper.pdf_url && (
                        <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer"
                           className="flex items-center gap-1 text-bp-muted hover:text-bp-text transition-colors">
                          <Download className="w-3 h-3" /> PDF
                        </a>
                      )}
                      {paper.published_at && (
                        <span className="text-bp-muted">
                          {paper.published_at.slice(0, 10)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 导入按钮 */}
                  <div className="shrink-0">
                    {isImported ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-green-500/15 text-green-400 text-sm font-medium border border-green-500/25">
                        <CheckCircle className="w-3.5 h-3.5" /> 已导入
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={isImporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        disabled={isImporting}
                        onClick={() => onImport(paper)}
                      >
                        {isImporting ? '导入中…' : '导入文献库'}
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {!searching && !searched && (
        <Card className="text-center py-12">
          <Search className="w-10 h-10 text-bp-muted mx-auto mb-3" />
          <p className="text-bp-muted text-sm">输入关键词后点击搜索，从 arXiv 检索论文元数据</p>
          <p className="text-bp-muted text-xs mt-1">当前阶段仅导入元数据，不下载 PDF</p>
        </Card>
      )}
    </div>
  );
}

// ---------- 空状态：已入库文献 ----------
function LibraryTabEmpty() {
  return (
    <Card className="text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-bp-surface flex items-center justify-center mx-auto mb-5">
        <Database className="w-8 h-8 text-bp-muted" />
      </div>
      <h3 className="text-lg font-medium text-bp-text mb-2">暂无已入库文献</h3>
      <p className="text-bp-muted max-w-md mx-auto text-sm">
        上传 PDF 或通过 arXiv 检索导入文献后，这里将显示所有已入库的文献。
      </p>
    </Card>
  );
}

// ---------- 已入库文献 Tab 内容 ----------
function LibraryTabContent({
  docs, loading,
  downloadingDoc, parsingDoc,
  onDownloadPdf, onParseAndIndex, onViewChunks,
  chunkViewer, chunkLoading, chunkList, onCloseChunks,
}: {
  docs: ImportedDocument[];
  loading: boolean;
  downloadingDoc: string | null;
  parsingDoc: string | null;
  onDownloadPdf: (docId: string, title: string) => void;
  onParseAndIndex: (docId: string, title: string) => void;
  onViewChunks: (docId: string, title: string) => void;
  chunkViewer: { docId: string; title: string } | null;
  chunkLoading: boolean;
  chunkList: any[];
  onCloseChunks: () => void;
}) {
  if (loading) {
    return (
      <div className="py-16 text-center text-bp-muted">
        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" />
        <p className="text-sm">加载已入库文献…</p>
      </div>
    );
  }

  if (docs.length === 0) {
    return <LibraryTabEmpty />;
  }

  return (
    <>
    <div className="space-y-4">
      <div className="text-sm text-bp-muted mb-2">共 {docs.length} 篇文献</div>
      {docs.map((doc) => {
        const sConf = sourceTypeConfig[doc.source_type ?? ''] ?? { label: doc.source_type ?? '—', className: 'bg-bp-panel text-bp-muted border-bp-border' };
        const iConf = importStatusConfig[doc.import_status ?? ''] ?? { label: doc.import_status ?? '—', className: 'bg-bp-panel text-bp-muted border-bp-border' };

        return (
          <Card key={doc.id}>
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <h4 className="text-base font-semibold text-bp-text leading-snug mb-1">
                  {doc.title || '未命名文献'}
                </h4>
                <p className="text-sm text-bp-muted mb-2">{doc.authors}</p>

                {doc.abstract && (
                  <p className="text-sm text-bp-muted leading-relaxed mb-3 line-clamp-2">
                    {doc.abstract}
                  </p>
                )}

                {/* 标签行 */}
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className={cn('text-xs px-2 py-0.5 rounded border', sConf.className)}>{sConf.label}</span>
                  <span className={cn('text-xs px-2 py-0.5 rounded border', iConf.className)}>{iConf.label}</span>
                  {doc.external_id && (
                    <span className="text-xs px-2 py-0.5 rounded bg-bp-surface/50 text-bp-muted border border-bp-border font-mono">
                      {doc.external_id}
                    </span>
                  )}
                  {doc.is_personal ? (
                    <span className="text-xs px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">个人</span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/25">基础库</span>
                  )}
                </div>

                {/* 链接 + 时间 */}
                <div className="flex items-center gap-3 text-xs">
                  {doc.source_url && (
                    <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-1 text-bp-cyan hover:text-bp-cyan transition-colors">
                      <ExternalLink className="w-3 h-3" /> 来源
                    </a>
                  )}
                  {doc.pdf_url && (
                    <a href={doc.pdf_url} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-1 text-bp-muted hover:text-bp-text transition-colors">
                      <Download className="w-3 h-3" /> PDF
                    </a>
                  )}
                  {doc.created_at && (
                    <span className="text-bp-muted">{doc.created_at.slice(0, 10)}</span>
                  )}
                </div>
              </div>

              {/* 操作 */}
              <div className="shrink-0 flex items-center gap-1.5">
                {/* 下载 PDF */}
                {doc.pdf_url && doc.import_status === 'imported' && (
                  <button title="下载 PDF"
                          disabled={downloadingDoc === doc.id}
                          onClick={() => onDownloadPdf(doc.id, doc.title || '文献')}
                          className="p-1.5 rounded-md text-blue-400 hover:text-bp-text hover:bg-blue-500/30 transition-colors disabled:opacity-50">
                    {downloadingDoc === doc.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                  </button>
                )}

                {/* 解析 + 索引 */}
                {((doc.import_status === 'pdf_downloaded' || doc.import_status === 'imported') && doc.pdf_url) && (
                  <button title="解析并索引"
                          disabled={parsingDoc === doc.id}
                          onClick={() => onParseAndIndex(doc.id, doc.title || '文献')}
                          className="p-1.5 rounded-md text-green-400 hover:text-bp-text hover:bg-green-500/30 transition-colors disabled:opacity-50">
                    {parsingDoc === doc.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <BrainCircuit className="w-3.5 h-3.5" />
                    )}
                  </button>
                )}

                {/* 查看 Chunk */}
                {(doc.import_status === 'parsed' || doc.import_status === 'indexed') && (
                  <button title="查看切片"
                          onClick={() => onViewChunks(doc.id, doc.title || '文献')}
                          className="p-1.5 rounded-md text-purple-400 hover:text-bp-text hover:bg-purple-500/30 transition-colors">
                    <FileSearch className="w-3.5 h-3.5" />
                  </button>
                )}

                {/* 查看详情 */}
                <button title="查看详情"
                        className="p-1.5 rounded-md text-bp-muted hover:text-bp-text hover:bg-bp-surface transition-colors">
                  <Eye className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </Card>
        );
      })}
    </div>

    {/* ========== Chunk 查看器 Modal ========== */}
      {chunkViewer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-bp-base/80 backdrop-blur-sm" onClick={onCloseChunks}>
          <div className="bg-bp-base border border-bp-cyan-dim rounded-bp w-full max-w-3xl max-h-[80vh] overflow-hidden shadow-bp-glow-strong" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b border-bp-cyan-dim bg-bp-panel/50">
              <div className="flex items-center gap-2">
                <FileSearch className="w-4 h-4 text-bp-purple" />
                <h3 className="text-sm font-semibold text-bp-text truncate max-w-md">
                  切片预览: {chunkViewer.title}
                </h3>
              </div>
              <button title="关闭"
                      onClick={onCloseChunks}
                      className="p-1 rounded-md text-bp-muted hover:text-bp-text hover:bg-bp-surface transition-colors">
                <XCircle className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="overflow-y-auto max-h-[65vh] p-4">
              {chunkLoading ? (
                <div className="py-12 text-center text-bp-muted">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" />
                  <p className="text-sm">加载切片…</p>
                </div>
              ) : chunkList.length === 0 ? (
                <div className="py-12 text-center text-bp-muted">
                  <p className="text-sm">暂无切片数据</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {chunkList.map((chunk: any, i: number) => (
                    <div key={chunk.id || i} className="p-3 rounded-bp bg-bp-panel-glass border border-bp-border">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs px-1.5 py-0.5 rounded-bp bg-bp-purple/15 text-bp-purple font-mono">
                          #{chunk.chunk_index ?? i + 1}
                        </span>
                        {chunk.page_number && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-bp-surface text-bp-muted">
                            p.{chunk.page_number}
                          </span>
                        )}
                        <span className={cn(
                          'text-xs px-1.5 py-0.5 rounded',
                          chunk.status === 'ready' ? 'bg-green-500/15 text-green-400' : 'bg-bp-surface text-bp-muted',
                        )}>
                          {chunk.status || 'pending'}
                        </span>
                      </div>
                      <p className="text-sm text-bp-text leading-relaxed whitespace-pre-wrap">
                        {chunk.content_preview || chunk.content || '(空)'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ---------- 已有文献表格 ----------
function LiteratureTable({
  items, loading, deleting, onDelete, extractionStats = {}, onOpenDataFinder,
}: {
  items: LiteratureItem[];
  loading: boolean;
  deleting: string | null;
  onDelete: (id: string) => void;
  extractionStats?: Record<string, { tables: number; figures_confirmed: number; figures_pending: number }>;
  onOpenDataFinder?: () => void;
}) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bp-border bg-bp-panel/50">
              {TABLE_COLUMNS.map((col) => (
                <th key={col.key} className={cn('px-4 py-3 font-medium text-bp-muted text-xs whitespace-nowrap', col.className)}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const tConf = typeConfig[item.type];
              const psConf = parseStatusConfig[item.parseStatus];
              const isDeleting = deleting === item.id;
              return (
                <tr key={item.id} className={cn('border-b border-bp-border hover:bg-bp-panel/30 transition-colors', isDeleting && 'opacity-50')}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded bg-bp-cyan-tint flex items-center justify-center shrink-0">
                        <FileText className="w-3.5 h-3.5 text-bp-cyan" />
                      </div>
                      <span className="text-bp-text text-sm font-medium line-clamp-1">{item.title}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-bp-muted whitespace-nowrap">{item.authors}</td>
                  <td className="px-4 py-3 text-center text-bp-text whitespace-nowrap">{item.year}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn('inline-block px-2 py-0.5 rounded text-[11px] font-medium border', tConf.className)}>{tConf.label}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border', psConf.className)}>
                      {item.parseStatus === 'parsing' && <Loader2 className="w-3 h-3 animate-spin" />}
                      {item.parseStatus === 'completed' && <CheckCircle className="w-3 h-3" />}
                      {item.parseStatus === 'pending' && <Clock className="w-3 h-3" />}
                      {item.parseStatus === 'error' && <AlertCircle className="w-3 h-3" />}
                      {psConf.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-bp-text">{item.snippetCount}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={item.factCount > 0 ? 'text-amber-400 font-medium' : 'text-bp-muted'}>{item.factCount}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {(() => {
                      const st = extractionStats[item.id];
                      if (!st || (st.tables === 0 && st.figures_confirmed === 0)) {
                        return <span className="text-bp-muted text-[11px]">—</span>;
                      }
                      return (
                        <button
                          type="button"
                          onClick={onOpenDataFinder}
                          className="inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300"
                          title="跳转 Data Finder 详情"
                        >
                          <Database className="w-3 h-3" />
                          {st.tables}表
                          {st.figures_confirmed > 0 ? ` · ${st.figures_confirmed}图` : ''}
                        </button>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button title="查看详情"
                              className="p-1.5 rounded-md text-bp-muted hover:text-bp-text hover:bg-bp-surface transition-colors">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button title="提取事实" disabled
                              className="p-1.5 rounded-md text-bp-muted cursor-not-allowed transition-colors">
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                      <button title="删除" disabled={isDeleting} onClick={() => onDelete(item.id)}
                              className={cn('p-1.5 rounded-md transition-colors',
                                isDeleting ? 'text-bp-muted cursor-not-allowed' : 'text-bp-muted hover:text-red-400 hover:bg-red-500/10',
                              )}>
                        {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {items.length === 0 && !loading && (
        <div className="py-12 text-center text-bp-muted text-sm">没有匹配的文献</div>
      )}
    </Card>
  );
}

// ========== 状态提示条 ==========
function StatusBar({ msg }: { msg: StatusToastMessage | null }) {
  const [dismissed, setDismissed] = useState(false);

  // 当 msg 变化时重置 dismiss 状态
  useEffect(() => {
    setDismissed(false);
  }, [msg]);

  if (!msg || dismissed) return null;

  const config = {
    loading: { bg: 'bg-blue-500/90', icon: Loader2, text: 'text-bp-text' },
    success: { bg: 'bg-green-500/90', icon: CheckCircle, text: 'text-bp-text' },
    error:   { bg: 'bg-red-500/90',   icon: XCircle,  text: 'text-bp-text' },
    info:    { bg: 'bg-bp-panel',  icon: Info,     text: 'text-bp-text' },
  }[msg.type];

  const Icon = config.icon;
  const isSpinning = msg.type === 'loading';

  return (
    <div className={cn(
      'fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-lg shadow-lg flex items-center gap-2.5 animate-slide-in',
      config.bg,
    )}>
      <Icon className={cn('w-4 h-4', config.text, isSpinning && 'animate-spin')} />
      <span className={cn('text-sm font-medium', config.text)}>{msg.text}</span>
      {msg.type === 'error' && (
        <button
          onClick={() => setDismissed(true)}
          className="ml-2 text-bp-text/60 hover:text-bp-text transition-colors"
        >
          <XCircle className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}