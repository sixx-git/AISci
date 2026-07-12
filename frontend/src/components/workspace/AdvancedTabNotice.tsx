import { Link } from 'react-router-dom';
import { ArrowRight, Info } from 'lucide-react';
import { buildProjectTabUrl } from '@/lib/projectNavigation';

interface AdvancedTabNoticeProps {
  projectId: string;
  tab: 'prompts' | 'logs';
}

const COPY: Record<AdvancedTabNoticeProps['tab'], { title: string; hint: string; primary: string }> = {
  prompts: {
    title: 'Prompt 管理已收纳至高级入口',
    hint: '日常修订请在工作流 / 人在回路中使用「编辑 Prompt」；此处保留全局预设与 8 阶段覆盖。',
    primary: '前往工作流',
  },
  logs: {
    title: '运行日志已收纳至工作流',
    hint: '阶段排查请在工作流节点详情查看日志；此处保留完整运行历史与模型参数。',
    primary: '前往工作流',
  },
};

export function AdvancedTabNotice({ projectId, tab }: AdvancedTabNoticeProps) {
  const copy = COPY[tab];
  return (
    <div className="mb-4 p-3 rounded-bp border border-bp-cyan/20 bg-bp-cyan/5 flex flex-wrap items-start gap-3 text-sm">
      <Info className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-bp-text">{copy.title}</p>
        <p className="text-xs text-bp-muted mt-1">{copy.hint}</p>
      </div>
      <Link
        to={buildProjectTabUrl(projectId, 'workflow')}
        className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:underline shrink-0"
      >
        {copy.primary}
        <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}
