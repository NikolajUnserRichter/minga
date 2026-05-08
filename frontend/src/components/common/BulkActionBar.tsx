import { ReactNode } from 'react';
import { X } from 'lucide-react';

interface BulkActionBarProps {
  count: number;
  onClear: () => void;
  children: ReactNode;
}

/**
 * Floating bar that appears when items are selected.
 * Renders action buttons passed as children.
 */
export default function BulkActionBar({ count, onClear, children }: BulkActionBarProps) {
  if (count === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-slide-up">
      <div className="flex items-center gap-3 px-5 py-3 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-xl shadow-2xl">
        <span className="text-sm font-medium whitespace-nowrap">
          {count} ausgewählt
        </span>
        <div className="w-px h-5 bg-gray-600 dark:bg-gray-300" />
        <div className="flex items-center gap-2">{children}</div>
        <div className="w-px h-5 bg-gray-600 dark:bg-gray-300" />
        <button
          onClick={onClear}
          className="p-1 hover:bg-gray-700 dark:hover:bg-gray-200 rounded-md transition-colors"
          title="Auswahl aufheben"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
