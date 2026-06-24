import { BookOpen, Play } from 'lucide-react';
import { Button } from '@/components/Button';
import { StatusBadge } from '@/components/StatusBadge';
import type { StatusType } from '@/components/StatusBadge';
import { ProjectMetaBar } from '@/components/workspace/ProjectMetaBar';

interface ProjectWorkspaceHeaderProps {
  projectName: string;
  status: StatusType;
  researchField: string;
  projectModeLabel: string;
  currentStage: string;
  description?: string;
  createdAtLabel: string;
  onUploadLiterature: () => void;
  onRunPipeline: () => void;
}

export function ProjectWorkspaceHeader({
  projectName,
  status,
  researchField,
  projectModeLabel,
  currentStage,
  description,
  createdAtLabel,
  onUploadLiterature,
  onRunPipeline,
}: ProjectWorkspaceHeaderProps) {
  return (
    <div className="mb-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <h1 className="text-3xl font-bold text-bp-text truncate">{projectName}</h1>
            <StatusBadge status={status} />
          </div>
          <ProjectMetaBar
            researchField={researchField}
            projectModeLabel={projectModeLabel}
            currentStage={currentStage}
            description={description}
            createdAtLabel={createdAtLabel}
          />
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" icon={<BookOpen className="w-4 h-4" />} onClick={onUploadLiterature}>
            上传文献
          </Button>
          <Button variant="primary" icon={<Play className="w-4 h-4" />} onClick={onRunPipeline}>
            运行 Pipeline
          </Button>
        </div>
      </div>
    </div>
  );
}
