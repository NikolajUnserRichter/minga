import { Customer } from '../../types';
import { CustomerTypeBadge, Badge } from '../ui';
import { MapPin, Mail, Phone, Calendar, Edit2, ShoppingCart, RefreshCw } from 'lucide-react';

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

interface CustomerCardProps {
  customer: Customer;
  onEdit?: () => void;
  onCreateOrder?: () => void;
  onManageSubscriptions?: () => void;
  onClick?: () => void;
  stats?: {
    activeSubscriptions?: number;
    monthlyRevenue?: number;
  };
}

export function CustomerCard({
  customer,
  onEdit,
  onCreateOrder,
  onManageSubscriptions,
  onClick,
  stats,
}: CustomerCardProps) {
  return (
    <div
      className={`card card-hover ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className="card-body">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">{customer.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <CustomerTypeBadge type={customer.typ} />
              {!customer.aktiv && <Badge variant="gray">Inaktiv</Badge>}
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-2">
          {customer.email && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Mail className="w-4 h-4 text-gray-400" />
              <a href={`mailto:${customer.email}`} className="hover:text-minga-600">
                {customer.email}
              </a>
            </div>
          )}
          {customer.telefon && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Phone className="w-4 h-4 text-gray-400" />
              <a href={`tel:${customer.telefon}`} className="hover:text-minga-600">
                {customer.telefon}
              </a>
            </div>
          )}
          {customer.adresse && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <MapPin className="w-4 h-4 text-gray-400" />
              <span>{customer.adresse}</span>
            </div>
          )}
          {customer.liefertage && customer.liefertage.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4 text-gray-400" />
              <span>
                Liefertage: {customer.liefertage.map((d) => WEEKDAYS[d]).join(', ')}
              </span>
            </div>
          )}
        </div>

        {stats && (
          <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-4">
            {stats.activeSubscriptions !== undefined && (
              <div>
                <p className="text-sm text-gray-500">Aktive Abos</p>
                <p className="font-semibold">{stats.activeSubscriptions}</p>
              </div>
            )}
            {stats.monthlyRevenue !== undefined && (
              <div>
                <p className="text-sm text-gray-500">Umsatz MTD</p>
                <p className="font-semibold">{stats.monthlyRevenue.toFixed(2)}</p>
              </div>
            )}
          </div>
        )}

        {(onEdit || onCreateOrder || onManageSubscriptions) && (
          <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap gap-2">
            {onEdit && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit();
                }}
              >
                <Edit2 className="w-4 h-4" />
                Details
              </button>
            )}
            {onCreateOrder && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onCreateOrder();
                }}
              >
                <ShoppingCart className="w-4 h-4" />
                Bestellung
              </button>
            )}
            {onManageSubscriptions && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onManageSubscriptions();
                }}
              >
                <RefreshCw className="w-4 h-4" />
                Abos
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Compact row version
interface CustomerRowProps {
  customer: Customer;
  onClick?: () => void;
}

export function CustomerRow({ customer, onClick }: CustomerRowProps) {
  return (
    <div
      className={`flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg ${
        onClick ? 'cursor-pointer hover:bg-gray-50' : ''
      }`}
      onClick={onClick}
    >
      <div>
        <p className="font-medium text-gray-900">{customer.name}</p>
        <p className="text-sm text-gray-500">
          {customer.email} {customer.telefon && `| ${customer.telefon}`}
        </p>
      </div>
      <div className="flex items-center gap-3">
        {customer.liefertage && customer.liefertage.length > 0 && (
          <span className="text-sm text-gray-500">
            {customer.liefertage.map((d) => WEEKDAYS[d]).join(', ')}
          </span>
        )}
        <CustomerTypeBadge type={customer.typ} />
      </div>
    </div>
  );
}
