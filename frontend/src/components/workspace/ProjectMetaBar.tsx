import { Calendar, Tag, TrendingUp } from 'lucide-react';

interface ProjectMetaBarProps {
  researchField: string;
  projectModeLabel: string;
  currentStage: string;
  description?: string;
  createdAtLabel: string;
}

export function ProjectMetaBar({
  researchField,
  projectModeLabel,
  currentStage,
  description,
  createdAtLabel,
}: ProjectMetaBarProps) {
  return (
    <div className="space-y-2 pb-4 border-b border-bp-cyan-dim">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="bp-chip bp-chip-cyan">
          <Tag className="w-3.5 h-3.5" />
          {researchField}
        </span>
        <span className="bp-chip bp-chip-purple">{projectModeLabel}</span>
        <span className="bp-chip bp-chip-cyan">
          <TrendingUp className="w-3.5 h-3.5" />
          当前阶段：{currentStage}
        </span>
      </div>
      {description && (
        <p className="text-sm text-bp-muted max-w-2xl">{description}</p>
      )}
      <div className="flex items-center gap-2 text-sm text-bp-muted">
        <Calendar className="w-4 h-4" />
        <span>创建于 {createdAtLabel}</span>
      </div>
    </div>
  );
}
