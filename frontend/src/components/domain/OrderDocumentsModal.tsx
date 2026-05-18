import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Truck, Package, Send, Download, Plus, CheckCheck, Receipt } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button, Input, useToast } from '../ui';
import { documentsApi, invoicesApi, OrderConfirmation, DeliveryNote } from '../../services/api';
import { Order, Invoice } from '../../types';

interface Props {
  open: boolean;
  onClose: () => void;
  order: Order | null;
}

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    ENTWURF: 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
    VERSENDET: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
    AUSGESTELLT: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    GELIEFERT: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  };
  return map[status] || 'bg-gray-100 text-gray-700';
};

export function OrderDocumentsModal({ open, onClose, order }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const orderId = order?.id;

  const confirmationsQuery = useQuery({
    queryKey: ['confirmations', orderId],
    queryFn: () => documentsApi.listConfirmations(orderId!),
    enabled: open && !!orderId,
  });

  const deliveryNotesQuery = useQuery({
    queryKey: ['delivery-notes', orderId],
    queryFn: () => documentsApi.listDeliveryNotes(orderId!),
    enabled: open && !!orderId,
  });

  const invoicesQuery = useQuery({
    queryKey: ['order-invoices', orderId],
    queryFn: () => invoicesApi.list({}).then((rows) => rows.filter((i: Invoice) => i.order_id === orderId)),
    enabled: open && !!orderId,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['confirmations', orderId] });
    queryClient.invalidateQueries({ queryKey: ['delivery-notes', orderId] });
    queryClient.invalidateQueries({ queryKey: ['order-invoices', orderId] });
    queryClient.invalidateQueries({ queryKey: ['invoices'] });
    queryClient.invalidateQueries({ queryKey: ['orders'] });
  };

  const createInvoice = useMutation({
    mutationFn: () => invoicesApi.createFromOrder(orderId!),
    onSuccess: (inv: Invoice) => { toast.success(`Rechnung ${inv.invoice_number} angelegt`); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Erstellen der Rechnung'),
  });

  const finalizeInvoice = useMutation({
    mutationFn: (inv: Invoice) => invoicesApi.finalize(inv.id),
    onSuccess: () => { toast.success('Rechnung finalisiert'); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Finalisieren'),
  });

  const downloadInvoicePdf = async (inv: Invoice) => {
    try {
      const res = await invoicesApi.downloadPdf(inv.id);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.download = `${inv.invoice_number}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'PDF-Download fehlgeschlagen');
    }
  };

  const createConfirmation = useMutation({
    mutationFn: () => documentsApi.createConfirmation(orderId!, {}),
    onSuccess: (c) => { toast.success(`AB ${c.confirmation_number} erstellt`); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Erstellen der AB'),
  });

  const sendConfirmation = useMutation({
    mutationFn: (conf: OrderConfirmation) => documentsApi.sendConfirmation(conf.id, {}),
    onSuccess: () => { toast.success('AB als versendet markiert'); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Versenden'),
  });

  const createDeliveryNote = useMutation({
    mutationFn: () => documentsApi.createDeliveryNote(orderId!, {}),
    onSuccess: (n) => { toast.success(`Lieferschein ${n.delivery_note_number} erstellt`); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Erstellen des Lieferscheins'),
  });

  const markDeliveredMutation = useMutation({
    mutationFn: ({ noteId, signed_by }: { noteId: string; signed_by: string }) =>
      documentsApi.markDelivered(noteId, { signed_by }),
    onSuccess: () => { toast.success('Lieferschein quittiert'); invalidate(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Quittieren'),
  });

  const [signedByInput, setSignedByInput] = useState<Record<string, string>>({});

  if (!order) return null;

  const confirmations = confirmationsQuery.data || [];
  const deliveryNotes = deliveryNotesQuery.data || [];
  const invoices = invoicesQuery.data || [];

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Belege zu Bestellung ${(order as any).order_number || order.id.slice(0, 8)}`}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>Schließen</Button>}
    >
      <div className="space-y-6">
        {/* AUFTRAGSBESTÄTIGUNG */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200">
              <FileText className="w-4 h-4" />
              Auftragsbestätigungen
            </h3>
            <Button
              size="sm"
              icon={<Plus className="w-3 h-3" />}
              loading={createConfirmation.isPending}
              onClick={() => createConfirmation.mutate()}
            >
              Neue AB
            </Button>
          </div>
          {confirmations.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">Noch keine AB angelegt.</p>
          ) : (
            <ul className="space-y-2">
              {confirmations.map((c) => (
                <li key={c.id} className="flex items-center justify-between border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">{c.confirmation_number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(c.status)}`}>{c.status}</span>
                    {c.sent_to_email && <span className="text-xs text-gray-500">→ {c.sent_to_email}</span>}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Download className="w-3 h-3" />}
                      onClick={() => documentsApi.downloadConfirmationPdf(c)}
                    >
                      PDF
                    </Button>
                    {c.status === 'ENTWURF' && (
                      <Button
                        size="sm"
                        icon={<Send className="w-3 h-3" />}
                        loading={sendConfirmation.isPending}
                        onClick={() => sendConfirmation.mutate(c)}
                      >
                        Versenden
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* LIEFERSCHEINE */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200">
              <Truck className="w-4 h-4" />
              Lieferscheine
            </h3>
            <Button
              size="sm"
              icon={<Plus className="w-3 h-3" />}
              loading={createDeliveryNote.isPending}
              onClick={() => createDeliveryNote.mutate()}
            >
              Neuer LS
            </Button>
          </div>
          {deliveryNotes.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">Noch kein Lieferschein angelegt.</p>
          ) : (
            <ul className="space-y-2">
              {deliveryNotes.map((n: DeliveryNote) => (
                <li key={n.id} className="border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm">{n.delivery_note_number}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(n.status)}`}>{n.status}</span>
                      {n.signed_by && <span className="text-xs text-gray-500">✓ {n.signed_by}</span>}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Download className="w-3 h-3" />}
                        onClick={() => documentsApi.downloadDeliveryNotePdf(n)}
                      >
                        LS-PDF
                      </Button>
                      {n.packing_list && (
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<Package className="w-3 h-3" />}
                          onClick={() => documentsApi.downloadPackingListPdf(n)}
                        >
                          Packliste
                        </Button>
                      )}
                    </div>
                  </div>
                  {n.status !== 'GELIEFERT' && (
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        placeholder="Unterzeichnet von..."
                        value={signedByInput[n.id] || ''}
                        onChange={(e) => setSignedByInput((p) => ({ ...p, [n.id]: e.target.value }))}
                      />
                      <Button
                        size="sm"
                        icon={<CheckCheck className="w-3 h-3" />}
                        loading={markDeliveredMutation.isPending}
                        onClick={() =>
                          markDeliveredMutation.mutate({
                            noteId: n.id,
                            signed_by: signedByInput[n.id] || '',
                          })
                        }
                      >
                        Quittieren
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* RECHNUNGEN */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200">
              <Receipt className="w-4 h-4" />
              Rechnungen
            </h3>
            <Button
              size="sm"
              icon={<Plus className="w-3 h-3" />}
              loading={createInvoice.isPending}
              onClick={() => createInvoice.mutate()}
            >
              Rechnung aus Bestellung
            </Button>
          </div>
          {invoices.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">Noch keine Rechnung zu dieser Bestellung.</p>
          ) : (
            <ul className="space-y-2">
              {invoices.map((inv: Invoice) => (
                <li key={inv.id} className="flex items-center justify-between border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">{inv.invoice_number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(inv.status)}`}>{inv.status}</span>
                    <span className="text-xs text-gray-500">€ {Number(inv.total || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Download className="w-3 h-3" />}
                      onClick={() => downloadInvoicePdf(inv)}
                    >
                      PDF
                    </Button>
                    {inv.status === 'ENTWURF' && (
                      <Button
                        size="sm"
                        icon={<Send className="w-3 h-3" />}
                        loading={finalizeInvoice.isPending}
                        onClick={() => finalizeInvoice.mutate(inv)}
                      >
                        Finalisieren
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Modal>
  );
}
