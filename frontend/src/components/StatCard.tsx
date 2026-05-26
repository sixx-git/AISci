import { cn } from '@/lib/utils';
import { Card } from '@/components/Card';

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  colorClass?: string;
}

/**
 * 统一统计卡片 —— 图标 + 数值 + 标签
 */
export function StatCard({ label, value, icon, colorClass = 'text-primary-400' }: StatCardProps) {
  // 从文字颜色推导背景色：text-xxx-400 → bg-xxx-500/15
  const bgClass = colorClass.replace(/^text-/, 'bg-').replace(/-400$/, '-500/15');

  return (
    <Card className="text-center" hover>
      <div className={cn(
        'w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-3',
        bgClass,
      )}>
        {icon}
      </div>
      <div className={cn('text-3xl font-bold', colorClass)}>{value}</div>
      <div className="text-[#94A3B8] mt-1 text-sm">{label}</div>
    </Card>
  );
}