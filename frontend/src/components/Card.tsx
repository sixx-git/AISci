import React from 'react';
import { cn } from '@/lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  /** 是否启用 hover 高亮和发光效果 */
  hover?: boolean;
  /** 是否无内边距（用于图表等场景） */
  noPadding?: boolean;
}

export function Card({
  children,
  title,
  subtitle,
  hover = false,
  noPadding = false,
  className,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        hover ? 'card-hover' : 'card',
        !noPadding && 'p-6',
        className,
      )}
      {...props}
    >
      {(title || subtitle) && (
        <div className="mb-4">
          {title && (
            <h3 className="text-lg font-semibold text-[#F8FAFC]">{title}</h3>
          )}
          {subtitle && (
            <p className="text-sm text-[#94A3B8] mt-1">{subtitle}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}