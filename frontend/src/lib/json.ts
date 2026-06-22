/** 安全解析 JSON 文本字段 */
export function safeParseJson<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw || !String(raw).trim()) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}
