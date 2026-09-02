import { useEffect, useId, useState } from 'react';
import { Info, X } from 'lucide-react';
import { Button } from '@/components/Button';

const STORAGE_KEY = 'aisci_welcome_notice_seen_v3';

function hasSeenWelcomeNotice(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function markWelcomeNoticeSeen(): void {
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // ignore quota / private mode
  }
}

/**
 * 挑战杯展示说明弹窗：每个浏览器仅在首次打开时显示一次。
 */
export function WelcomeNoticeModal() {
  const [open, setOpen] = useState(() => !hasSeenWelcomeNotice());
  const titleId = useId();

  const dismiss = () => {
    markWelcomeNoticeSeen();
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') dismiss();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-bp-base/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="w-full max-w-xl rounded-xl border border-bp-cyan/30 bg-[#161b22] shadow-bp-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="shrink-0 w-10 h-10 rounded-bp bg-bp-cyan/15 border border-bp-cyan/30 flex items-center justify-center">
              <Info className="w-5 h-5 text-bp-cyan" />
            </div>
            <div className="min-w-0">
              <h3 id={titleId} className="text-base font-semibold text-bp-cyan">
                挑战杯展示说明
              </h3>
              <p className="text-xs text-bp-muted mt-1">
                阿里云榜题 · 交互前端演示
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={dismiss}
            className="shrink-0 p-1 rounded-bp text-bp-muted hover:text-bp-text hover:bg-bp-cyan-tint/30 transition-colors"
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-4">
          <div className="rounded-bp border border-bp-border bg-bp-base/50 px-4 py-3 space-y-3 text-sm leading-relaxed text-bp-text max-h-[70vh] overflow-y-auto">
            <p>
              您好！我们是挑战杯·中国青年科技创新“揭榜挂帅”擂台赛，参加阿里云榜题：基于国产开源大模型的
              AI Scientist 的研发与应用（题目编号：
              <span className="font-mono text-bp-cyan">XH-202619</span>
              ），队伍编号
              <span className="font-mono text-bp-cyan"> 592929</span>
              。
            </p>
            <p>
              本项目以赛道一方向 1 AB
              为重点，围绕两大研究方向展开，并以三大创新机制支撑完整闭环、可追溯的科学假设生成；依托迭代实验模块，实现研究方案的沙箱运行与自主反馈优化。同时完成「科学影响力预测」赛题：对上传论文生成高质量评分表并进行元数据处理，开展科研影响力分析与偏差解释。
            </p>
            <p>
              在此进行可交互前端页面的展示。由于云端数据库免费额度有限，在此只上传了两个完整项目和全量的最终报告。
            </p>
          </div>

          <div className="flex justify-end">
            <Button size="sm" variant="primary" onClick={dismiss}>
              我知道了
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
