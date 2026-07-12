import { RunLogsPage } from '@/components/RunLogsPage';

interface RunHistoryPanelProps {
  projectId: string;
  latestRunId?: string | null;
  refreshKey?: number;
}

/** 工作流内嵌的运行历史（复用 RunLogsPage 嵌入模式） */
export function RunHistoryPanel({ projectId, latestRunId, refreshKey }: RunHistoryPanelProps) {
  return (
    <RunLogsPage
      projectId={projectId}
      embedded
      revalidateKey={refreshKey}
      latestRunId={latestRunId}
    />
  );
}
