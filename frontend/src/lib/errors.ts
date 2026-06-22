/** 从 unknown 错误中提取用户可读消息（配合 api 拦截器抛出的 Error） */
export function getErrorMessage(err: unknown, fallback = '操作失败'): string {
  if (err instanceof Error && err.message) {
    return err.message;
  }
  if (typeof err === 'string' && err.trim()) {
    return err;
  }
  const anyErr = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
  const detail = anyErr?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  const msg = anyErr?.response?.data?.message;
  if (typeof msg === 'string' && msg.trim()) {
    return msg;
  }
  if (typeof anyErr?.message === 'string' && anyErr.message.trim()) {
    return anyErr.message;
  }
  return fallback;
}
