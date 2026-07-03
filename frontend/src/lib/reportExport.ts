const DEFAULT_REPORT_TITLE = '科学假设与研究计划';

/** 将报告标题转为安全的下载文件名（含扩展名） */
export function buildReportDownloadFilename(
  title: string | undefined | null,
  extension: string,
  fallback = DEFAULT_REPORT_TITLE,
): string {
  const ext = extension.replace(/^\./, '');
  const base = (title || fallback)
    .trim()
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .slice(0, 100)
    .trim();
  return `${base || fallback}.${ext}`;
}

export function getReportDisplayTitle(
  title?: string | null,
  paperTitle?: string | null,
): string {
  return (title || paperTitle || DEFAULT_REPORT_TITLE).trim() || DEFAULT_REPORT_TITLE;
}
