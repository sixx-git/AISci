import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SlidersHorizontal, CheckCircle2, Lock } from 'lucide-react';
import { Card } from '@/components/Card';
import { LoadingState } from '@/components/workspace/LoadingState';
import { PromptStageEditor } from '@/components/PromptStageEditor';
import { PromptPresetBar } from '@/components/PromptPresetBar';
import { PIPELINE_PROMPT_STAGES } from '@/config/promptStages';
import promptService, { type PromptInfo } from '@/services/promptService';
import { cn } from '@/lib/utils';

interface PromptManagementPageProps {
  projectId: string;
  projectMode?: string;
}

export function PromptManagementPage({ projectId, projectMode = 'general' }: PromptManagementPageProps) {
  const [searchParams] = useSearchParams();
  const stageFromUrl = searchParams.get('prompt_stage');
  const initialStage =
    stageFromUrl && PIPELINE_PROMPT_STAGES.some((s) => s.key === stageFromUrl)
      ? stageFromUrl
      : PIPELINE_PROMPT_STAGES[0].key;

  const [selectedStage, setSelectedStage] = useState(initialStage);
  const [overrideMap, setOverrideMap] = useState<Record<string, boolean>>({});
  const [loadingList, setLoadingList] = useState(true);
  const [editorKey, setEditorKey] = useState(0);

  const loadOverrideStatus = useCallback(async () => {
    setLoadingList(true);
    try {
      const results = await Promise.allSettled(
        PIPELINE_PROMPT_STAGES.map((s) => promptService.getPrompt(projectId, s.key)),
      );
      const map: Record<string, boolean> = {};
      results.forEach((r, i) => {
        const key = PIPELINE_PROMPT_STAGES[i].key;
        if (r.status === 'fulfilled' && r.value.code === 200 && r.value.data) {
          map[key] = !!r.value.data.has_override;
        }
      });
      setOverrideMap(map);
    } finally {
      setLoadingList(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadOverrideStatus();
  }, [loadOverrideStatus]);

  useEffect(() => {
    if (stageFromUrl && PIPELINE_PROMPT_STAGES.some((s) => s.key === stageFromUrl)) {
      setSelectedStage(stageFromUrl);
    }
  }, [stageFromUrl]);

  const handleSaved = (info: PromptInfo) => {
    setOverrideMap((prev) => ({ ...prev, [info.stage]: !!info.has_override }));
  };

  const handlePresetApplied = () => {
    loadOverrideStatus();
    setEditorKey((k) => k + 1);
  };

  const selectedMeta = PIPELINE_PROMPT_STAGES.find((s) => s.key === selectedStage);
  const overrideCount = Object.values(overrideMap).filter(Boolean).length;

  return (
    <div className="space-y-4">
      <Card
        title="Prompt 管理"
        subtitle="范式模板库 + 项目级覆盖；报告生成阶段锁定为固定章节模板"
      >
        <div className="flex flex-wrap gap-4 text-xs text-bp-muted">
          <span className="flex items-center gap-1.5">
            <SlidersHorizontal className="w-3.5 h-3.5 text-bp-cyan" />
            {PIPELINE_PROMPT_STAGES.length} 个 Pipeline 阶段 · 其中 7 个可选范式预设
          </span>
          {loadingList ? (
            <span className="text-bp-muted">检查覆盖状态…</span>
          ) : (
            <span>
              已自定义 <span className="text-bp-yellow">{overrideCount}</span> / {PIPELINE_PROMPT_STAGES.length}
            </span>
          )}
        </div>
      </Card>

      <PromptPresetBar
        projectId={projectId}
        stage={selectedStage}
        presetLocked={selectedMeta?.presetLocked}
        onApplied={handlePresetApplied}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[520px]">
        <div className="lg:col-span-4">
          <Card className="p-0 overflow-hidden h-full">
            <div className="px-3 py-2 border-b border-bp-border text-xs font-medium text-bp-muted">
              Pipeline 阶段
            </div>
            <ul className="divide-y divide-bp-border max-h-[calc(100vh-280px)] overflow-y-auto">
              {PIPELINE_PROMPT_STAGES.map((item, idx) => {
                const active = selectedStage === item.key;
                const hasOverride = overrideMap[item.key];
                return (
                  <li key={item.key}>
                    <button
                      type="button"
                      onClick={() => setSelectedStage(item.key)}
                      className={cn(
                        'w-full text-left px-3 py-3 transition-colors',
                        active
                          ? 'bg-bp-cyan-tint border-l-2 border-bp-cyan'
                          : 'hover:bg-bp-panel/60 border-l-2 border-transparent',
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-bp-muted font-mono w-4">{idx + 1}</span>
                            <span className={cn('text-sm font-medium', active ? 'text-bp-cyan' : 'text-bp-text')}>
                              {item.label}
                            </span>
                            {item.presetLocked && (
                              <Lock className="w-3 h-3 text-bp-muted" />
                            )}
                          </div>
                          <p className="text-xs text-bp-muted mt-1 ml-6 line-clamp-2">{item.description}</p>
                        </div>
                        {hasOverride && (
                          <span title="已覆盖">
                            <CheckCircle2 className="w-3.5 h-3.5 text-bp-yellow shrink-0 mt-0.5" />
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>

        <div className="lg:col-span-8">
          <Card className="h-full min-h-[480px] flex flex-col">
            {loadingList ? (
              <LoadingState message="加载 Prompt 阶段列表…" />
            ) : (
              <>
            {selectedMeta?.presetLocked ? (
              <div className="py-8 text-center space-y-2">
                <Lock className="w-8 h-8 text-bp-muted mx-auto" />
                <p className="text-sm text-bp-text">报告生成 Prompt 锁定</p>
                <p className="text-xs text-bp-muted max-w-md mx-auto">
                  研究报告须严格遵循系统固定章节模板（12 章结构），不提供 Sakana/AISci 范式替换。
                  仍可手动编辑下方系统默认模板（不推荐修改章节 Schema）。
                </p>
              </div>
            ) : null}
            <PromptStageEditor
              key={`${selectedStage}-${editorKey}`}
              projectId={projectId}
              stage={selectedStage}
              stageLabel={selectedMeta?.label}
              onSaved={handleSaved}
            />
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default PromptManagementPage;
