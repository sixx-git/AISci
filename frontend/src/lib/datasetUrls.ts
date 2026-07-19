/** 将数据集下载地址规范为可点击的绝对 URL（修复 HF org/name 相对 ID）。 */
export function toAbsoluteDatasetUrl(url?: string | null, name?: string | null): string {
  let raw = (url || '').trim();
  if (!raw && name && /^[\w.-]+\/[\w.-]+$/.test(name.trim())) {
    raw = name.trim();
  }
  if (!raw) return '';

  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith('//')) return `https:${raw}`;

  // 站内相对 API：拼当前 origin
  if (raw.startsWith('/')) {
    if (typeof window !== 'undefined' && window.location?.origin) {
      return `${window.location.origin}${raw}`;
    }
    return raw;
  }

  // HuggingFace dataset id: org/name
  const cleaned = raw.replace(/\s+/g, '');
  const m = /^(?:datasets\/)?([\w.-]+\/[\w.-]+)(?:\/.*)?$/.exec(cleaned);
  if (m) {
    return `https://huggingface.co/datasets/${m[1]}`;
  }

  return raw;
}
