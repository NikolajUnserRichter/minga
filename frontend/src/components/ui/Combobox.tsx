import { useState, useRef, useEffect } from 'react';

export interface ComboboxOption {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

interface ComboboxProps {
  options: ComboboxOption[];
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
  error?: string;
  className?: string;
  disabled?: boolean;
}

/**
 * Combobox – durchsuchbares Dropdown mit Tastatur-Navigation.
 * Eignet sich für lange Listen (Produkte, Kunden, Saatgut-Chargen).
 *
 * Verhalten:
 * - Beim Tippen wird die Liste live gefiltert (Substring, case-insensitive)
 * - Pfeil-Up/Down zum Navigieren, Enter zum Auswählen, Esc zum Schließen
 * - Klick außerhalb schließt die Liste
 */
export function Combobox({
  options,
  value,
  onChange,
  placeholder,
  label,
  required,
  error,
  className,
  disabled,
}: ComboboxProps) {
  const selectedOption = options.find(o => o.value === value);
  const [query, setQuery] = useState<string>(selectedOption?.label ?? '');
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Synchronize displayed text when value changes externally
  useEffect(() => {
    setQuery(selectedOption?.label ?? '');
  }, [value, selectedOption?.label]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        // Restore visible value to the selected one (avoid keeping stale typed text)
        setQuery(selectedOption?.label ?? '');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [selectedOption?.label]);

  const filtered = query.trim().length === 0
    ? options
    : options.filter(o => o.label.toLowerCase().includes(query.trim().toLowerCase()));

  const pick = (opt: ComboboxOption) => {
    if (opt.disabled) return;
    onChange(opt.value);
    setQuery(opt.label);
    setOpen(false);
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setHighlightedIndex(i => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(i => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[highlightedIndex]) {
        pick(filtered[highlightedIndex]);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setQuery(selectedOption?.label ?? '');
    }
  };

  return (
    <div className={`relative ${className || ''}`} ref={wrapperRef}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
      )}
      <input
        type="text"
        value={query}
        disabled={disabled}
        placeholder={placeholder || 'Tippen zum Suchen…'}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlightedIndex(0);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        autoComplete="off"
        className={`w-full px-3 py-2 border ${error ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-md dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-1 focus:ring-minga-500`}
      />
      {open && filtered.length > 0 && (
        <ul
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black/10 dark:ring-white/10"
          role="listbox"
        >
          {filtered.map((opt, i) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={i === highlightedIndex}
              onMouseDown={(e) => {
                // mousedown statt click, sonst feuert das blur des inputs erst
                e.preventDefault();
                pick(opt);
              }}
              onMouseEnter={() => setHighlightedIndex(i)}
              className={`px-3 py-1.5 text-sm cursor-pointer flex justify-between gap-2 ${
                opt.disabled
                  ? 'opacity-50 cursor-not-allowed'
                  : i === highlightedIndex
                    ? 'bg-minga-100 dark:bg-minga-900/30 text-gray-900 dark:text-white'
                    : 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:bg-gray-700'
              }`}
            >
              <span className="truncate">{opt.label}</span>
              {opt.hint && (
                <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{opt.hint}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {open && filtered.length === 0 && (
        <div className="absolute z-10 mt-1 w-full rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black/10 dark:ring-white/10 px-3 py-2 text-sm text-gray-500">
          Keine Treffer
        </div>
      )}
      {error && (
        <p className="mt-1 text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
