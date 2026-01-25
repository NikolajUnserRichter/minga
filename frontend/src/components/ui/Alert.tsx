import { ReactNode } from 'react';
import { AlertCircle, CheckCircle, AlertTriangle, Info, X } from 'lucide-react';

type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: ReactNode;
  onClose?: () => void;
  className?: string;
}

const variantConfig: Record<AlertVariant, { class: string; icon: ReactNode }> = {
  info: { class: 'alert-info', icon: <Info className="w-5 h-5" /> },
  success: { class: 'alert-success', icon: <CheckCircle className="w-5 h-5" /> },
  warning: { class: 'alert-warning', icon: <AlertTriangle className="w-5 h-5" /> },
  danger: { class: 'alert-danger', icon: <AlertCircle className="w-5 h-5" /> },
};

export function Alert({ variant = 'info', title, children, onClose, className = '' }: AlertProps) {
  const config = variantConfig[variant];

  return (
    <div className={`alert ${config.class} ${className}`} role="alert">
      <div className="flex-shrink-0">{config.icon}</div>
      <div className="flex-1">
        {title && <p className="font-medium mb-1">{title}</p>}
        <div className="text-sm">{children}</div>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="flex-shrink-0 p-1 hover:opacity-80 transition-opacity"
          aria-label="Schließen"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
