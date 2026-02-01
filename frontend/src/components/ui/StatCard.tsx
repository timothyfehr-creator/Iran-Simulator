import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string;
  unit?: string;
  trend?: 'up' | 'down';
  status?: 'success' | 'warning' | 'danger' | 'neutral';
  icon?: ReactNode;
}

const statusColors = {
  success: 'text-war-room-success',
  warning: 'text-war-room-warning',
  danger: 'text-war-room-danger',
  neutral: 'text-war-room-text-primary',
} as const;

export function StatCard({ label, value, unit, trend, status = 'neutral', icon }: StatCardProps) {
  return (
    <div className="panel p-5">
      <div className="flex items-center gap-2 mb-2">
        {icon && <span className="text-war-room-text-secondary">{icon}</span>}
        <span className="text-caption uppercase tracking-wider text-war-room-text-secondary">
          {label}
        </span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-mono font-bold ${statusColors[status]}`}>
          {value}
        </span>
        {unit && (
          <span className="text-caption text-war-room-muted">{unit}</span>
        )}
        {trend && (
          <span className={trend === 'up' ? 'text-war-room-danger' : 'text-war-room-success'}>
            {trend === 'up' ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
          </span>
        )}
      </div>
    </div>
  );
}
