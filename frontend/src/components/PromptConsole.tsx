import { PromptStageEditor } from '@/components/PromptStageEditor';

interface PromptConsoleProps {
  projectId: string;
  stage: string;
  open: boolean;
  onClose: () => void;
}

export function PromptConsole({ projectId, stage, open, onClose }: PromptConsoleProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="w-full max-w-3xl max-h-[85vh] overflow-hidden rounded-xl border border-gray-700 bg-[#161b22] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
          <h3 className="text-sm font-semibold text-white">Prompt 编辑</h3>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white text-sm">
            关闭
          </button>
        </div>
        <div className="p-4 flex-1 overflow-y-auto min-h-0">
          <PromptStageEditor projectId={projectId} stage={stage} />
        </div>
      </div>
    </div>
  );
}

export default PromptConsole;
