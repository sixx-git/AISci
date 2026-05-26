import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function toValidDate(date?: string | Date | null): Date | null {
  if (!date) return null;

  const value = date instanceof Date ? date : new Date(date);

  if (Number.isNaN(value.getTime())) {
    return null;
  }

  return value;
}

export function formatDate(date?: string | Date | null): string {
  const value = toValidDate(date);

  if (!value) return '-';

  return value.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(date?: string | Date | null): string {
  const value = toValidDate(date);

  if (!value) return '-';

  return value.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function truncateText(
  text?: string | null,
  maxLength: number = 100,
): string {
  if (!text || maxLength <= 0) return '';
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}