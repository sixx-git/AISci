import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Puzzle, Search, FilterX, RefreshCw, Loader2, Bot, ToggleLeft, ToggleRight, Lock,
  ChevronLeft, ChevronRight,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import skillService, { type SkillRecord, type SkillSummary } from '@/services/skillService';
import { cn } from '@/lib/utils';

const filterSelectClass = 'input-field select-field w-full h-10 py-2 text-sm';
const filterButtonClass = 'h-10 shrink-0';
const PAGE_SIZE = 12;

export function Skills() {
  const [skills, setSkills] = useState<SkillRecord[]>([]);
  const [summary, setSummary] = useState<SkillSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [categoryFilter, setCategoryFilter] = useState('');
  const [agentFilter, setAgentFilter] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [appliedKeyword, setAppliedKeyword] = useState('');

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const listRes = await skillService.list({
        category: categoryFilter || undefined,
        agent: agentFilter || undefined,
        keyword: appliedKeyword || undefined,
        refresh,
      });
      const summaryRes = await skillService.getSummary(refresh);
      if (listRes.code === 200 && Array.isArray(listRes.data)) {
        setSkills(listRes.data);
      } else {
        setError(listRes.message || '加载技能列表失败');
      }
      if (summaryRes.code === 200 && summaryRes.data) {
        setSummary(summaryRes.data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, agentFilter, appliedKeyword]);

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [categoryFilter, agentFilter, appliedKeyword]);

  const totalPages = Math.max(1, Math.ceil(skills.length / PAGE_SIZE));

  const paginatedSkills = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return skills.slice(start, start + PAGE_SIZE);
  }, [skills, page]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const categoryOptions = useMemo(
    () => summary?.categories ?? [],
    [summary],
  );

  const agentOptions = useMemo(
    () => summary?.agents ?? [],
    [summary],
  );

  const handleToggle = async (skill: SkillRecord) => {
    if (skill.locked) return;
    setTogglingId(skill.id);
    try {
      const res = await skillService.setEnabled(skill.id, !skill.enabled);
      if (res.code === 200 && res.data) {
        setSkills((prev) => prev.map((s) => (s.id === skill.id ? res.data! : s)));
        const summaryRes = await skillService.getSummary(true);
        if (summaryRes.code === 200 && summaryRes.data) {
          setSummary(summaryRes.data);
        }
      }
    } catch {
      setError('切换状态失败');
    } finally {
      setTogglingId(null);
    }
  };

  const hasFilters = Boolean(categoryFilter || agentFilter || appliedKeyword);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="技能管理"
        subtitle="Pipeline 核心 Skill 已锁定不可禁用；其余 Skill 禁用后运行时将自动跳过"
      />

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold font-mono text-bp-text">{summary.total}</div>
            <div className="text-xs text-bp-muted mt-1">技能总数</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold font-mono text-bp-green">{summary.enabled}</div>
            <div className="text-xs text-bp-muted mt-1">已启用</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold font-mono text-bp-yellow">{summary.disabled}</div>
            <div className="text-xs text-bp-muted mt-1">已禁用</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold font-mono text-bp-cyan">{summary.locked ?? 0}</div>
            <div className="text-xs text-bp-muted mt-1">核心锁定</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold font-mono text-bp-cyan">{summary.agents.length}</div>
            <div className="text-xs text-bp-muted mt-1">关联网智能体</div>
          </Card>
        </div>
      )}

      <Card className="p-4 mb-6">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-bp-muted mb-1 block">分类</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className={filterSelectClass}
            >
              <option value="">全部分类</option>
              {categoryOptions.map((c) => (
                <option key={c.id} value={c.id}>{c.label} ({c.count})</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-bp-muted mb-1 block">智能体</label>
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className={filterSelectClass}
            >
              <option value="">全部智能体</option>
              {agentOptions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div className="flex-[2] min-w-[200px]">
            <label className="text-xs text-bp-muted mb-1 block">搜索</label>
            <div className="flex gap-2 items-center">
              <input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && setAppliedKeyword(keywordInput.trim())}
                placeholder="技能名称 / 描述"
                className="input-field flex-1 h-10 py-2 text-sm"
              />
              <Button
                variant="secondary"
                size="sm"
                className={filterButtonClass}
                icon={<Search className="w-4 h-4" />}
                onClick={() => setAppliedKeyword(keywordInput.trim())}
              >
                搜索
              </Button>
            </div>
          </div>
          <div className="flex flex-col min-w-0">
            <label className="text-xs text-bp-muted mb-1 block invisible select-none" aria-hidden>
              操作
            </label>
            <div className="flex gap-2 items-center h-10">
              {hasFilters && (
                <Button
                  variant="secondary"
                  size="sm"
                  className={filterButtonClass}
                  icon={<FilterX className="w-4 h-4" />}
                  onClick={() => {
                    setCategoryFilter('');
                    setAgentFilter('');
                    setKeywordInput('');
                    setAppliedKeyword('');
                  }}
                >
                  清除
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                className={filterButtonClass}
                icon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                onClick={() => load(true)}
                disabled={loading}
              >
                刷新
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {loading && skills.length === 0 && (
        <Card><LoadingState message="扫描 Skill 模块…" /></Card>
      )}

      {!loading && error && (
        <Card><ErrorState message={error} onRetry={() => load(true)} /></Card>
      )}

      {!loading && !error && skills.length === 0 && (
        <Card>
          <EmptyState
            icon={<Puzzle className="w-8 h-8" />}
            title="未找到匹配的技能"
            description={hasFilters ? '尝试调整筛选条件' : '后端未发现 Skill 模块'}
          />
        </Card>
      )}

      {skills.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1 text-xs text-bp-muted">
            <span>
              共 {skills.length} 项技能
              {totalPages > 1 && ` · 第 ${page} / ${totalPages} 页`}
            </span>
            {totalPages > 1 && (
              <span>每页 {PAGE_SIZE} 项</span>
            )}
          </div>
          {paginatedSkills.map((skill) => (
            <Card key={skill.id} className={cn('p-4', !skill.enabled && 'opacity-70')}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="text-sm font-semibold text-bp-text font-mono">{skill.name}</h3>
                    <span className="text-xs px-1.5 py-0.5 rounded border border-bp-border text-bp-muted">
                      {skill.category_label}
                    </span>
                    <span
                      className={cn(
                        'text-xs px-1.5 py-0.5 rounded',
                        skill.enabled
                          ? 'bg-bp-green/10 text-bp-green border border-bp-green/20'
                          : 'bg-bp-yellow/10 text-bp-yellow border border-bp-yellow/20',
                      )}
                    >
                      {skill.enabled ? '已启用' : '已禁用'}
                    </span>
                    {skill.locked && (
                      <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-bp-panel text-bp-muted border border-bp-border">
                        <Lock className="w-3 h-3" />
                        核心
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-bp-muted leading-relaxed mb-2">
                    {skill.description || '（无描述）'}
                  </p>
                  {skill.agents.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {skill.agents.map((agent) => (
                        <span
                          key={agent}
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/20"
                        >
                          <Bot className="w-2.5 h-2.5" />
                          {agent}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-bp-muted/60 mt-2 font-mono truncate" title={skill.module_path}>
                    {skill.module_path}
                  </p>
                </div>
                {skill.locked ? (
                  <span
                    className="shrink-0 p-1 rounded-bp text-bp-muted/60"
                    title="Pipeline 核心 Skill，不可禁用"
                  >
                    <Lock className="w-8 h-8" />
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleToggle(skill)}
                    disabled={togglingId === skill.id}
                    className="shrink-0 p-1 rounded-bp hover:bg-bp-panel transition-colors disabled:opacity-50"
                    title={skill.enabled ? '点击禁用' : '点击启用'}
                  >
                    {togglingId === skill.id ? (
                      <Loader2 className="w-8 h-8 animate-spin text-bp-muted" />
                    ) : skill.enabled ? (
                      <ToggleRight className="w-8 h-8 text-bp-green" />
                    ) : (
                      <ToggleLeft className="w-8 h-8 text-bp-muted" />
                    )}
                  </button>
                )}
              </div>
            </Card>
          ))}

          {totalPages > 1 && (
            <div className="flex items-center justify-between gap-2 pt-2 px-1">
              <span className="text-sm text-bp-muted">
                第 {page} / {totalPages} 页
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1 || loading}
                  icon={<ChevronLeft className="w-4 h-4" />}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  下一页
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
