import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Truck, Package, Send, Download, Plus, CheckCheck, Receipt, Mail, Pencil } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { useAuth } from '../../context/AuthContext';
import { Button, Input, useToast } from '../ui';
import { documentsApi, invoicesApi, salesApi, OrderConfirmation, DeliveryNote, BelegVersandAuftrag } from '../../services/api';
import { VersandFormular, VersandProtokoll, versandMeldung } from './BelegVersand';
import { Order, Invoice } from '../../types';
import { belegHerunterladen, type BelegAngaben, type Geladen } from '../../services/belegordner';
import { belegartDerRechnung } from '../../services/belegpfad';
import { getErrorMessage } from '../../services/errors';
import { rechnungsnummerAnzeige, FINALISIEREN_RUECKFRAGE } from '../../services/rechnungsnummer';
import { belegStatusLabel } from '../ui/statusLabels';
import { invalidateOrderViews } from '../../services/orderQueries';
import { InvoiceDetail } from '../../pages/Invoices';

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
  // Rechnungen nur mit Rechnungsrecht (main.py: _deps_geld = admin, sales,
  // accounting). Planung und Halle öffnen den Dialog wegen AB und Lieferschein;
  // für sie entfallen Rechnungsteil und Abfrage. Der Server sperrt /invoices
  // für sie trotzdem (403). Rollen aus dem Token wie in App.tsx (Startseite).
  const { user } = useAuth();
  const darfRechnungen = ['admin', 'sales', 'accounting'].some((rolle) => user?.roles?.includes(rolle));

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

  // Serverseitig gefiltert: Rechnung aus Bestellung (order_id) und
  // Sammelrechnung (über den Lieferschein). Früher wurden die 20 neuesten
  // Rechnungen clientseitig gefiltert — ab Rechnung 21 stand hier "keine
  // Rechnung", und der Knopf erzeugte eine Doppelrechnung.
  // page_size 100: ohne Angabe kürzt das Backend still auf 20.
  // Schlüssel unter 'invoices', damit Änderungen im Entwurf (InvoiceDetail
  // invalidiert ['invoices']) auch diese Liste neu laden.
  const invoicesQuery = useQuery({
    queryKey: ['invoices', 'order', orderId],
    queryFn: () => invoicesApi.list({ order_id: orderId!, page_size: 100 }),
    enabled: open && !!orderId && darfRechnungen,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['confirmations', orderId] });
    queryClient.invalidateQueries({ queryKey: ['delivery-notes', orderId] });
    queryClient.invalidateQueries({ queryKey: ['invoices'] });
    // Quittieren setzt die Bestellung auf Geliefert — Tagesplan mit neu laden
    void invalidateOrderViews(queryClient);
  };

  const createInvoice = useMutation({
    mutationFn: () => invoicesApi.createFromOrder(orderId!),
    onSuccess: () => { toast.success('Rechnungsentwurf angelegt — die Nummer vergibt das Finalisieren'); invalidate(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Erstellen der Rechnung')),
  });

  const finalizeInvoice = useMutation({
    mutationFn: (inv: Invoice) => invoicesApi.finalize(inv.id),
    onSuccess: (inv: Invoice) => { toast.success(`Rechnung ${inv.invoice_number} finalisiert`); invalidate(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Finalisieren')),
  });

  // Abschnitt O: alle PDFs dieses Dialogs über die eine Download-Funktion
  // (Belegordner, sonst Download-Ordner; Name vom Server, B7)
  const belegPdf = (angaben: BelegAngaben, laden: () => Promise<Geladen | null>) =>
    belegHerunterladen(angaben, laden, toast).catch((e) => {
      toast.error(getErrorMessage(e, 'PDF-Download fehlgeschlagen'));
      return null;
    });

  const downloadInvoicePdf = (inv: Invoice) =>
    belegPdf(
      { art: belegartDerRechnung(inv), datum: inv.invoice_date, ersatzname: `${inv.invoice_number}.pdf` },
      () => invoicesApi.downloadPdf(inv.id),
    );

  // Belegversand (Paket 3, Q2): offenes Versandformular 'AB:<id>', 'LS:<id>' oder 'RE:<id>'
  const [versandOffen, setVersandOffen] = useState<string | null>(null);
  const versandUmschalten = (schluessel: string) =>
    setVersandOffen((offen) => (offen === schluessel ? null : schluessel));
  // Kundenstamm für „Neue AB“/„Neuer LS“: Sind für die Belegart Empfänger
  // hinterlegt, öffnet sich das Versandformular gleich (T5 3.3).
  const kundeQuery = useQuery({
    queryKey: ['customer', order?.customer_id],
    queryFn: () => salesApi.getCustomer(order!.customer_id!),
    enabled: open && !!order?.customer_id,
  });

  const createConfirmation = useMutation({
    mutationFn: () => documentsApi.createConfirmation(orderId!, {}),
    onSuccess: (c) => {
      toast.success(`AB ${c.confirmation_number} erstellt`);
      invalidate();
      if (kundeQuery.data?.confirmation_emails?.length) setVersandOffen(`AB:${c.id}`);
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Erstellen der AB')),
  });

  const sendConfirmation = useMutation({
    mutationFn: ({ conf, auftrag }: { conf: OrderConfirmation; auftrag: BelegVersandAuftrag }) =>
      documentsApi.sendConfirmation(conf.id, auftrag),
    onSuccess: (c) => {
      versandMeldung(toast, `AB ${c.confirmation_number}`, c.dispatches);
      setVersandOffen(null);
      invalidate();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Versenden')),
  });

  const sendDeliveryNote = useMutation({
    mutationFn: ({ note, auftrag }: { note: DeliveryNote; auftrag: BelegVersandAuftrag }) =>
      documentsApi.sendDeliveryNote(note.id, auftrag),
    onSuccess: (n) => {
      versandMeldung(toast, `Lieferschein ${n.delivery_note_number}`, n.dispatches);
      setVersandOffen(null);
      invalidate();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Versenden')),
  });

  const sendInvoiceMail = useMutation({
    mutationFn: ({ inv, auftrag }: { inv: Invoice; auftrag: BelegVersandAuftrag }) =>
      invoicesApi.sendInvoice(inv.id, auftrag),
    onSuccess: (zeile) => {
      // Nummer aus der Protokollzeile: ein Entwurf bekommt sie erst mit dem Versand (Q1)
      versandMeldung(toast, `Rechnung ${zeile.document_number}`, [zeile]);
      setVersandOffen(null);
      invalidate();
    },
    // Ein Entwurf ist vor dem Versand finalisiert worden — auch wenn die Mail scheitert (Q1)
    onError: (e: any) => { toast.error(getErrorMessage(e, 'Fehler beim Versand')); invalidate(); },
  });

  const createDeliveryNote = useMutation({
    mutationFn: (zusaetzlich: boolean) => documentsApi.createDeliveryNote(orderId!, {}, { zusaetzlich }),
    onSuccess: (n) => {
      toast.success(`Lieferschein ${n.delivery_note_number} erstellt`);
      invalidate();
      if (kundeQuery.data?.delivery_note_emails?.length) setVersandOffen(`LS:${n.id}`);
    },
    onError: (e: any) => {
      // 409 = es gibt schon einen Lieferschein; das fragt neuerLieferschein() nach.
      if (e?.response?.status === 409) return;
      toast.error(getErrorMessage(e, 'Fehler beim Erstellen des Lieferscheins'));
    },
  });

  const neuerLieferschein = async () => {
    try {
      await createDeliveryNote.mutateAsync(false);
    } catch (e: any) {
      if (e?.response?.status !== 409) return; // Fehlermeldung kam schon aus onError
      if (!window.confirm(`${getErrorMessage(e)}\n\nTrotzdem einen weiteren Lieferschein anlegen?`)) return;
      await createDeliveryNote.mutateAsync(true).catch(() => undefined);
    }
  };

  const markDeliveredMutation = useMutation({
    mutationFn: ({ noteId, signed_by, actual_delivery_date }: { noteId: string; signed_by: string; actual_delivery_date: string }) =>
      documentsApi.markDelivered(noteId, { signed_by, actual_delivery_date }),
    onSuccess: () => { toast.success('Lieferschein quittiert'); invalidate(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Quittieren')),
  });

  const [signedByInput, setSignedByInput] = useState<Record<string, string>>({});
  // Aufgeklappte Rechnung: Positionen prüfen und im Entwurf bearbeiten
  const [offeneRechnung, setOffeneRechnung] = useState<string | null>(null);

  // Tatsächlicher Liefertag je Lieferschein (Eingabe des Anwenders).
  const [lieferdatumInput, setLieferdatumInput] = useState<Record<string, string>>({});

  if (!order) return null;

  const heute = new Date().toLocaleDateString('sv-SE');
  // Vorschlag: Ist die Bestellung schon geliefert, ihr Lieferdatum — der Server
  // überschreibt es nie, Lieferschein und Bestellung sollen gleich lauten.
  // Sonst der geplante Liefertag, höchstens heute (Nachtragen, LÜCKEN 4).
  const vorschlagLieferdatum =
    order.actual_delivery_date
    ?? (order.liefer_datum && order.liefer_datum < heute ? order.liefer_datum : heute);
  // Quittieren setzt die Bestellung auf Geliefert; aus Entwurf und Storniert
  // lehnt der Server das ab (order_status_service.setze_status).
  const quittierbar = order.status !== 'ENTWURF' && order.status !== 'STORNIERT';

  const confirmations = confirmationsQuery.data || [];
  const deliveryNotes = deliveryNotesQuery.data || [];
  const invoices = invoicesQuery.data || [];
  // Rechnungen gehören zur Geldseite (main.py: _deps_geld = sales, accounting,
  // admin). Planung und Halle öffnen den Dialog wegen der Lieferscheine auch,
  // GET /invoices antwortet ihnen mit 403 — das ist kein Ladefehler.
  const ohneRechnungsrecht = (invoicesQuery.error as any)?.response?.status === 403;
  // Gleiche Regel wie das Backend (InvoiceService.aktive_rechnung_zur_bestellung):
  // eine nicht stornierte Rechnung vom Typ RECHNUNG sperrt die nächste.
  const aktiveRechnung = invoices.find((i: Invoice) => i.invoice_type === 'RECHNUNG' && i.status !== 'STORNIERT');
  // Fakturiert = außerhalb von NovaERP abgerechnet (z. B. über DATEV); der
  // Server lehnt jede Rechnung dazu mit 409 ab (Paket 4, B; G66).
  const fakturiert = order.status === 'FAKTURIERT';
  // Ohne frisch geladene Liste kein Knopf: lieber einmal zu wenig anbieten als doppelt berechnen.
  const rechnungMoeglich = order.status !== 'STORNIERT' && !fakturiert && invoicesQuery.isSuccess && !invoicesQuery.isFetching && !aktiveRechnung;

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
                <li key={c.id} className="border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">{c.confirmation_number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(c.status)}`}>{belegStatusLabel(c.status)}</span>
                    {/* Vor Q2 versendet: kein Protokoll, nur die Kurzanzeige */}
                    {c.sent_to_email && !c.dispatches?.length && (
                      <span className="text-xs text-gray-500">→ {c.sent_to_email}</span>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Download className="w-3 h-3" />}
                      onClick={() => belegPdf(
                        { art: 'Auftragsbestätigungen', datum: c.issued_at, ersatzname: `${c.confirmation_number}.pdf` },
                        () => documentsApi.confirmationPdf(c),
                      )}
                    >
                      PDF
                    </Button>
                    <Button
                      size="sm"
                      icon={<Send className="w-3 h-3" />}
                      onClick={() => versandUmschalten(`AB:${c.id}`)}
                    >
                      {c.status === 'ENTWURF' ? 'Versenden' : 'Erneut senden'}
                    </Button>
                  </div>
                  </div>
                  <VersandProtokoll eintraege={c.dispatches} />
                  {versandOffen === `AB:${c.id}` && (
                    <div className="mt-2">
                      <VersandFormular
                        belegart="AB"
                        belegNummer={c.confirmation_number}
                        customerId={order.customer_id}
                        nurMarkierenMoeglich={c.status === 'ENTWURF'}
                        pending={sendConfirmation.isPending}
                        onSenden={(auftrag) => sendConfirmation.mutate({ conf: c, auftrag })}
                        onAbbrechen={() => setVersandOffen(null)}
                      />
                    </div>
                  )}
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
              onClick={neuerLieferschein}
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
                      <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(n.status)}`}>{belegStatusLabel(n.status)}</span>
                      {n.signed_by && <span className="text-xs text-gray-500">✓ {n.signed_by}</span>}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Download className="w-3 h-3" />}
                        onClick={() => belegPdf(
                          { art: 'Lieferscheine', datum: n.issued_at, ersatzname: `${n.delivery_note_number}.pdf` },
                          () => documentsApi.deliveryNotePdf(n),
                        )}
                      >
                        LS-PDF
                      </Button>
                      {n.packing_list && (
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<Package className="w-3 h-3" />}
                          onClick={() => belegPdf(
                            {
                              art: 'Packlisten',
                              datum: n.packing_list?.created_at ?? n.issued_at,
                              ersatzname: `${n.packing_list?.packing_list_number || n.delivery_note_number}.pdf`,
                            },
                            () => documentsApi.packingListPdf(n),
                          )}
                        >
                          Packliste
                        </Button>
                      )}
                      <Button
                        size="sm"
                        icon={<Send className="w-3 h-3" />}
                        onClick={() => versandUmschalten(`LS:${n.id}`)}
                      >
                        {n.dispatches && n.dispatches.length > 0 ? 'Erneut senden' : 'Versenden'}
                      </Button>
                    </div>
                  </div>
                  <VersandProtokoll eintraege={n.dispatches} />
                  {versandOffen === `LS:${n.id}` && (
                    <div className="mt-2">
                      <VersandFormular
                        belegart="LS"
                        belegNummer={n.delivery_note_number}
                        customerId={order.customer_id}
                        nurMarkierenMoeglich={n.status === 'ENTWURF'}
                        pending={sendDeliveryNote.isPending}
                        onSenden={(auftrag) => sendDeliveryNote.mutate({ note: n, auftrag })}
                        onAbbrechen={() => setVersandOffen(null)}
                      />
                    </div>
                  )}
                  {n.status !== 'GELIEFERT' && !quittierbar && (
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      {order.status === 'STORNIERT'
                        ? 'Bestellung ist storniert, der Lieferschein kann nicht quittiert werden.'
                        : 'Erst die Bestellung bestätigen, dann den Lieferschein quittieren.'}
                    </p>
                  )}
                  {n.status !== 'GELIEFERT' && quittierbar && (
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        placeholder="Unterzeichnet von..."
                        value={signedByInput[n.id] || ''}
                        onChange={(e) => setSignedByInput((p) => ({ ...p, [n.id]: e.target.value }))}
                      />
                      <Input
                        type="date"
                        aria-label="Liefertag"
                        title="Tatsächlicher Liefertag"
                        max={heute}
                        value={lieferdatumInput[n.id] ?? vorschlagLieferdatum}
                        onChange={(e) => setLieferdatumInput((p) => ({ ...p, [n.id]: e.target.value }))}
                      />
                      <Button
                        size="sm"
                        icon={<CheckCheck className="w-3 h-3" />}
                        loading={markDeliveredMutation.isPending}
                        onClick={() =>
                          markDeliveredMutation.mutate({
                            noteId: n.id,
                            signed_by: signedByInput[n.id] || '',
                            actual_delivery_date: lieferdatumInput[n.id] || vorschlagLieferdatum,
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

        {/* RECHNUNGEN — nur mit Rechnungsrecht (darfRechnungen) */}
        {darfRechnungen && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200">
              <Receipt className="w-4 h-4" />
              Rechnungen
            </h3>
            {rechnungMoeglich && (
              <Button
                size="sm"
                icon={<Plus className="w-3 h-3" />}
                loading={createInvoice.isPending}
                onClick={() => createInvoice.mutate()}
              >
                Rechnung aus Bestellung
              </Button>
            )}
          </div>
          {ohneRechnungsrecht ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Rechnungen sehen nur Vertrieb und Buchhaltung.
            </p>
          ) : invoicesQuery.isError ? (
            <p className="text-sm text-red-700 dark:text-red-300">
              Rechnungen zu dieser Bestellung konnten nicht geladen werden. Bitte den Dialog neu öffnen.
            </p>
          ) : invoices.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              {fakturiert
                ? 'Als „Fakturiert“ gekennzeichnet: außerhalb von NovaERP abgerechnet (z. B. über DATEV). Eine Rechnung ist hier nicht möglich.'
                : 'Noch keine Rechnung zu dieser Bestellung.'}
            </p>
          ) : (
            <ul className="space-y-2">
              {invoices.map((inv: Invoice) => (
                <li key={inv.id} className="border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">{rechnungsnummerAnzeige(inv.invoice_number)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${statusBadge(inv.status)}`}>{belegStatusLabel(inv.status)}</span>
                    <span className="text-xs text-gray-500">€ {Number(inv.total || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Pencil className="w-3 h-3" />}
                      onClick={() => setOffeneRechnung(offeneRechnung === inv.id ? null : inv.id)}
                    >
                      {inv.status === 'ENTWURF' ? 'Bearbeiten' : 'Positionen'}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Download className="w-3 h-3" />}
                      onClick={() => downloadInvoicePdf(inv)}
                    >
                      PDF
                    </Button>
                    {inv.status !== 'STORNIERT' && (
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Mail className="w-3 h-3" />}
                        onClick={() => versandUmschalten(`RE:${inv.id}`)}
                      >
                        {inv.dispatches && inv.dispatches.length > 0 ? 'Erneut senden' : 'Versenden'}
                      </Button>
                    )}
                    {inv.status === 'ENTWURF' && (
                      <Button
                        size="sm"
                        icon={<Send className="w-3 h-3" />}
                        loading={finalizeInvoice.isPending}
                        onClick={() => { if (window.confirm(FINALISIEREN_RUECKFRAGE)) finalizeInvoice.mutate(inv); }}
                      >
                        Finalisieren
                      </Button>
                    )}
                  </div>
                  </div>
                  <VersandProtokoll eintraege={inv.dispatches} />
                  {versandOffen === `RE:${inv.id}` && (
                    <div className="mt-2">
                      {inv.status === 'ENTWURF' && (
                        <p className="mb-1 text-xs text-gray-600 dark:text-gray-300">
                          Der Entwurf wird beim Mailen finalisiert: Er erhält die nächste freie Rechnungsnummer und lässt sich danach nur noch stornieren.
                        </p>
                      )}
                      <VersandFormular
                        belegart="RE"
                        belegNummer={rechnungsnummerAnzeige(inv.invoice_number)}
                        customerId={inv.customer_id}
                        pending={sendInvoiceMail.isPending}
                        onSenden={(auftrag) => {
                          // Rückfrage aus Q1.7: Mailen eines Entwurfs schreibt ihn fest
                          if (inv.status === 'ENTWURF'
                              && !window.confirm(`Der Entwurf wird beim Mailen finalisiert. ${FINALISIEREN_RUECKFRAGE}`)) return;
                          sendInvoiceMail.mutate({ inv, auftrag });
                        }}
                        onAbbrechen={() => setVersandOffen(null)}
                      />
                    </div>
                  )}
                  {offeneRechnung === inv.id && (
                    <div className="mt-3 border-t pt-3 dark:border-gray-700">
                      <InvoiceDetail invoice={inv} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
        )}
      </div>
    </Modal>
  );
}
