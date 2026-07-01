import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash, PackageCheck, Ban, Eye } from 'lucide-react';
import { purchasingApi, suppliersApi, productsApi, PurchaseOrderCreatePayload } from '../services/api';
import { PurchaseOrder, PurchaseOrderStatus } from '../types';
import { PageHeader } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  SelectOption,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  Badge,
  useToast,
} from '../components/ui';

const STATUS_VARIANT: Record<PurchaseOrderStatus, 'gray' | 'info' | 'warning' | 'success' | 'danger'> = {
  ENTWURF: 'gray',
  BESTELLT: 'info',
  TEILWEISE_ERHALTEN: 'warning',
  ERHALTEN: 'success',
  STORNIERT: 'danger',
};
const STATUS_LABEL: Record<PurchaseOrderStatus, string> = {
  ENTWURF: 'Entwurf',
  BESTELLT: 'Bestellt',
  TEILWEISE_ERHALTEN: 'Teilw. erhalten',
  ERHALTEN: 'Erhalten',
  STORNIERT: 'Storniert',
};

const num = (v: number | string | null | undefined): number => (v == null ? 0 : typeof v === 'string' ? parseFloat(v) : v);
const eur = (v: number | string | null | undefined): string => `${num(v).toFixed(2)} €`;

export default function Purchasing() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<PurchaseOrder | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const { data, isLoading } = useQuery({
    queryKey: ['purchase-orders', statusFilter],
    queryFn: () => purchasingApi.list(statusFilter === 'all' ? {} : { status_filter: statusFilter as PurchaseOrderStatus }),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => purchasingApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      toast.success('Bestellung storniert');
      setCancelling(null);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Stornieren fehlgeschlagen'),
  });

  const statusOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Status' },
    ...(Object.keys(STATUS_LABEL) as PurchaseOrderStatus[]).map((s) => ({ value: s, label: STATUS_LABEL[s] })),
  ];

  if (isLoading) return <PageLoader />;

  const orders = data?.items || [];

  return (
    <div>
      <PageHeader
        title="Einkauf"
        subtitle={`${orders.length} Bestellungen`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
            Neue Bestellung
          </Button>
        }
      />

      <div className="mb-4 max-w-xs">
        <Select options={statusOptions} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
      </div>

      {orders.length === 0 ? (
        <EmptyState
          title="Keine Bestellungen"
          description="Lege deine erste Einkaufsbestellung beim Lieferanten an. Nach dem Wareneingang wird der Bestand fortgeschrieben."
          action={
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
              Bestellung anlegen
            </Button>
          }
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Nummer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Lieferant</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Datum</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Brutto</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {orders.map((po) => (
                <tr key={po.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{po.po_number}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{po.supplier_name || '–'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    {new Date(po.order_date).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={STATUS_VARIANT[po.status]}>{STATUS_LABEL[po.status]}</Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-right text-gray-900 dark:text-white">{eur(po.total_gross)}</td>
                  <td className="px-6 py-4 text-right whitespace-nowrap">
                    <Button variant="ghost" size="sm" icon={<Eye className="w-4 h-4" />} onClick={() => setDetailId(po.id)} title="Details / Wareneingang" />
                    {po.status !== 'ERHALTEN' && po.status !== 'STORNIERT' && (
                      <Button variant="ghost" size="sm" icon={<Ban className="w-4 h-4" />} onClick={() => setCancelling(po as any)} title="Stornieren" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={creating} onClose={() => setCreating(false)} title="Neue Bestellung" size="lg">
        <CreatePurchaseOrderForm
          onDone={() => {
            queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
            setCreating(false);
            toast.success('Bestellung angelegt');
          }}
          onCancel={() => setCreating(false)}
        />
      </Modal>

      <Modal open={!!detailId} onClose={() => setDetailId(null)} title="Bestelldetails" size="lg">
        {detailId && (
          <PurchaseOrderDetail
            poId={detailId}
            onReceived={() => queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={!!cancelling}
        onClose={() => setCancelling(null)}
        onConfirm={() => cancelling && cancelMutation.mutate(cancelling.id)}
        title="Bestellung stornieren?"
        message={`"${cancelling?.po_number}" wird auf Storniert gesetzt.`}
        confirmLabel="Stornieren"
        variant="danger"
        loading={cancelMutation.isPending}
      />
    </div>
  );
}

interface LineDraft {
  product_id: string;
  beschreibung: string;
  quantity: string;
  unit: string;
  unit_price: string;
  tax_rate: string;
}

const emptyLine = (): LineDraft => ({ product_id: '', beschreibung: '', quantity: '1', unit: 'STK', unit_price: '0', tax_rate: 'STANDARD' });

function CreatePurchaseOrderForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [supplierId, setSupplierId] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState<LineDraft[]>([emptyLine()]);

  const { data: suppliersData } = useQuery({ queryKey: ['suppliers', 'active'], queryFn: () => suppliersApi.list({ is_active: true }) });
  const { data: products } = useQuery({ queryKey: ['products', 'active'], queryFn: () => productsApi.list({ is_active: true }) });

  const supplierOptions: SelectOption[] = [
    { value: '', label: '— Lieferant wählen —' },
    ...(suppliersData?.items || []).map((s) => ({ value: s.id, label: s.name })),
  ];
  const productOptions: SelectOption[] = [
    { value: '', label: '— frei / kein Produkt —' },
    ...(products || []).map((p) => ({ value: p.id, label: `${p.name} (${p.sku})` })),
  ];
  const taxOptions: SelectOption[] = [
    { value: 'STANDARD', label: '19 %' },
    { value: 'REDUZIERT', label: '7 %' },
    { value: 'STEUERFREI', label: '0 %' },
  ];

  const total = useMemo(
    () => lines.reduce((sum, l) => sum + num(l.quantity) * num(l.unit_price), 0),
    [lines],
  );

  const updateLine = (i: number, patch: Partial<LineDraft>) => {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  };
  const onPickProduct = (i: number, productId: string) => {
    const p = (products || []).find((x) => x.id === productId);
    updateLine(i, { product_id: productId, beschreibung: p ? p.name : lines[i].beschreibung });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supplierId) {
      toast.error('Bitte einen Lieferanten wählen');
      return;
    }
    const validLines = lines.filter((l) => num(l.quantity) > 0 && (l.beschreibung.trim() || l.product_id));
    if (validLines.length === 0) {
      toast.error('Mindestens eine Position mit Menge und Bezeichnung');
      return;
    }
    setLoading(true);
    try {
      const payload: PurchaseOrderCreatePayload = {
        supplier_id: supplierId,
        requested_delivery_date: deliveryDate || null,
        notes: notes || null,
        lines: validLines.map((l) => ({
          product_id: l.product_id || null,
          beschreibung: l.beschreibung || null,
          quantity: num(l.quantity),
          unit: l.unit || 'STK',
          unit_price: num(l.unit_price),
          tax_rate: l.tax_rate,
        })),
      };
      await purchasingApi.create(payload);
      onDone();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Fehler beim Anlegen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select label="Lieferant" required options={supplierOptions} value={supplierId} onChange={(e) => setSupplierId(e.target.value)} />
        <Input label="Wunsch-Lieferdatum" type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Positionen</span>
          <Button type="button" variant="secondary" size="sm" icon={<Plus className="w-4 h-4" />} onClick={() => setLines((p) => [...p, emptyLine()])}>
            Position
          </Button>
        </div>
        {lines.map((l, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end border border-gray-100 dark:border-gray-700 rounded-lg p-2">
            <div className="col-span-12 md:col-span-3">
              <Select label={i === 0 ? 'Produkt' : undefined} options={productOptions} value={l.product_id} onChange={(e) => onPickProduct(i, e.target.value)} />
            </div>
            <div className="col-span-12 md:col-span-3">
              <Input label={i === 0 ? 'Bezeichnung' : undefined} value={l.beschreibung} onChange={(e) => updateLine(i, { beschreibung: e.target.value })} placeholder="Artikel" />
            </div>
            <div className="col-span-4 md:col-span-1">
              <Input label={i === 0 ? 'Menge' : undefined} type="number" value={l.quantity} onChange={(e) => updateLine(i, { quantity: e.target.value })} />
            </div>
            <div className="col-span-4 md:col-span-1">
              <Input label={i === 0 ? 'Einheit' : undefined} value={l.unit} onChange={(e) => updateLine(i, { unit: e.target.value })} />
            </div>
            <div className="col-span-4 md:col-span-2">
              <Input label={i === 0 ? 'EK-Preis' : undefined} type="number" value={l.unit_price} onChange={(e) => updateLine(i, { unit_price: e.target.value })} />
            </div>
            <div className="col-span-8 md:col-span-1">
              <Select label={i === 0 ? 'MwSt' : undefined} options={taxOptions} value={l.tax_rate} onChange={(e) => updateLine(i, { tax_rate: e.target.value })} />
            </div>
            <div className="col-span-4 md:col-span-1 flex justify-end">
              <Button type="button" variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => setLines((p) => p.filter((_, idx) => idx !== i))} disabled={lines.length === 1} />
            </div>
          </div>
        ))}
      </div>

      <Input label="Notizen" value={notes} onChange={(e) => setNotes(e.target.value)} />

      <div className="flex items-center justify-between pt-4 border-t">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          Netto-Summe (ohne Rabatt/MwSt): <b className="text-gray-900 dark:text-white">{eur(total)}</b>
        </span>
        <div className="flex gap-3">
          <Button type="button" variant="secondary" onClick={onCancel}>Abbrechen</Button>
          <Button type="submit" loading={loading}>Bestellung anlegen</Button>
        </div>
      </div>
    </form>
  );
}

function PurchaseOrderDetail({ poId, onReceived }: { poId: string; onReceived: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [receiptQty, setReceiptQty] = useState<Record<string, string>>({});

  const { data: po, isLoading } = useQuery({ queryKey: ['purchase-order', poId], queryFn: () => purchasingApi.get(poId) });

  const receiveMutation = useMutation({
    mutationFn: (receipts: { line_id: string; quantity: number }[]) => purchasingApi.receive(poId, receipts),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-order', poId] });
      onReceived();
      setReceiptQty({});
      toast.success('Wareneingang verbucht');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Wareneingang fehlgeschlagen'),
  });

  if (isLoading || !po) return <PageLoader />;

  const submitReceipt = () => {
    const receipts = Object.entries(receiptQty)
      .map(([line_id, q]) => ({ line_id, quantity: num(q) }))
      .filter((r) => r.quantity > 0);
    if (receipts.length === 0) {
      toast.error('Keine Eingangsmenge erfasst');
      return;
    }
    receiveMutation.mutate(receipts);
  };

  const open = po.status !== 'ERHALTEN' && po.status !== 'STORNIERT';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">{po.po_number}</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">{po.supplier_name}</div>
        </div>
        <Badge variant={STATUS_VARIANT[po.status]}>{STATUS_LABEL[po.status]}</Badge>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-xs text-gray-500 dark:text-gray-400 uppercase border-b dark:border-gray-700">
            <tr>
              <th className="px-2 py-2 text-left">Position</th>
              <th className="px-2 py-2 text-right">Menge</th>
              <th className="px-2 py-2 text-right">Erhalten</th>
              <th className="px-2 py-2 text-right">Offen</th>
              <th className="px-2 py-2 text-right">EK</th>
              <th className="px-2 py-2 text-right">Marge</th>
              {open && <th className="px-2 py-2 text-right">Eingang</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {po.lines.map((l) => (
              <tr key={l.id}>
                <td className="px-2 py-2 text-gray-900 dark:text-white">{l.beschreibung || l.product_sku || '–'}</td>
                <td className="px-2 py-2 text-right">{num(l.quantity)} {l.unit}</td>
                <td className="px-2 py-2 text-right">{num(l.quantity_received)}</td>
                <td className="px-2 py-2 text-right">{num(l.quantity_open)}</td>
                <td className="px-2 py-2 text-right">{eur(l.unit_price)}</td>
                <td className="px-2 py-2 text-right">
                  {l.margin_percent != null ? (
                    <span className={num(l.margin_percent) >= 0 ? 'text-green-600' : 'text-red-600'}>
                      {num(l.margin_percent).toFixed(1)} %
                    </span>
                  ) : '–'}
                </td>
                {open && (
                  <td className="px-2 py-2 text-right">
                    {l.is_fully_received ? (
                      <span className="text-green-600 text-xs">vollständig</span>
                    ) : (
                      <input
                        type="number"
                        className="w-20 px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600 text-right"
                        placeholder={String(num(l.quantity_open))}
                        value={receiptQty[l.id] ?? ''}
                        onChange={(e) => setReceiptQty((prev) => ({ ...prev, [l.id]: e.target.value }))}
                      />
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between pt-3 border-t dark:border-gray-700">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          Gesamt: <b className="text-gray-900 dark:text-white">{eur(po.total_gross)}</b> (Netto {eur(po.total_net)})
        </span>
        {open && (
          <Button icon={<PackageCheck className="w-4 h-4" />} onClick={submitReceipt} loading={receiveMutation.isPending}>
            Wareneingang verbuchen
          </Button>
        )}
      </div>
    </div>
  );
}
