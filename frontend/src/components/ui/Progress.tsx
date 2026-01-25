interface ProgressProps {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'success' | 'warning' | 'danger';
  showLabel?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: 'progress-sm',
  md: 'progress-md',
  lg: 'progress-lg',
};

const variantClasses = {
  default: 'bg-minga-500',
  success: 'bg-green-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
};

export function Progress({
  value,
  max = 100,
  size = 'md',
  variant = 'default',
  showLabel = false,
  className = '',
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`progress ${sizeClasses[size]} flex-1`}>
        <div
          className={`progress-bar ${variantClasses[variant]}`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        />
      </div>
      {showLabel && <span className="text-sm text-gray-600 min-w-[3rem]">{Math.round(percentage)}%</span>}
    </div>
  );
}

// Capacity indicator variant
interface CapacityIndicatorProps {
  current: number;
  max: number;
  label?: string;
  showValues?: boolean;
}

export function CapacityIndicator({ current, max, label, showValues = true }: CapacityIndicatorProps) {
  const percentage = (current / max) * 100;
  const variant = percentage >= 90 ? 'danger' : percentage >= 70 ? 'warning' : 'success';

  const fillClasses = {
    success: 'capacity-low',
    warning: 'capacity-medium',
    danger: 'capacity-high',
  };

  return (
    <div className="capacity-indicator">
      {label && <span className="text-sm text-gray-600 min-w-[80px]">{label}</span>}
      <div className="capacity-bar flex-1">
        <div
          className={`capacity-fill ${fillClasses[variant]}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      {showValues && (
        <span className="text-sm text-gray-600 min-w-[60px] text-right">
          {current}/{max}
        </span>
      )}
    </div>
  );
}
