import { Card } from '@/components/Card';
import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  colorClass?: string;
}

export function StatCard({ label, value, icon, colorClass = 'text-primary-400' }: StatCardProps) {
  // 根据 text color class 推导背景色：text-xxx-400 → bg-xxx-500/15
  const bgClass = colorClass.replace(/^text-/, 'bg-').replace(/-400$/, '-500/15');

  return (
    <Card className="text-center">
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-3', bgClass)}>
        {icon}
      </div>
      <div className={cn('text-3xl font-bold', colorClass)}>{value}</div>
      <div className="text-gray-400 mt-1 text-sm">{label}</div>
    </Card>
  );
}