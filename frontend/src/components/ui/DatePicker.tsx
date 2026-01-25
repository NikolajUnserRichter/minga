import { forwardRef, InputHTMLAttributes } from 'react';
import { Calendar } from 'lucide-react';

interface DatePickerProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  error?: string;
  hint?: string;
  required?: boolean;
}

export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(
  ({ label, error, hint, required, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="form-group">
        {label && (
          <label htmlFor={inputId} className={`label ${required ? 'label-required' : ''}`}>
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            type="date"
            id={inputId}
            className={`input pr-10 ${error ? 'input-error' : ''} ${className}`}
            aria-invalid={error ? 'true' : 'false'}
            {...props}
          />
          <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {hint && !error && <p className="form-hint">{hint}</p>}
      </div>
    );
  }
);

DatePicker.displayName = 'DatePicker';

// Helper to format date for display
export function formatDate(dateString: string | Date, format: 'short' | 'long' | 'iso' = 'short'): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString;

  if (isNaN(date.getTime())) return '-';

  const options: Intl.DateTimeFormatOptions =
    format === 'long'
      ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
      : format === 'short'
      ? { day: '2-digit', month: '2-digit', year: 'numeric' }
      : { year: 'numeric', month: '2-digit', day: '2-digit' };

  return format === 'iso'
    ? date.toISOString().split('T')[0]
    : date.toLocaleDateString('de-DE', options);
}

// Helper to get relative date description
export function getRelativeDate(dateString: string): string {
  const date = new Date(dateString);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);

  const diffDays = Math.round((date.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Heute';
  if (diffDays === 1) return 'Morgen';
  if (diffDays === -1) return 'Gestern';
  if (diffDays > 0 && diffDays <= 7) return `In ${diffDays} Tagen`;
  if (diffDays < 0 && diffDays >= -7) return `Vor ${Math.abs(diffDays)} Tagen`;

  return formatDate(dateString);
}
