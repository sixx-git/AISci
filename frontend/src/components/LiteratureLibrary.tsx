import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import {
  BookOpen, Upload, FileText,
  Database, Eye, Sparkles, Trash2,
  FileSearch, Loader2, CheckCircle, Clock, AlertCircle, Plus,
  Layers, BrainCircuit,
  XCircle, ArrowUp,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import type { LiteratureItem, LiteratureStats } from '@/types';
import { cn } from '@/lib/utils';
import { documentService, vectorService } from '@/services';
import type { DocumentInfo } from '@/services/documentService';

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
    case 'uploaded':
      return 'pending';
    case 'processing':
      return 'parsing';
    case 'processed':
      return 'completed';
    case 'failed':
      return 'error';
    default:
      return 'pending';
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ============ 类型标签映射 ============
const typeConfig: Record<LiteratureItem['type'], { label: string; className: string }> = {
  '论文':   { label: '论文',   className: 'bg-blue-500/15 text-blue-400 border-blue-500/25' },
  '综述':   { label: '综述',   className: 'bg-purple-500/15 text-purple-400 border-purple-500/25' },
  '会议':   { label: '会议',   className: 'bg-amber-500/15 text-amber-400 border-amber-500/25' },
  '预印本': { label: '预印本', className: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/25' },
};

// ============ 解析状态映射 ============
const parseStatusConfig: Record<LiteratureItem['parseStatus'], { label: string; className: string }> = {
  pending:   { label: '待解析', className: 'bg-gray-500/15 text-gray-400 border-gray-500/25' },
  parsing:   { label: '解析中', className: 'bg-blue-500/15 text-blue-400 border-blue-500/25' },
  completed: { label: '已解析', className: 'bg-green-500/15 text-green-400 border-green-500/25' },
  error:     { label: '失败',   className: 'bg-red-500/15 text-red-400 border-red-500/25' },
};

// ============ 状态消息 ============
interface StatusMsg {
  type: 'loading' | 'success' | 'error';
  text: string;
}

// ============ 表格列定义 ============
const TABLE_COLUMNS = [
  { key: 'title', label: '论文标题', className: 'text-left' },
  { key: 'authors', label: '作者', className: 'text-left' },
  { key: 'year', label: '年份', className: 'text-center' },
  { key: 'type', label: '类型', className: 'text-center' },
  { key: 'parseStatus', label: '解析状态', className: 'text-center' },
  { key: 'snippetCount', label: '切片', className: 'text-center' },
  { key: 'factCount', label: '事实', className: 'text-center' },
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
  const [literature, setLiterature] = useState<LiteratureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [buildingIndex, setBuildingIndex] = useState(false);
  const [search, setSearch] = useState('');
  const [statusMsg, setStatusMsg] = useState<StatusMsg | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    } catch (err: any) {
      console.error('获取文献列表失败:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // ========== 显示状态消息 ==========
  const showStatus = useCallback((msg: StatusMsg) => {
    setStatusMsg(msg);
    setTimeout(() => setStatusMsg(null), 4000);
  }, []);

  // ========== 上传 PDF ==========
  const handlePdfUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 重置 input 以便重复选择同一文件
    if (fileInputRef.current) fileInputRef.current.value = '';

    // 校验文件类型
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
        showStatus({
          type: 'success',
          text: `"${uploadedDoc?.filename ?? file.name}" 上传成功，已生成 ${chunks} 个切片`,
        });
        await loadDocuments();
      } else {
        showStatus({ type: 'error', text: res.message || '上传失败' });
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err.message;
      showStatus({ type: 'error', text: `上传失败: ${detail}` });
    } finally {
      setUploading(false);
    }
  }, [projectId, loadDocuments, showStatus]);

  // ========== 删除 ==========
  const handleDelete = useCallback(async (id: string) => {
    setDeleting(id);
    try {
      const res = await documentService.deleteDocument(id);
      if (res.code === 200) {
        showStatus({ type: 'success', text: '文献已删除' });
        await loadDocuments();
      } else {
        showStatus({ type: 'error', text: res.message || '删除失败' });
      }
    } catch (err: any) {
      showStatus({ type: 'error', text: `删除失败: ${err.message}` });
    } finally {
      setDeleting(null);
    }
  }, [loadDocuments, showStatus]);

  // ========== 构建向量索引 ==========
  const handleBuildIndex = useCallback(async () => {
    setBuildingIndex(true);
    showStatus({ type: 'loading', text: '正在构建向量索引…' });
    try {
      const res = await vectorService.buildIndex(projectId);
      if (res.code === 200) {
        const added = (res.data as any)?.added_count ?? 0;
        const total = (res.data as any)?.total_count ?? added;
        showStatus({
          type: 'success',
          text: `向量索引构建成功，新增 ${added} 条，共 ${total} 条切片`,
        });
      } else {
        showStatus({ type: 'error', text: res.message || '构建索引失败' });
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err.message;
      showStatus({ type: 'error', text: `构建索引失败: ${detail}` });
    } finally {
      setBuildingIndex(false);
    }
  }, [projectId, showStatus]);

  // ========== 搜索 ==========
  const filtered = useMemo(() => {
    if (!search.trim()) return literature;
    const kw = search.trim().toLowerCase();
    return literature.filter(
      (l) =>
        l.title.toLowerCase().includes(kw) ||
        l.authors.toLowerCase().includes(kw),
    );
  }, [literature, search]);

  // ========== 空状态 ==========
  if (!loading && literature.length === 0) {
    return (
      <div className="max-w-7xl mx-auto">
        {/* 状态提示 */}
        <StatusBar msg={statusMsg} />

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">科研文献库</h1>
          <p className="text-gray-400">
            上传论文 PDF 后，系统将进行文本解析、文献切片、向量索引构建与科学事实提取。
          </p>
        </div>

        <Card className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-dark-700 flex items-center justify-center mx-auto mb-5">
            <BookOpen className="w-8 h-8 text-gray-500" />
          </div>
          <h3 className="text-lg font-medium text-gray-300 mb-2">还没有上传科研文献</h3>
          <p className="text-gray-500 max-w-md mx-auto mb-6 text-sm">
            上传论文 PDF 后，系统将自动完成文本解析、文献切片、向量索引构建和科学事实提取。
          </p>
          {/* 隐藏文件选择器 + 按钮触发 */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handlePdfUpload}
            className="hidden"
          />
          <Button
            icon={uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? '解析中…' : '上传第一篇论文'}
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* 状态提示 */}
      <StatusBar msg={statusMsg} />

      {/* ========== 头部 ========== */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">科研文献库</h1>
        <p className="text-gray-400">
          上传论文 PDF 后，系统将进行文本解析、文献切片、向量索引构建与科学事实提取。
        </p>
      </div>

      {/* ========== 上传区域 ========== */}
      <Card className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <FileSearch className="w-4 h-4 text-primary-400" />
          <h3 className="text-sm font-semibold text-gray-200">数据导入与处理</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* PDF 上传 */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handlePdfUpload}
            className="hidden"
          />
          <button
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'flex items-start gap-3 p-4 rounded-lg border text-left transition-all duration-200',
              uploading
                ? 'border-primary-500 bg-primary-500/10'
                : 'border-gray-700 bg-gray-800/40 hover:border-primary-500/40 hover:bg-gray-800',
            )}
          >
            <div className={cn(
              'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
              uploading ? 'bg-primary-500/25' : 'bg-gray-700',
            )}>
              {uploading ? (
                <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 text-gray-300" />
              )}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-200">
                {uploading ? '解析中…' : '上传 PDF'}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">上传论文 PDF，自动解析文本</div>
            </div>
          </button>

          {/* 占位 */}
          <button disabled className="flex items-start gap-3 p-4 rounded-lg border border-gray-700 bg-gray-800/40 opacity-60 text-left">
            <div className="w-9 h-9 rounded-lg bg-gray-700 flex items-center justify-center shrink-0">
              <ArrowUp className="w-4 h-4 text-gray-400" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-500">导入 CSV 数据</div>
              <div className="text-xs text-gray-600 mt-0.5">导入结构化科研数据</div>
            </div>
          </button>

          <button
            disabled={buildingIndex}
            onClick={handleBuildIndex}
            className={cn(
              'flex items-start gap-3 p-4 rounded-lg border text-left transition-all duration-200',
              buildingIndex
                ? 'border-primary-500 bg-primary-500/10'
                : 'border-gray-700 bg-gray-800/40 hover:border-primary-500/40 hover:bg-gray-800',
            )}
          >
            <div className={cn(
              'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
              buildingIndex ? 'bg-primary-500/25' : 'bg-gray-700',
            )}>
              {buildingIndex ? (
                <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
              ) : (
                <BrainCircuit className="w-4 h-4 text-gray-300" />
              )}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-200">
                {buildingIndex ? '构建中…' : '构建向量索引'}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">为文献构建语义检索索引</div>
            </div>
          </button>
        </div>
      </Card>

      {/* ========== 统计卡片 ========== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="已上传文献" value={stats.uploaded} icon={<Database className="w-5 h-5" />} colorClass="text-blue-400" />
        <StatCard label="已解析文献" value={stats.parsed} icon={<FileText className="w-5 h-5" />} colorClass="text-green-400" />
        <StatCard label="知识片段" value={stats.snippets} icon={<Layers className="w-5 h-5" />} colorClass="text-purple-400" />
        <StatCard label="已提取事实" value={stats.facts} icon={<Sparkles className="w-5 h-5" />} colorClass="text-amber-400" />
      </div>

      {/* ========== 搜索 + 结果数 ========== */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <FileSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="搜索论文标题或作者…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 transition-colors"
          />
        </div>
        <span className="text-sm text-gray-500">
          {loading ? '加载中…' : `共 ${filtered.length} 篇文献`}
        </span>
      </div>

      {/* ========== 文献列表表格 ========== */}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dark-700 bg-dark-800/50">
                {TABLE_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      'px-4 py-3 font-medium text-gray-400 text-xs whitespace-nowrap',
                      col.className,
                    )}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const tConf = typeConfig[item.type];
                const psConf = parseStatusConfig[item.parseStatus];
                const isDeleting = deleting === item.id;
                return (
                  <tr
                    key={item.id}
                    className={cn(
                      'border-b border-dark-800 hover:bg-dark-800/30 transition-colors',
                      isDeleting && 'opacity-50',
                    )}
                  >
                    {/* 标题 */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded bg-primary-500/15 flex items-center justify-center shrink-0">
                          <FileText className="w-3.5 h-3.5 text-primary-400" />
                        </div>
                        <span className="text-white text-sm font-medium line-clamp-1">
                          {item.title}
                        </span>
                      </div>
                    </td>
                    {/* 作者 */}
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                      {item.authors}
                    </td>
                    {/* 年份 */}
                    <td className="px-4 py-3 text-center text-gray-300 whitespace-nowrap">
                      {item.year}
                    </td>
                    {/* 类型 */}
                    <td className="px-4 py-3 text-center">
                      <span className={cn(
                        'inline-block px-2 py-0.5 rounded text-[11px] font-medium border',
                        tConf.className,
                      )}>
                        {tConf.label}
                      </span>
                    </td>
                    {/* 解析状态 */}
                    <td className="px-4 py-3 text-center">
                      <span className={cn(
                        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border',
                        psConf.className,
                      )}>
                        {item.parseStatus === 'parsing' && (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        )}
                        {item.parseStatus === 'completed' && (
                          <CheckCircle className="w-3 h-3" />
                        )}
                        {item.parseStatus === 'pending' && (
                          <Clock className="w-3 h-3" />
                        )}
                        {item.parseStatus === 'error' && (
                          <AlertCircle className="w-3 h-3" />
                        )}
                        {psConf.label}
                      </span>
                    </td>
                    {/* 切片数量 */}
                    <td className="px-4 py-3 text-center text-gray-300">
                      {item.snippetCount}
                    </td>
                    {/* 事实数量 */}
                    <td className="px-4 py-3 text-center">
                      <span className={item.factCount > 0 ? 'text-amber-400 font-medium' : 'text-gray-600'}>
                        {item.factCount}
                      </span>
                    </td>
                    {/* 操作 */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          title="查看详情"
                          className="p-1.5 rounded-md text-gray-500 hover:text-gray-200 hover:bg-gray-700 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          title="提取事实"
                          disabled
                          className="p-1.5 rounded-md text-gray-600 cursor-not-allowed transition-colors"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                        </button>
                        <button
                          title="删除"
                          disabled={isDeleting}
                          onClick={() => handleDelete(item.id)}
                          className={cn(
                            'p-1.5 rounded-md transition-colors',
                            isDeleting
                              ? 'text-gray-600 cursor-not-allowed'
                              : 'text-gray-500 hover:text-red-400 hover:bg-red-500/10',
                          )}
                        >
                          {isDeleting ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && !loading && (
          <div className="py-12 text-center text-gray-500 text-sm">
            没有匹配的文献
          </div>
        )}
      </Card>
    </div>
  );
}

// ========== 状态提示条 ==========
function StatusBar({ msg }: { msg: StatusMsg | null }) {
  if (!msg) return null;

  const config = {
    loading: { bg: 'bg-blue-500/90', icon: Loader2, text: 'text-white' },
    success: { bg: 'bg-green-500/90', icon: CheckCircle, text: 'text-white' },
    error:   { bg: 'bg-red-500/90',   icon: XCircle,  text: 'text-white' },
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
    </div>
  );
}