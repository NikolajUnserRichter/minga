import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import {
  Search,
  LayoutDashboard,
  Sprout,
  Layers,
  Scissors,
  Users,
  FileText,
  RefreshCw,
  TrendingUp,
  Target,
  BarChart3,
  Settings,
  UserCog,
  Warehouse,
  Receipt,
  Tag,
  Plus,
  ArrowRight,
} from 'lucide-react';

interface CommandItem {
  id: string;
  label: string;
  section: string;
  icon: React.ComponentType<{ className?: string }>;
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const go = useCallback(
    (path: string) => {
      navigate(path);
      onClose();
    },
    [navigate, onClose],
  );

  const commands: CommandItem[] = useMemo(
    () => [
      // Navigation
      { id: 'nav-dashboard', label: 'Dashboard', section: 'Navigation', icon: LayoutDashboard, action: () => go('/dashboard'), keywords: ['home', 'übersicht'] },
      { id: 'nav-analytics', label: 'Analytics', section: 'Navigation', icon: BarChart3, action: () => go('/analytics'), keywords: ['auswertung', 'umsatz'] },
      { id: 'nav-seeds', label: 'Saatgut', section: 'Navigation', icon: Sprout, action: () => go('/seeds'), keywords: ['samen', 'seed'] },
      { id: 'nav-products', label: 'Produkte', section: 'Navigation', icon: Tag, action: () => go('/products'), keywords: ['artikel', 'ware'] },
      { id: 'nav-inventory', label: 'Lagerverwaltung', section: 'Navigation', icon: Warehouse, action: () => go('/inventory'), keywords: ['bestand', 'lager', 'stock'] },
      { id: 'nav-production', label: 'Wachstumschargen', section: 'Navigation', icon: Layers, action: () => go('/production'), keywords: ['chargen', 'batch'] },
      { id: 'nav-harvests', label: 'Ernten', section: 'Navigation', icon: Scissors, action: () => go('/harvests'), keywords: ['ernte', 'harvest'] },
      { id: 'nav-customers', label: 'Kunden', section: 'Navigation', icon: Users, action: () => go('/customers'), keywords: ['kunde', 'customer'] },
      { id: 'nav-orders', label: 'Bestellungen', section: 'Navigation', icon: FileText, action: () => go('/orders'), keywords: ['bestellung', 'order'] },
      { id: 'nav-subscriptions', label: 'Abonnements', section: 'Navigation', icon: RefreshCw, action: () => go('/subscriptions'), keywords: ['abo', 'subscription'] },
      { id: 'nav-invoices', label: 'Rechnungen', section: 'Navigation', icon: Receipt, action: () => go('/invoices'), keywords: ['rechnung', 'invoice'] },
      { id: 'nav-forecasting', label: 'Prognosen', section: 'Navigation', icon: TrendingUp, action: () => go('/forecasting'), keywords: ['forecast', 'prognose'] },
      { id: 'nav-suggestions', label: 'Produktionsvorschläge', section: 'Navigation', icon: Target, action: () => go('/suggestions'), keywords: ['vorschlag'] },
      { id: 'nav-accuracy', label: 'Accuracy Reports', section: 'Navigation', icon: BarChart3, action: () => go('/accuracy'), keywords: ['genauigkeit'] },
      { id: 'nav-settings', label: 'Einstellungen', section: 'Navigation', icon: Settings, action: () => go('/settings') },
      { id: 'nav-users', label: 'Benutzerverwaltung', section: 'Navigation', icon: UserCog, action: () => go('/users'), keywords: ['benutzer'] },
      // Quick actions
      { id: 'action-new-order', label: 'Neue Bestellung erstellen', section: 'Aktionen', icon: Plus, action: () => go('/orders?action=create'), keywords: ['bestellung', 'order', 'neu'] },
      { id: 'action-new-batch', label: 'Neue Aussaat anlegen', section: 'Aktionen', icon: Plus, action: () => go('/production?action=create'), keywords: ['aussaat', 'batch', 'chargen', 'neu'] },
      { id: 'action-new-invoice', label: 'Neue Rechnung erstellen', section: 'Aktionen', icon: Plus, action: () => go('/invoices?action=create'), keywords: ['rechnung', 'invoice', 'neu'] },
      { id: 'action-new-customer', label: 'Neuen Kunden anlegen', section: 'Aktionen', icon: Plus, action: () => go('/customers?action=create'), keywords: ['kunde', 'customer', 'neu'] },
    ],
    [go],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(q) ||
        cmd.section.toLowerCase().includes(q) ||
        cmd.keywords?.some((k) => k.includes(q)),
    );
  }, [query, commands]);

  // Group by section
  const sections = useMemo(() => {
    const map = new Map<string, CommandItem[]>();
    for (const item of filtered) {
      const arr = map.get(item.section) || [];
      arr.push(item);
      map.set(item.section, arr);
    }
    return Array.from(map.entries());
  }, [filtered]);

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Clamp selectedIndex
  useEffect(() => {
    if (selectedIndex >= filtered.length) {
      setSelectedIndex(Math.max(0, filtered.length - 1));
    }
  }, [filtered.length, selectedIndex]);

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.querySelector('[data-selected="true"]');
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((i) => (i + 1) % filtered.length);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
          break;
        case 'Enter':
          e.preventDefault();
          filtered[selectedIndex]?.action();
          break;
        case 'Escape':
          onClose();
          break;
      }
    },
    [filtered, selectedIndex, onClose],
  );

  if (!open) return null;

  let flatIndex = 0;

  return createPortal(
    <div className="fixed inset-0 z-[1060] animate-fade-in" onKeyDown={handleKeyDown}>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="fixed inset-x-0 top-[15%] mx-auto w-full max-w-lg animate-scale-in">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 border-b border-gray-200 dark:border-gray-700">
            <Search className="w-5 h-5 text-gray-400 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Seite, Aktion oder Befehl suchen…"
              className="w-full py-3.5 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none text-sm"
            />
            <kbd className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 text-xs text-gray-400 border border-gray-300 dark:border-gray-600 rounded">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[360px] overflow-y-auto py-2">
            {filtered.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                Keine Ergebnisse für &ldquo;{query}&rdquo;
              </div>
            ) : (
              sections.map(([section, items]) => (
                <div key={section}>
                  <p className="px-4 pt-3 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {section}
                  </p>
                  {items.map((item) => {
                    const idx = flatIndex++;
                    const isSelected = idx === selectedIndex;
                    return (
                      <button
                        key={item.id}
                        data-selected={isSelected}
                        onClick={() => item.action()}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          isSelected
                            ? 'bg-minga-50 text-minga-700 dark:bg-minga-900/30 dark:text-minga-400'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                        }`}
                      >
                        <item.icon className="w-4 h-4 flex-shrink-0 opacity-60" />
                        <span className="flex-1 text-left">{item.label}</span>
                        {isSelected && <ArrowRight className="w-4 h-4 opacity-40" />}
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-400">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <kbd className="px-1 border border-gray-300 dark:border-gray-600 rounded">↑</kbd>
                <kbd className="px-1 border border-gray-300 dark:border-gray-600 rounded">↓</kbd>
                navigieren
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 border border-gray-300 dark:border-gray-600 rounded">↵</kbd>
                ausführen
              </span>
            </div>
            <span>{filtered.length} Ergebnisse</span>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
