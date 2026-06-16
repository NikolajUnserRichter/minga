import { useEffect, useState } from 'react';

/**
 * Verzögert den Wert um `delay` ms. Nützlich für Such-Eingaben, damit
 * nicht bei jedem Tastendruck ein Request feuert.
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
