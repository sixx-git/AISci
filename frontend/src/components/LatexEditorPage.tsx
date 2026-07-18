import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Code2, FileText, Loader2, Save, Play, ListTree } from 'lucide-react';
import { Card } from './Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { ReportPdfPreview } from './ReportPdfPreview';
import { reportService, type LatexSourcePayload } from '@/services/reportService';
import { useToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';
import {
  LATEX_SECTION_JUMPS,
  findTexOffset,
  jumpTextareaToOffset,
  type LatexSectionJump,
} from '@/lib/latexSectionNav';

interface LatexEditorPageProps {
  projectId: string;
  reportId: string;
  onBack: () => void;
}

type EditorTab = 'tex' | 'bib';

export function LatexEditorPage({ projectId: _projectId, reportId, onBack }: LatexEditorPageProps) {
  const { message: alertMsg, showAlert } = useToast(2800);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<LatexSourcePayload | null>(null);
  const [tex, setTex] = useState('');
  const [bib, setBib] = useState('');
  const [savedTex, setSavedTex] = useState('');
  const [savedBib, setSavedBib] = useState('');
  const [activeTab, setActiveTab] = useState<EditorTab>('tex');
  const [saving, setSaving] = useState(false);
  const [compiling, setCompiling] = useState(false);
  const [pdfRefreshKey, setPdfRefreshKey] = useState(0);
  const [activeSectionKey, setActiveSectionKey] = useState<string | null>(null);
  const [pendingTexOffset, setPendingTexOffset] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const dirty = tex !== savedTex || bib !== savedBib;

  const sectionAvailability = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const sec of LATEX_SECTION_JUMPS) {
      map.set(sec.key, findTexOffset(tex, sec.texPattern) >= 0);
    }
    return map;
  }, [tex]);

  const loadSource = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.getLatexSource(reportId);
      setMeta(data);
      setTex(data.tex);
      setBib(data.bib || '');
      setSavedTex(data.tex);
      setSavedBib(data.bib || '');
      setActiveTab(data.has_bib ? activeTab : 'tex');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载 LaTeX 源码失败');
    } finally {
      setLoading(false);
    }
  }, [reportId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void loadSource();
  }, [loadSource]);

  useEffect(() => {
    if (pendingTexOffset == null || activeTab !== 'tex') return;
    const ta = textareaRef.current;
    if (!ta) return;
    jumpTextareaToOffset(ta, pendingTexOffset);
    setPendingTexOffset(null);
  }, [pendingTexOffset, activeTab, tex]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await reportService.saveLatexSource(reportId, {
        tex,
        bib: meta?.has_bib || bib.trim() ? bib : undefined,
      });
      if (res.code !== 200) {
        showAlert(res.message || '保存失败');
        return;
      }
      setSavedTex(tex);
      setSavedBib(bib);
      showAlert('LaTeX 源码已保存');
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCompile = async () => {
    setCompiling(true);
    try {
      if (dirty) {
        const saveRes = await reportService.saveLatexSource(reportId, {
          tex,
          bib: meta?.has_bib || bib.trim() ? bib : undefined,
        });
        if (saveRes.code !== 200) {
          showAlert(saveRes.message || '保存失败，已取消编译');
          return;
        }
        setSavedTex(tex);
        setSavedBib(bib);
      }
      const res = await reportService.compileLatex(reportId);
      if (res.code !== 200 || !res.data?.pdf_success) {
        showAlert(res.data?.warning || res.message || 'PDF 编译失败');
      } else {
        showAlert('PDF 编译成功');
      }
      setPdfRefreshKey((k) => k + 1);
    } catch (e) {
      showAlert(e instanceof Error ? e.message : 'PDF 编译失败');
    } finally {
      setCompiling(false);
    }
  };

  const handleSectionJump = (sec: LatexSectionJump) => {
    setActiveTab('tex');
    setActiveSectionKey(sec.key);

    const offset = findTexOffset(tex, sec.texPattern);
    if (offset < 0) {
      showAlert(`源码中未找到「${sec.label}」`);
      return;
    }
    setPendingTexOffset(offset);
  };

  if (loading) {
    return <LoadingState message="正在加载 LaTeX 编辑器…" />;
  }

  if (error) {
    return (
      <div className="space-y-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-bp-muted hover:text-bp-text"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          返回报告
        </button>
        <ErrorState message={error} onRetry={() => void loadSource()} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {alertMsg && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2 rounded-lg bg-bp-panel border border-bp-border text-sm text-bp-text shadow-lg">
          {alertMsg}
        </div>
      )}

      <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-bp-border text-xs text-bp-muted hover:text-bp-text transition-colors shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            返回报告
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4 text-bp-cyan shrink-0" />
              <p className="text-sm font-medium text-bp-text truncate">
                LaTeX 编辑器 · {meta?.title || '研究报告'}
              </p>
              {dirty && (
                <span className="text-[11px] text-bp-yellow shrink-0">未保存</span>
              )}
            </div>
            <p className="text-xs text-bp-muted mt-0.5">
              左侧大纲可跳转到对应源码位置；改完后编译即可在右侧预览 PDF。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || compiling || !dirty}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bp-panel border border-bp-border text-xs text-bp-muted hover:text-bp-text disabled:opacity-40 transition-colors"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            保存
          </button>
          <button
            type="button"
            onClick={() => void handleCompile()}
            disabled={saving || compiling}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-bp-cyan/15 border border-bp-cyan/30 text-xs text-bp-cyan hover:bg-bp-cyan/25 disabled:opacity-40 transition-colors"
          >
            {compiling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            {dirty ? '保存并编译' : '编译 PDF'}
          </button>
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-[200px_minmax(0,1fr)_minmax(0,1fr)] gap-4 items-start">
        <Card className="min-w-0 xl:sticky xl:top-4" noPadding>
          <div className="flex items-center gap-1.5 px-3 py-2.5 border-b border-bp-border bg-bp-base/40">
            <ListTree className="w-3.5 h-3.5 text-bp-cyan" />
            <p className="text-xs font-medium text-bp-text">章节跳转</p>
          </div>
          <nav className="max-h-[calc(100vh-260px)] overflow-y-auto py-1.5">
            {LATEX_SECTION_JUMPS.map((sec) => {
              const available = sectionAvailability.get(sec.key) ?? false;
              const active = activeSectionKey === sec.key;
              return (
                <button
                  key={sec.key}
                  type="button"
                  onClick={() => handleSectionJump(sec)}
                  disabled={!available}
                  className={cn(
                    'w-full text-left px-3 py-1.5 text-xs transition-colors border-l-2',
                    sec.indent && 'pl-5',
                    active
                      ? 'border-bp-cyan bg-bp-cyan/10 text-bp-cyan'
                      : 'border-transparent text-bp-muted hover:text-bp-text hover:bg-bp-base/50',
                    !available && 'opacity-35 cursor-not-allowed hover:bg-transparent hover:text-bp-muted',
                  )}
                  title={available ? `跳转到「${sec.label}」` : `源码中未找到「${sec.label}」`}
                >
                  {sec.label}
                </button>
              );
            })}
          </nav>
        </Card>

        <Card className="min-w-0 overflow-hidden" noPadding>
          <div className="flex items-center gap-1 px-3 py-2 border-b border-bp-border bg-bp-base/40">
            <button
              type="button"
              onClick={() => setActiveTab('tex')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors',
                activeTab === 'tex'
                  ? 'bg-bp-cyan/15 text-bp-cyan'
                  : 'text-bp-muted hover:text-bp-text',
              )}
            >
              <FileText className="w-3.5 h-3.5" />
              report.tex
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('bib')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors',
                activeTab === 'bib'
                  ? 'bg-bp-cyan/15 text-bp-cyan'
                  : 'text-bp-muted hover:text-bp-text',
              )}
            >
              <FileText className="w-3.5 h-3.5" />
              references.bib
            </button>
            <span className="ml-auto text-[11px] text-bp-muted">
              {activeTab === 'tex' ? `${tex.length.toLocaleString()} 字符` : `${bib.length.toLocaleString()} 字符`}
            </span>
          </div>
          <textarea
            ref={textareaRef}
            value={activeTab === 'tex' ? tex : bib}
            onChange={(e) => {
              if (activeTab === 'tex') setTex(e.target.value);
              else setBib(e.target.value);
            }}
            spellCheck={false}
            className="w-full min-h-[calc(100vh-260px)] px-3 py-3 bg-[#0f1419] text-[#d6deeb] font-mono text-[12.5px] leading-5 resize-y border-0 outline-none focus:ring-0"
            placeholder={activeTab === 'tex' ? '% LaTeX source…' : '% BibTeX entries…'}
          />
        </Card>

        <Card className="min-w-0">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-bp-text">PDF 预览</p>
            <p className="text-xs text-bp-muted">编译后自动刷新</p>
          </div>
          <ReportPdfPreview
            reportId={reportId}
            refreshKey={pdfRefreshKey}
            regenerating={compiling}
          />
        </Card>
      </div>
    </div>
  );
}
