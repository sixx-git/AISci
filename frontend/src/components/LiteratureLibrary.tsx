import { useState, useMemo } from 'react';
import {
  BookOpen, Upload, FileText,
  Database, Eye, Sparkles, Trash2,
  FileSearch, Loader2, CheckCircle, Clock, AlertCircle, Plus,
  Layers, FileDown, BrainCircuit,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatCard } from '@/components/StatCard';
import { MOCK_LITERATURE, computeLiteratureStats } from '@/data/mockData';
import type { LiteratureItem, LiteratureStats } from '@/data/mockData';
import { cn } from '@/lib/utils';

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

// ============ 上传动作 ============
interface UploadAction {
  key: string;
  label: string;
  desc: string;
  icon: React.FC<{ className?: string }>;
  variant: 'primary' | 'secondary' | 'outline';
}

const UPLOAD_ACTIONS: UploadAction[] = [
  { key: 'pdf', label: '上传 PDF', desc: '上传论文 PDF，自动解析文本', icon: Upload, variant: 'primary' },
  { key: 'csv', label: '导入 CSV 数据', desc: '导入结构化科研数据', icon: FileDown, variant: 'secondary' },
  { key: 'index', label: '构建向量索引', desc: '为文献构建语义检索索引', icon: BrainCircuit, variant: 'outline' },
];

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

// ============ Props ============
interface LiteratureLibraryProps {
  projectId?: string;
  compact?: boolean;
}

export function LiteratureLibrary({ projectId: _projectId, compact: _compact = false }: LiteratureLibraryProps) {
  const [literature, setLiterature] = useState<LiteratureItem[]>(MOCK_LITERATURE);
  const [uploading, setUploading] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const stats: LiteratureStats = useMemo(() => computeLiteratureStats(literature), [literature]);

  const filtered = useMemo(() => {
    if (!search.trim()) return literature;
    const kw = search.trim().toLowerCase();
    return literature.filter(
      (l) =>
        l.title.toLowerCase().includes(kw) ||
        l.authors.toLowerCase().includes(kw),
    );
  }, [literature, search]);

  // ===== 模拟操作 =====
  const handleUploadAction = (key: string) => {
    setUploading(key);
    setTimeout(() => setUploading(null), 1800);
  };

  const handleExtractFacts = (id: string) => {
    setLiterature((prev) =>
      prev.map((l) =>
        l.id === id ? { ...l, parseStatus: 'parsing' as const } : l,
      ),
    );
    setTimeout(() => {
      setLiterature((prev) =>
        prev.map((l) =>
          l.id === id
            ? { ...l, parseStatus: 'completed' as const, snippetCount: l.snippetCount + 5, factCount: l.factCount + 4 }
            : l,
        ),
      );
    }, 1500);
  };

  const handleDelete = (id: string) => {
    setLiterature((prev) => prev.filter((l) => l.id !== id));
  };

  // ===== 空状态 =====
  if (literature.length === 0) {
    return (
      <div className="max-w-7xl mx-auto">
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
          <Button
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setLiterature(MOCK_LITERATURE)}
          >
            上传第一篇论文
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
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
          {UPLOAD_ACTIONS.map((action) => {
            const Icon = action.icon;
            const isActive = uploading === action.key;
            return (
              <button
                key={action.key}
                disabled={uploading !== null}
                onClick={() => handleUploadAction(action.key)}
                className={cn(
                  'flex items-start gap-3 p-4 rounded-lg border text-left transition-all duration-200',
                  isActive
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-gray-700 bg-gray-800/40 hover:border-primary-500/40 hover:bg-gray-800',
                  uploading !== null && 'opacity-60 cursor-not-allowed',
                )}
              >
                <div className={cn(
                  'w-9 h-9 rounded-lg flex items-center justify-center shrink-0',
                  isActive ? 'bg-primary-500/25' : 'bg-gray-700',
                )}>
                  {isActive
                    ? <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
                    : <Icon className="w-4 h-4 text-gray-300" />
                  }
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-200">
                    {isActive ? '处理中…' : action.label}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">{action.desc}</div>
                </div>
              </button>
            );
          })}
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
          共 {filtered.length} 篇文献
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
                return (
                  <tr
                    key={item.id}
                    className="border-b border-dark-800 hover:bg-dark-800/30 transition-colors"
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
                          onClick={() => handleExtractFacts(item.id)}
                          disabled={item.parseStatus === 'parsing'}
                          className={cn(
                            'p-1.5 rounded-md transition-colors',
                            item.parseStatus === 'parsing'
                              ? 'text-gray-600 cursor-not-allowed'
                              : 'text-gray-500 hover:text-amber-400 hover:bg-amber-500/10',
                          )}
                        >
                          {item.parseStatus === 'parsing' ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5" />
                          )}
                        </button>
                        <button
                          title="删除"
                          onClick={() => handleDelete(item.id)}
                          className="p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}