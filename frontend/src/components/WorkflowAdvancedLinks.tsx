import { Link } from 'react-router-dom';
import { SlidersHorizontal, ScrollText } from 'lucide-react';
import { buildProjectTabUrl } from '@/lib/projectNavigation';

interface WorkflowAdvancedLinksProps {
  projectId: string;
  promptStage?: string;
}

export function WorkflowAdvancedLinks({ projectId, promptStage }: WorkflowAdvancedLinksProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-bp-muted mt-2">
      <span>高级：</span>
      <Link
        to={buildProjectTabUrl(projectId, 'prompts', promptStage ? { prompt_stage: promptStage } : undefined)}
        className="inline-flex items-center gap-1 text-bp-cyan hover:underline"
      >
        <SlidersHorizontal className="w-3.5 h-3.5" />
        Prompt 全局管理
      </Link>
      <span className="text-bp-border">·</span>
      <Link
        to={buildProjectTabUrl(projectId, 'logs')}
        className="inline-flex items-center gap-1 text-bp-cyan hover:underline"
      >
        <ScrollText className="w-3.5 h-3.5" />
        完整运行日志
      </Link>
    </div>
  );
}
