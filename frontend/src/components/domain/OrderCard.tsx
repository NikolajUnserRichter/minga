import { Order, OrderItem } from '../../types';
import { OrderStatusBadge, formatDate, getRelativeDate } from '../ui';
import { User, Calendar, Package, Check, Truck } from 'lucide-react';

interface OrderCardProps {
  order: Order;
  onMarkReady?: () => void;
  onMarkDelivered?: () => void;
  onClick?: () => void;
}

export function OrderCard({ order, onMarkReady, onMarkDelivered, onClick }: OrderCardProps) {
  const totalValue = order.positionen?.reduce(
    (sum, item) => sum + (item.menge * (item.preis_pro_einheit || 0)),
    0
  ) || 0;

  const canMarkReady = order.status === 'IN_PRODUKTION' || order.status === 'BESTAETIGT';
  const canMarkDelivered = order.status === 'BEREIT';

  return (
    <div
      className={`card ${onClick ? 'cursor-pointer card-hover' : ''}`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-sm font-mono text-gray-500">#{order.id.slice(0, 8)}</span>
            <h3 className="font-semibold text-gray-900 mt-1">{order.kunde?.name || 'Unbekannt'}</h3>
          </div>
          <OrderStatusBadge status={order.status} />
        </div>

        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>Lieferung: {formatDate(order.liefer_datum)}</span>
            <span className="text-minga-600 font-medium">({getRelativeDate(order.liefer_datum)})</span>
          </div>
        </div>

        {/* Order Items */}
        {order.positionen && order.positionen.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-sm font-medium text-gray-700 mb-2">Positionen:</p>
            <div className="space-y-1">
              {order.positionen.slice(0, 3).map((item, idx) => (
                <div key={idx} className="flex justify-between text-sm">
                  <span className="text-gray-600">
                    {item.seed?.name || 'Produkt'} {item.menge} {item.einheit}
                  </span>
                  {item.preis_pro_einheit && (
                    <span className="text-gray-900">
                      {(item.menge * item.preis_pro_einheit).toFixed(2)}
                    </span>
                  )}
                </div>
              ))}
              {order.positionen.length > 3 && (
                <p className="text-sm text-gray-500">
                  +{order.positionen.length - 3} weitere Positionen
                </p>
              )}
            </div>
          </div>
        )}

        {/* Total */}
        <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between">
          <span className="font-medium text-gray-700">Gesamt:</span>
          <span className="font-bold text-gray-900">{totalValue.toFixed(2)}</span>
        </div>

        {/* Actions */}
        {(canMarkReady || canMarkDelivered) && (
          <div className="mt-4 flex gap-2">
            {canMarkReady && onMarkReady && (
              <button
                className="btn btn-success btn-sm flex-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkReady();
                }}
              >
                <Check className="w-4 h-4" />
                Bereit
              </button>
            )}
            {canMarkDelivered && onMarkDelivered && (
              <button
                className="btn btn-primary btn-sm flex-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkDelivered();
                }}
              >
                <Truck className="w-4 h-4" />
                Geliefert
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Compact row version for lists
interface OrderRowProps {
  order: Order;
  onClick?: () => void;
}

export function OrderRow({ order, onClick }: OrderRowProps) {
  const totalValue = order.positionen?.reduce(
    (sum, item) => sum + (item.menge * (item.preis_pro_einheit || 0)),
    0
  ) || 0;

  return (
    <div
      className={`flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg ${
        onClick ? 'cursor-pointer hover:bg-gray-50' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-500">#{order.id.slice(0, 8)}</span>
            <span className="font-medium">{order.kunde?.name}</span>
          </div>
          <p className="text-sm text-gray-500">
            {order.positionen?.length || 0} Position(en) | {formatDate(order.liefer_datum)}
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
