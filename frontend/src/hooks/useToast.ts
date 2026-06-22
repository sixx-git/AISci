import { useCallback, useState } from 'react';

export type StatusToastType = 'success' | 'error' | 'loading' | 'info';

export interface StatusToastMessage {
  type: StatusToastType;
  text: string;
}

/** 简单字符串提示（默认 3 秒） */
export function useToast(defaultDurationMs = 3000) {
  const [message, setMessage] = useState<string | null>(null);

  const showAlert = useCallback((msg: string, durationMs = defaultDurationMs) => {
    setMessage(msg);
    window.setTimeout(() => setMessage(null), durationMs);
  }, [defaultDurationMs]);

  const clearAlert = useCallback(() => setMessage(null), []);

  return { message, showAlert, clearAlert };
}

/** 带类型的状态条（error 10s，其余 4s）— 用于文献库等复杂页面 */
export function useStatusToast() {
  const [statusMsg, setStatusMsg] = useState<StatusToastMessage | null>(null);

  const showStatus = useCallback((msg: StatusToastMessage) => {
    setStatusMsg(msg);
    const duration = msg.type === 'error' ? 10000 : 4000;
    window.setTimeout(() => setStatusMsg(null), duration);
  }, []);

  const clearStatus = useCallback(() => setStatusMsg(null), []);

  return { statusMsg, showStatus, clearStatus };
}
