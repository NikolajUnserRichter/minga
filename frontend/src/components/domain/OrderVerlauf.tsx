import { useQuery } from '@tanstack/react-query';
import { History } from 'lucide-react';
import { Button } from '../ui';
import { getErrorMessage } from '../../services/errors';
import { bestellverlaufApi } from '../../services/bestellverlaufApi';
import { verlaufAufbereiten } from '../../services/bestellverlauf';

/**
 * Verlauf einer Bestellung im Belege-Dialog (Paket 4.1, Abschnitt V): wann,
 * wer, was, Status alt → neu, Grund — älteste zuerst. Schlüssel unter
 * 'orders', damit invalidateOrderViews (Statuswechsel, Quittieren,
 * Bearbeiten) den Verlauf mit neu lädt.
 */
export function OrderVerlauf({ orderId, open }: { orderId: string; open: boolean }) {
  const verlauf = useQuery({
    queryKey: ['orders', orderId, 'verlauf'],
    queryFn: () => bestellverlaufApi.liste(orderId),
    enabled: open && !!orderId,
  });
  const zeilen = verlauf.data ? verlaufAufbereiten(verlauf.data) : [];

  return (
    <section>
      <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200 mb-3">
        <History className="w-4 h-4" />
        Verlauf
      </h3>
      {verlauf.isLoading ? (
        <p role="status" className="text-sm text-gray-500 dark:text-gray-400">Verlauf wird geladen…</p>
      ) : verlauf.isError ? (
        <div role="alert" className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
          <span>{getErrorMessage(verlauf.error, 'Verlauf konnte nicht geladen werden')}</span>
          <Button size="sm" variant="secondary" onClick={() => verlauf.refetch()}>Erneut laden</Button>
        </div>
      ) : zeilen.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">
          Noch keine Einträge. Protokolliert werden Statuswechsel, Importe und Änderungen ab der Bestätigung.
        </p>
      ) : (
        <ol className="space-y-2">
          {zeilen.map((z) => (
            <li key={z.id} className="border rounded p-2 text-sm dark:border-gray-700">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{z.zeit}</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">{z.aktion}</span>
                {z.status && <span className="text-gray-700 dark:text-gray-300">{z.status}</span>}
                <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">{z.wer}</span>
              </div>
              {z.details.length > 0 && (
                <ul className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                  {z.details.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              )}
              {z.grund && <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">Grund: {z.grund}</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
