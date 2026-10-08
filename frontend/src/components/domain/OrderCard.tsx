import { useState, type MouseEvent } from 'react';
import { OrderWithCustomer } from '../../types';
import { OrderStatusBadge, formatDate, getRelativeDate } from '../ui';
import { Calendar, Check, ClipboardCheck, Truck } from 'lucide-react';

// Darf ein Promise liefern (z. B. mutateAsync); Fehler meldet der Aufrufer selbst.
type Aktion = () => unknown;

interface OrderCardProps {
  order: OrderWithCustomer;
  onConfirm?: Aktion;
  onMarkReady?: Aktion;
  onMarkDelivered?: Aktion;
  onClick?: () => void;
}

export function OrderCard({ order, onConfirm, onMarkReady, onMarkDelivered, onClick }: OrderCardProps) {
  // Solange ein Statuswechsel läuft, sind alle Knöpfe der Karte gesperrt.
  const [busy, setBusy] = useState(false);
  const run = (aktion: Aktion) => async (e: MouseEvent) => {
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    try {
      await aktion();
    } catch {
      // Der Aufrufer zeigt den Fehler als Toast; hier nur die Sperre lösen.
    } finally {
      setBusy(false);
    }
  };
  // Prefer backend-computed total_gross; fall back to legacy gesamtwert / line-summation
  const totalValue = Number(
    (order as any).total_gross ??
    order.gesamtwert ??
    order.positionen?.reduce((sum, item) => sum + (item.menge * (item.preis_pro_einheit || 0)), 0) ??
    0
  ) || 0;

  // Eine neu erfasste Bestellung steht auf ENTWURF. Ohne diesen Schritt
  // ist die Statuskette aus der Oberfläche nicht begehbar, weil
  // "Gepackt" erst ab BESTAETIGT erscheint.
  const canConfirm = order.status === 'ENTWURF';
  // "Gepackt" und "Geliefert" stehen ab Bestätigt nebeneinander und behalten
  // ihren Platz: nach "Gepackt" bleibt der Knopf ausgegraut stehen. Vorher
  // rückte "Geliefert" an dieselbe Stelle, ein Doppelklick löste beide
  // Wechsel aus (Audit-Log 07.10.: BESTAETIGT → IN_PRODUKTION → GELIEFERT
  // in derselben Sekunde).
  const showPackDeliver = order.status === 'BESTAETIGT' || order.status === 'IN_PRODUKTION';
  const isPacked = order.status === 'IN_PRODUKTION';

  return (
    <div
      className={`card ${onClick ? 'cursor-pointer card-hover' : ''}`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-sm font-mono text-gray-500 dark:text-gray-400">{order.order_number || `#${order.id.slice(0, 8)}`}</span>
            <h3 className="font-semibold text-gray-900 dark:text-white mt-1">{order.kunde?.name || 'Unbekannt'}</h3>
          </div>
          <OrderStatusBadge status={order.status} />
        </div>

        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>Lieferung: {formatDate((order.liefer_datum || (order as any).requested_delivery_date))}</span>
            <span className="text-minga-600 dark:text-minga-400 font-medium">({getRelativeDate((order.liefer_datum || (order as any).requested_delivery_date))})</span>
          </div>
        </div>

        {/* Order Items */}
        {order.positionen && order.positionen.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Positionen:</p>
            <div className="space-y-1">
              {order.positionen.slice(0, 3).map((item, idx) => {
                const name = (item as any).product_name || item.seed?.name || 'Produkt';
                const qty = Number(item.menge ?? (item as any).quantity ?? 0);
                const unit = item.einheit ?? (item as any).unit ?? '';
                const price = Number(item.preis_pro_einheit ?? (item as any).unit_price ?? 0);
                return (
                  <div key={idx} className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">
                      {name} {qty} {unit}
                    </span>
                    {price > 0 && (
                      <span className="text-gray-900 dark:text-white">
                        {(qty * price).toFixed(2)}
                      </span>
                    )}
                  </div>
                );
              })}
              {order.positionen.length > 3 && (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  +{order.positionen.length - 3} weitere Positionen
                </p>
              )}
            </div>
          </div>
        )}

        {/* Total */}
        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex justify-between">
          <span className="font-medium text-gray-700 dark:text-gray-300">Gesamt:</span>
          <span className="font-bold text-gray-900 dark:text-white">{totalValue.toFixed(2)}</span>
        </div>

        {/* Actions */}
        {((canConfirm && onConfirm) || (showPackDeliver && onMarkReady && onMarkDelivered)) && (
          <div className="mt-4 flex gap-2">
            {canConfirm && onConfirm && (
              <button
                className="btn btn-primary btn-sm flex-1"
                disabled={busy}
                onClick={run(onConfirm)}
              >
                <ClipboardCheck className="w-4 h-4" />
                Bestätigen
              </button>
            )}
            {showPackDeliver && onMarkReady && onMarkDelivered && (
              <>
                <button
                  className="btn btn-success btn-sm flex-1"
                  disabled={busy || isPacked}
                  title={isPacked ? 'Bereits gepackt' : undefined}
                  onClick={run(onMarkReady)}
                >
                  <Check className="w-4 h-4" />
                  Gepackt
                </button>
                <button
                  className="btn btn-primary btn-sm flex-1"
                  disabled={busy}
                  onClick={run(onMarkDelivered)}
                >
                  <Truck className="w-4 h-4" />
                  Geliefert
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Compact row version for lists
interface OrderRowProps {
  order: OrderWithCustomer;
  onClick?: () => void;
}

export function OrderRow({ order, onClick }: OrderRowProps) {
  const totalValue = order.positionen?.reduce(
    (sum, item) => sum + (item.menge * (item.preis_pro_einheit || 0)),
    0
  ) || 0;

  return (
    <div
      className={`flex items-center justify-between p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg ${onClick ? 'cursor-pointer hover:bg-gray-50 dark:bg-gray-700/50' : ''
        }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-500 dark:text-gray-400">{order.order_number || `#${order.id.slice(0, 8)}`}</span>
            <span className="font-medium">{order.kunde?.name}</span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {order.positionen?.length || 0} Position(en) | {formatDate((order.liefer_datum || (order as any).requested_delivery_date))}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span className="font-medium">{totalValue.toFixed(2)}</span>
        <OrderStatusBadge status={order.status} />
      </div>
    </div>
  );
}
