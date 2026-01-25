interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'spinner-sm',
  md: 'spinner-md',
  lg: 'spinner-lg',
};

export function Spinner({ size = 'md', className = '' }: SpinnerProps) {
  return (
    <div
      className={`spinner ${sizeClasses[size]} ${className}`}
      role="status"
      aria-label="Lädt..."
    >
      <span className="sr-only">Lädt...</span>
    </div>
  );
}

// Full page loading state
export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <Spinner size="lg" className="text-minga-600 mx-auto" />
        <p className="mt-4 text-gray-500">Lädt...</p>
      </div>
    </div>
  );
}

// Inline loading state
export function InlineLoader({ text = 'Lädt...' }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-gray-500">
      <Spinner size="sm" />
      <span>{text}</span>
    </div>
  );
}
