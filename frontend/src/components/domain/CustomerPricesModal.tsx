import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../ui/Modal';
import { Button, Input, Combobox, useToast } from '../ui';
import { customerPricesApi, productsApi, CustomerPrice } from '../../services/api';
import { Trash, Plus, Tag } from 'lucide-react';

interface Props {
  open: boolean;
  onClose: () => void;
  customerId: string | null;
  customerName: string;
}

export function CustomerPricesModal({ open, onClose, customerId, customerName }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: prices = [] } = useQuery({
    queryKey: ['customer-prices', customerId],
    queryFn: () => customerPricesApi.list(customerId!),
    enabled: open && !!customerId,
  });

  const { data: productsData = [] } = useQuery({
    queryKey: ['products', 'active'],
    queryFn: () => productsApi.list({ is_active: true }),
    enabled: open,
  });

  const [draft, setDraft] = useState({
    product_id: '',
    unit_price: '',
    valid_from: '',
    valid_until: '',
    notes: '',
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['customer-prices', customerId] });

  const createMut = useMutation({
    mutationFn: () => customerPricesApi.create(customerId!, {
      product_id: draft.product_id,
      unit_price: Number(draft.unit_price),
      valid_from: draft.valid_from || undefined,
      valid_until: draft.valid_until || undefined,
      notes: draft.notes || undefined,
    }),
    onSuccess: () => {
      toast.success('Sonderpreis angelegt');
      setDraft({ product_id: '', unit_price: '', valid_from: '', valid_until: '', notes: '' });
      invalidate();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Anlegen fehlgeschlagen'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => customerPricesApi.delete(id),
    onSuccess: () => { toast.success('Sonderpreis entfernt'); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Löschen fehlgeschlagen'),
  });

  return (
    <Modal
      open={open && !!customerId}
      onClose={onClose}
      title={`Sonderpreise — ${customerName}`}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>Schließen</Button>}
    >
      <div className="space-y-5">
        {/* Anlegen */}
        <div className="border rounded p-3 dark:border-gray-700 bg-gray-50/40 dark:bg-gray-800/40 space-y-2">
          <h4 className="font-medium text-sm flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Neuen Sonderpreis hinterlegen
          </h4>
          <Combobox
            label="Produkt"
            placeholder="Produkt suchen…"
            value={draft.product_id}
            onChange={(v) => setDraft({ ...draft, product_id: v })}
            options={productsData.map((p) => ({
              value: p.id,
              label: `${(p.is_bundle || p.is_variable_bundle) ? '📦 ' : ''}${p.name}`,
              hint: p.base_price != null ? `Default: ${Number(p.base_price).toFixed(2)} €` : undefined,
            }))}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <Input
              label="Preis (€)"
              type="number"
              step="0.01"
              min={0}
              value={draft.unit_price}
              onChange={(e) => setDraft({ ...draft, unit_price: e.target.value })}
            />
            <Input
              label="Gültig ab"
              type="date"
              value={draft.valid_from}
              onChange={(e) => setDraft({ ...draft, valid_from: e.target.value })}
            />
            <Input
              label="Gültig bis"
              type="date"
              value={draft.valid_until}
              onChange={(e) => setDraft({ ...draft, valid_until: e.target.value })}
            />
          </div>
          <Input
            placeholder="Notiz (optional)"
            value={draft.notes}
            onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              icon={<Plus className="w-3 h-3" />}
              loading={createMut.isPending}
              disabled={!draft.product_id || !draft.unit_price}
              onClick={() => createMut.mutate()}
            >
              Hinzufügen
            </Button>
          </div>
        </div>

        {/* Liste */}
        <div>
          <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
            <Tag className="w-4 h-4" />
            Aktive Sonderpreise ({prices.length})
          </h4>
          {prices.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Noch keine Sonderpreise — alle Produkte werden mit Standard-Preis verrechnet.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {prices.map((p: CustomerPrice) => (
                <li key={p.id} className="flex items-center justify-between gap-2 border rounded p-2 text-sm dark:border-gray-700">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">
                      {p.product_name ?? p.product_id.slice(0, 8)}
                      <span className="ml-2 text-xs text-gray-500">{p.product_sku}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      <span className="font-semibold text-gray-700 dark:text-gray-200">
                        {Number(p.unit_price).toFixed(2)} {p.currency}
                      </span>
                      <span>ab {new Date(p.valid_from).toLocaleDateString('de-DE')}</span>
                      {p.valid_until && <span>bis {new Date(p.valid_until).toLocaleDateString('de-DE')}</span>}
                      {p.notes && <span className="italic">„{p.notes}"</span>}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="danger"
                    icon={<Trash className="w-3 h-3" />}
                    onClick={() => {
                      if (confirm(`Sonderpreis für ${p.product_name ?? 'Produkt'} entfernen?`)) {
                        deleteMut.mutate(p.id);
                      }
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  );
}
