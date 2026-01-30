import { ReactNode } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  change?: {
    value: string;
    positive?: boolean;
  };
  subtitle?: string;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
}

export function StatCard({ title, value, icon, change, subtitle, variant = 'default', className = '' }: StatCardProps) {
  const variantStyles = {
    default: 'bg-gray-50 text-gray-600',
    primary: 'bg-minga-50 text-minga-600',
    success: 'bg-green-50 text-green-600',
    warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-red-50 text-red-600',
    info: 'bg-blue-50 text-blue-600',
  };

  return (
    <div className={`stat-card ${className}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="stat-card-label">{title}</p>
          <p className="stat-card-value mt-1">{value}</p>
          {change && (
            <p
              className={`stat-card-change flex items-center gap-1 ${change.positive ? 'stat-card-change-positive' : 'stat-card-change-negative'
                }`}
            >
              {change.positive ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
              {change.value}
            </p>
          )}
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
        {icon && (
          <div className={`p-3 rounded-lg ${variantStyles[variant]}`}>{icon}</div>
        )}
      </div>
    </div>
  );
}

// Compact variant for dashboard grids
interface CompactStatProps {
  label: string;
  value: string | number;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}

export function CompactStat({ label, value, variant = 'default' }: CompactStatProps) {
  const variantClasses = {
    default: 'bg-gray-50 text-gray-900',
    success: 'bg-green-50 text-green-700',
    warning: 'bg-amber-50 text-amber-700',
    danger: 'bg-red-50 text-red-700',
  };

  return (
    <div className={`px-4 py-3 rounded-lg ${variantClasses[variant]}`}>
      <p className="text-sm font-medium opacity-75">{label}</p>
      <p className="text-xl font-bold">{value}</p>
    </div>
  );
}
