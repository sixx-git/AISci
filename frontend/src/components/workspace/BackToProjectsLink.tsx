import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BackToProjectsLinkProps {
  className?: string;
}

export function BackToProjectsLink({ className }: BackToProjectsLinkProps) {
  return (
    <Link to="/" className={cn('bp-link-back mb-4', className)}>
      <ArrowLeft className="w-4 h-4 mr-2" />
      <span>返回项目列表</span>
    </Link>
  );
}
