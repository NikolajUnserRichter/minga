import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, FileText, Download, AlertCircle, CheckCircle, Clock, Mail } from 'lucide-react';
import { invoicesApi, salesApi, productsApi, integrationsApi } from '../services/api';
import { Invoice, InvoiceStatus, InvoiceType, Customer } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  EmptyState,
  useToast,
  Badge,
  SelectOption,
  Tabs,
  Pagination,
  Alert,
} from '../components/ui';
import { ListPageSkeleton } from '../components/ui/Skeleton';
import { belegHerunterladen } from '../services/belegordner';
import { belegartDerRechnung } from '../services/belegpfad';
import { getErrorMessage } from '../services/errors';
import { rechnungenJeReiter, reiterZaehler, type RechnungsReiter } from '../services/rechnungssuche';
import { eingabeAusZahl, positionsaenderung } from '../services/positionsaenderung';
import { euro } from '../services/zahlenformat';
import { BelegVersandAuftrag } from '../services/api';
import { VersandFormular, VersandProtokoll, versandMeldung, versandZeile } from '../components/domain/BelegVersand';
import { MonatsrechnungenDialog, MonatsrechnungenBanner } from '../components/domain/MonatsrechnungenDialog';
import { LeergutLaufModal } from '../components/domain/Leergut';
import { SepaEinzugsliste } from '../components/domain/SepaEinzugsliste';
import { useAuth } from '../context/AuthContext';
import { istEntwurfsnummer, rechnungsnummerAnzeige, FINALISIEREN_RUECKFRAGE } from '../services/rechnungsnummer';
import { lexofficeStatusLabel } from '../components/ui/statusLabels';

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  ENTWURF: 'Entwurf',
  OFFEN: 'Offen',
  TEILBEZAHLT: 'Teilbezahlt',
  BEZAHLT: 'Bezahlt',
  UEBERFAELLIG: 'Überfällig',
  STORNIERT: 'Storniert',
};

const STATUS_COLORS: Record<InvoiceStatus, 'gray' | 'info' | 'warning' | 'success' | 'danger' | 'purple'> = {
  ENTWURF: 'gray',
  OFFEN: 'info',
  TEILBEZAHLT: 'warning',
  BEZAHLT: 'success',
  UEBERFAELLIG: 'danger',
  STORNIERT: 'purple',
};

// Die Rechnungsliste lädt bis zu 100 Rechnungen (Obergrenze des Backends).
// Kommen genau 100 zurück, ist sie womöglich gekürzt — das muss sichtbar sein.
const LISTENGRENZE = 100;

const TYPE_LABELS: Record<InvoiceType, string> = {
  RECHNUNG: 'Rechnung',
  GUTSCHRIFT: 'Gutschrift',
  PROFORMA: 'Proforma',
};

export default function Invoices() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [isCreating, setIsCreating] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showDatevExport, setShowDatevExport] = useState(false);
  // Storno: Grund-Auswahl + Freitext, erzeugt die Stornorechnung
  const [stornoFuer, setStornoFuer] = useState<Invoice | null>(null);
  // Versand per E-Mail (Paket 3, Q2)
  const [versandFuer, setVersandFuer] = useState<Invoice | null>(null);
  const versandMutation = useMutation({
    mutationFn: ({ inv, auftrag }: { inv: Invoice; auftrag: BelegVersandAuftrag }) =>
      invoicesApi.sendInvoice(inv.id, auftrag),
    onSuccess: (zeile) => {
      // Nummer aus der Protokollzeile: ein Entwurf bekommt sie erst mit dem Versand (Q1)
      versandMeldung(toast, `Rechnung ${zeile.document_number}`, [zeile]);
      setVersandFuer(null);
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    // Ein Entwurf ist vor dem Versand finalisiert worden — auch wenn die Mail scheitert (Q1)
    onError: (e: any) => {
      toast.error(getErrorMessage(e, 'Fehler beim Versand'));
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
  });
  const [stornoGrundCode, setStornoGrundCode] = useState('FALSCHE_MENGE');
  const [stornoGrund, setStornoGrund] = useState('');
  // Monatsrechnungen (B5): Monat → Stand → Entwürfe anlegen
  const [monatsrechnungenOffen, setMonatsrechnungenOffen] = useState(false);


  // Leergutabrechnung (Pfand monatlich, Paket 3 Q6)
  const [leergutOffen, setLeergutOffen] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  // SEPA-Einzugsliste (B10): Bankdaten nur für Admin und Buchhaltung
  const [einzugOffen, setEinzugOffen] = useState(false);
  const { user } = useAuth();
  const darfBankdaten = ['admin', 'accounting'].some((r) => user?.roles?.includes(r));
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // Fetch invoices
  const { data: invoices = [], isLoading, isError, error } = useQuery({
    queryKey: ['invoices', { status: filterStatus, invoice_type: filterType }],
    queryFn: () =>
      invoicesApi.list({
        status: filterStatus === 'all' ? undefined : filterStatus as InvoiceStatus,
        invoice_type: filterType === 'all' ? undefined : filterType as InvoiceType,
        page_size: LISTENGRENZE,
      }),
  });

  // Fetch customers for creation
  const { data: customersData } = useQuery({
    queryKey: ['customers'],
    queryFn: () => salesApi.listCustomers(),
  });
  const customers = customersData?.items || [];

  // Fetch overdue
  const { data: overdueInvoices = [] } = useQuery({
    // Unter 'invoices': jede invalidateQueries({ queryKey: ['invoices'] })
    // (Zahlung, Storno, Finalisieren, Versand …) lädt auch „Überfällig“
    // neu — sonst blieben Liste und Zähler bis zum Neuladen stehen
    // (Paket 4.1, Z).
    queryKey: ['invoices', 'overdue'],
    queryFn: () => invoicesApi.getOverdue(),
  });

  // Finalize mutation
  const finalizeMutation = useMutation({
    mutationFn: (id: string) => invoicesApi.finalize(id),
    onSuccess: (inv: Invoice) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success(`Rechnung ${inv.invoice_number} finalisiert`);
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Finalisieren')),
  });

  // Entwurf ohne Rechnungsnummer verwerfen — verbraucht keine Nummer
  const discardMutation = useMutation({
    mutationFn: (id: string) => invoicesApi.discard(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Entwurf verworfen');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Verwerfen fehlgeschlagen')),
  });

  const { data: lexStatus } = useQuery({
    queryKey: ['integration', 'lexoffice'],
    queryFn: () => integrationsApi.lexofficeStatus(),
    retry: false,
  });

  const lexPushMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.lexofficePushInvoice(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success(res.status === 'already_synced' ? 'Bereits in lexoffice' : 'An lexoffice übertragen');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Übertragung fehlgeschlagen')),
  });

  const lexPullMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.lexofficePullStatus(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success(res.updated ? 'Als bezahlt übernommen' : `lexoffice-Status: ${lexofficeStatusLabel(res.lexoffice_status)}`);
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Statusabruf fehlgeschlagen')),
  });

  const stornoMutation = useMutation({
    mutationFn: () => invoicesApi.cancel(stornoFuer!.id, {
      reason: stornoGrund,
      reason_code: stornoGrundCode,
    }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      setStornoFuer(null);
      setStornoGrund('');
      toast.success(`Stornorechnung ${res.credit_note?.invoice_number ?? ''} erstellt — Lieferscheine sind wieder abrechenbar`);
      // Was der Storno nicht selbst löst (gezahltes Geld, lexoffice) — lange stehen lassen
      if (res.warnungen?.length) toast.warning(res.warnungen.join(' '), 15000);
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Storno fehlgeschlagen')),
  });



  const statusOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Status' },
    { value: 'ENTWURF', label: 'Entwurf' },
    { value: 'OFFEN', label: 'Offen' },
    { value: 'TEILBEZAHLT', label: 'Teilbezahlt' },
    { value: 'BEZAHLT', label: 'Bezahlt' },
    { value: 'UEBERFAELLIG', label: 'Überfällig' },
    { value: 'STORNIERT', label: 'Storniert' },
  ];

  const typeOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Typen' },
    { value: 'RECHNUNG', label: 'Rechnung' },
    { value: 'GUTSCHRIFT', label: 'Gutschrift' },
    { value: 'PROFORMA', label: 'Proforma' },
  ];

  // Je Reiter seine Liste, darauf die Suche „nach Nummer oder Kunde“
  // (Paket 4, B; G05). Tabelle und Zähler lesen dieselben Listen; der
  // Zähler geht an `badge` — `count` kennt die Reiterleiste nicht
  // (Paket 4.1, Z).
  const reiter = rechnungenJeReiter(invoices, overdueInvoices, search);
  // Volle Liste: ältere Rechnungen fehlen womöglich, die Zahl ist eine
  // Untergrenze („60+“). „Überfällig“ kommt ungekürzt von /invoices/overdue.
  const listeGekuerzt = invoices.length === LISTENGRENZE;

  const tabs = [
    { id: 'all', label: 'Alle', badge: reiterZaehler(reiter.all.length, listeGekuerzt) },
    { id: 'open', label: 'Offen', badge: reiterZaehler(reiter.open.length, listeGekuerzt) },
    { id: 'overdue', label: 'Überfällig', badge: reiterZaehler(reiter.overdue.length, false) },
    { id: 'paid', label: 'Bezahlt', badge: reiterZaehler(reiter.paid.length, listeGekuerzt) },
  ];

  const displayInvoices = reiter[activeTab as RechnungsReiter] ?? reiter.all;

  if (isLoading) {
    return <ListPageSkeleton />;
  }

  if (isError) {
    const keineBerechtigung = (error as { response?: { status?: number } })?.response?.status === 403;
    return (
      <div className="p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          {keineBerechtigung ? 'Keine Berechtigung für Rechnungen' : 'Rechnungen konnten nicht geladen werden'}
        </h2>
        {!keineBerechtigung && (
          <p className="text-gray-500 dark:text-gray-400">Bitte prüfe die Verbindung zum Server und versuche es erneut.</p>
        )}
      </div>
    );
  }

  const totalOpen = invoices
    .filter((i) => ['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG'].includes(i.status))
    .reduce((sum, i) => sum + (i.total - i.paid_amount), 0);

  return (
    <div>
      <PageHeader
        title="Rechnungswesen"
        subtitle={`${invoices.length === LISTENGRENZE ? `${LISTENGRENZE}+` : invoices.length} Rechnungen`}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" icon={<Download className="w-4 h-4" />} onClick={() => setShowDatevExport(true)}>
              DATEV Export
            </Button>
            <Button variant="secondary" onClick={() => setMonatsrechnungenOffen(true)}>
              Monatsrechnungen
            </Button>
            <Button variant="secondary" onClick={() => setLeergutOffen(true)}>
              Leergutabrechnung
            </Button>
            <LeergutLaufModal open={leergutOffen} onClose={() => setLeergutOffen(false)} />
            {darfBankdaten && (
              <Button variant="secondary" onClick={() => setEinzugOffen(true)}>
                Lastschrift-Einzüge
              </Button>
            )}
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
              Neue Rechnung
            </Button>
          </div>
        }
      />

      <MonatsrechnungenBanner onOeffnen={() => setMonatsrechnungenOffen(true)} />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Offene Forderungen</p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">{totalOpen.toFixed(2)} €</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
              <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Überfällig</p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">{overdueInvoices.length}</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
              <Clock className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Entwürfe</p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">{invoices.filter((i) => i.status === 'ENTWURF').length}</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Bezahlt (Monat)</p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">{invoices.filter((i) => i.status === 'BEZAHLT').length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Neuer Reiter oder neue Suche: zurück auf Seite 1, sonst bleibt ein
          Treffer auf einer leeren Seite unsichtbar. Kein useEffect: die
          Paket-3-Abnahme rendert diese Seite mit einem Ersatz, der nur
          useState kennt. */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={(id) => { setActiveTab(id); setCurrentPage(1); }} className="mb-6" />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen nach Nummer oder Kunde..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        <Select options={statusOptions} value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} />
        <Select options={typeOptions} value={filterType} onChange={(e) => setFilterType(e.target.value)} />
      </FilterBar>

      {invoices.length === LISTENGRENZE && (
        <p className="mb-2 text-sm text-amber-700 dark:text-amber-300">
          Es werden die neuesten {LISTENGRENZE} Rechnungen angezeigt. Ältere Rechnungen über den Status- oder Typfilter eingrenzen.
        </p>
      )}

      {displayInvoices.length === 0 ? (
        <EmptyState
          title="Keine Rechnungen gefunden"
          description={search ? 'Versuche eine andere Suche.' : 'Erstelle deine erste Rechnung.'}
          action={
            !search && (
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                Erste Rechnung erstellen
              </Button>
            )
          }
        />
      ) : (
        <div className="card overflow-hidden">
          {/* overflow-x-auto: die Tabelle ist breiter als schmale Fenster —
              ohne Scrollcontainer schnitt die Karte die rechten Spalten
              (Betrag, Aktionen) ersatzlos ab. */}
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Nummer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Kunde</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Datum</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Fällig</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Betrag</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {displayInvoices.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((invoice) => (
                <tr key={invoice.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{rechnungsnummerAnzeige(invoice.invoice_number)}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {invoice.invoice_type === 'GUTSCHRIFT' && invoice.original_invoice_id
                        ? 'Stornorechnung'
                        : invoice.beleg_art === 'LEERGUT'
                          ? 'Leergutabrechnung'
                          : TYPE_LABELS[invoice.invoice_type]}
                    </div>
                    {invoice.dispatches && invoice.dispatches.length > 0 && (
                      <div
                        className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate"
                        title={invoice.dispatches.map(versandZeile).join('\n')}
                      >
                        <Mail className="w-3 h-3 shrink-0" />
                        {versandZeile(invoice.dispatches[invoice.dispatches.length - 1])}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                    {invoice.customer_name || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(invoice.invoice_date).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(invoice.due_date).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{invoice.total.toFixed(2)} €</div>
                    {invoice.paid_amount > 0 && invoice.paid_amount < invoice.total && (
                      <div className="text-xs text-gray-500 dark:text-gray-400">Bezahlt: {invoice.paid_amount.toFixed(2)} €</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={STATUS_COLORS[invoice.status]}>{STATUS_LABELS[invoice.status]}</Badge>
                    {invoice.zahlungsart === 'LASTSCHRIFT' && (
                      <Badge variant={invoice.lastschrift_status === 'RUECKLASTSCHRIFT' ? 'danger' : 'purple'} className="ml-1">
                        {invoice.lastschrift_status === 'RUECKLASTSCHRIFT' ? 'Rücklastschrift' : 'Lastschrift'}
                      </Badge>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {invoice.status === 'ENTWURF' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (window.confirm(FINALISIEREN_RUECKFRAGE)) finalizeMutation.mutate(invoice.id);
                        }}
                        loading={finalizeMutation.isPending}
                      >
                        Finalisieren
                      </Button>
                    )}
                    {invoice.status === 'ENTWURF' && istEntwurfsnummer(invoice.invoice_number) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 dark:text-red-400"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Entwurf verwerfen? Er wird gelöscht; zugeordnete Lieferscheine werden wieder abrechenbar.')) {
                            discardMutation.mutate(invoice.id);
                          }
                        }}
                        loading={discardMutation.isPending}
                      >
                        Verwerfen
                      </Button>
                    )}
                    {['ENTWURF', 'OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG', 'BEZAHLT', 'STORNIERT'].includes(invoice.status) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Download className="w-4 h-4" />}
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            // Abschnitt O: Belegordner nach Belegart und Monat, sonst
                            // Download-Ordner; Name vom Server (B7: RE-….pdf bzw. Entwurf-….pdf)
                            await belegHerunterladen(
                              {
                                art: belegartDerRechnung(invoice),
                                datum: invoice.invoice_date,
                                ersatzname: `${invoice.invoice_number}.pdf`,
                              },
                              () => invoicesApi.downloadPdf(invoice.id),
                              toast,
                            );
                          } catch (err) {
                            toast.error('Fehler beim Laden des PDFs');
                          }
                        }}
                      >
                        PDF
                      </Button>
                    )}
                    {['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG', 'BEZAHLT'].includes(invoice.status)
                      && invoice.invoice_type === 'RECHNUNG' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 dark:text-red-400"
                        onClick={(e) => { e.stopPropagation(); setStornoFuer(invoice); }}
                      >
                        Stornieren
                      </Button>
                    )}
                    {lexStatus?.enabled && ['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG', 'BEZAHLT'].includes(invoice.status) && (
                      invoice.lexoffice_id ? (
                        <span className="ml-1 inline-flex items-center gap-1" title={`Übertragen am ${invoice.lexoffice_synced_at ? new Date(invoice.lexoffice_synced_at).toLocaleDateString('de-DE') : ''}`}>
                          <Badge variant="info">In lexoffice</Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Zahlungsstatus aus lexoffice abrufen"
                            loading={lexPullMutation.isPending && lexPullMutation.variables === invoice.id}
                            onClick={(e) => { e.stopPropagation(); lexPullMutation.mutate(invoice.id); }}
                          >
                            Status
                          </Button>
                        </span>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="An lexoffice übertragen"
                          loading={lexPushMutation.isPending && lexPushMutation.variables === invoice.id}
                          onClick={(e) => { e.stopPropagation(); lexPushMutation.mutate(invoice.id); }}
                        >
                          → lexoffice
                        </Button>
                      )
                    )}
                    {['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG'].includes(invoice.status)
                      // Lastschrift: keine Mahnung, solange der Einzug aussteht (B10)
                      && (invoice.zahlungsart !== 'LASTSCHRIFT' || invoice.lastschrift_status === 'RUECKLASTSCHRIFT') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Zahlungserinnerung / Mahnung erzeugen (PDF)"
                        disabled={invoice.beleg_art === 'LEERGUT' && Number(invoice.total) <= 0}
                        onClick={async (e) => {
                          e.stopPropagation();
                          const nextLevel = Math.min(3, (invoice.reminder_level || 0) + 1);
                          const stageLabel = ['Zahlungserinnerung', '1. Mahnung', '2. Mahnung'][nextLevel - 1];
                          const fee = nextLevel === 1 ? 0 : nextLevel === 2 ? 5 : 10;
                          try {
                            // Abschnitt O: erst die Ordner-Freigabe (braucht den frischen
                            // Klick), dann die Rückfrage, dann erzeugen. Abbrechen → null.
                            const ergebnis = await belegHerunterladen(
                              {
                                art: 'Mahnungen',
                                ersatzname: `Zahlungserinnerung_${invoice.invoice_number}_Stufe${nextLevel}.pdf`,
                              },
                              async () => {
                                if (!confirm(`${stageLabel} mit Gebühr €${fee.toFixed(2)} erzeugen?`)) return null;
                                return invoicesApi.generatePaymentReminder(invoice.id, nextLevel, fee);
                              },
                              toast,
                            );
                            if (!ergebnis) return;
                            queryClient.invalidateQueries({ queryKey: ['invoices'] });
                            toast.success(`${stageLabel} erzeugt`);
                          } catch (err: any) {
                            toast.error(getErrorMessage(err, 'Fehler beim Erzeugen'));
                          }
                        }}
                      >
                        Mahnung
                      </Button>
                    )}
                    {['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG'].includes(invoice.status) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedInvoice(invoice);
                          setShowPaymentModal(true);
                        }}
                      >
                        Zahlung
                      </Button>
                    )}
                    {(invoice.status !== 'STORNIERT'
                      || (invoice.invoice_type === 'GUTSCHRIFT' && !!invoice.original_invoice_id)) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Mail className="w-4 h-4" />}
                        onClick={(e) => { e.stopPropagation(); setVersandFuer(invoice); }}
                      >
                        Versenden
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => setSelectedInvoice(invoice)}>
                      {invoice.status === 'ENTWURF' ? 'Bearbeiten' : 'Details'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {displayInvoices.length > itemsPerPage && (
            <Pagination
              currentPage={currentPage}
              totalPages={Math.ceil(displayInvoices.length / itemsPerPage)}
              totalItems={displayInvoices.length}
              itemsPerPage={itemsPerPage}
              onPageChange={setCurrentPage}
            />
          )}
        </div>
      )}

      {/* Create Invoice Modal */}
      <Modal
        open={isCreating}
        onClose={() => setIsCreating(false)}
        title="Neue Rechnung"
        size="lg"
      >
        <InvoiceCreateForm
          customers={customers}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['invoices'] });
            setIsCreating(false);
            toast.success('Rechnung erstellt');
          }}
          onCancel={() => setIsCreating(false)}
        />
      </Modal>

      {/* Payment Modal */}
      <Modal
        open={showPaymentModal && !!selectedInvoice}
        onClose={() => {
          setShowPaymentModal(false);
          setSelectedInvoice(null);
        }}
        title={`Zahlung für ${selectedInvoice?.invoice_number}`}
      >
        {selectedInvoice && (
          <PaymentForm
            invoice={selectedInvoice}
            onSubmit={() => {
              queryClient.invalidateQueries({ queryKey: ['invoices'] });
              setShowPaymentModal(false);
              setSelectedInvoice(null);
              toast.success('Zahlung erfasst');
            }}
            onCancel={() => {
              setShowPaymentModal(false);
              setSelectedInvoice(null);
            }}
          />
        )}
      </Modal>

      {/* DATEV Export Modal */}
      <Modal open={einzugOffen} onClose={() => setEinzugOffen(false)} title="Lastschrift-Einzüge" size="xl">
        {einzugOffen && <SepaEinzugsliste />}
      </Modal>

      <Modal open={showDatevExport} onClose={() => setShowDatevExport(false)} title="DATEV Export">
        <DatevExportForm onClose={() => setShowDatevExport(false)} />
      </Modal>

      {/* Versand per E-Mail: eine Mail an alle Empfänger (Paket 3, Q2) */}
      <Modal
        open={!!versandFuer}
        onClose={() => setVersandFuer(null)}
        title={`Rechnung ${rechnungsnummerAnzeige(versandFuer?.invoice_number)} versenden`}
      >
        {versandFuer && (
          <div className="space-y-3">
            {versandFuer.status === 'ENTWURF' && (
              <Alert variant="info">
                Der Entwurf wird beim Mailen finalisiert: Er erhält die nächste freie Rechnungsnummer und lässt sich danach nur noch stornieren.
              </Alert>
            )}
            <VersandProtokoll eintraege={versandFuer.dispatches} />
            <VersandFormular
              belegart="RE"
              belegNummer={rechnungsnummerAnzeige(versandFuer.invoice_number)}
              customerId={versandFuer.customer_id}
              pending={versandMutation.isPending}
              onSenden={(auftrag) => {
                // Rückfrage aus Q1.7: Mailen eines Entwurfs schreibt ihn fest
                if (versandFuer.status === 'ENTWURF'
                    && !window.confirm(`Der Entwurf wird beim Mailen finalisiert. ${FINALISIEREN_RUECKFRAGE}`)) return;
                versandMutation.mutate({ inv: versandFuer, auftrag });
              }}
              onAbbrechen={() => setVersandFuer(null)}
            />
          </div>
        )}
      </Modal>

      {/* Storno: eigene Nummer aus dem regulären Kreis, Original wird gesperrt */}
      <Modal open={!!stornoFuer} onClose={() => setStornoFuer(null)}
             title={`Rechnung ${stornoFuer?.invoice_number ?? ''} stornieren`}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Es wird eine <b>Stornorechnung mit eigener Nummer</b> erzeugt; das Original
            bleibt erhalten und wird schreibgeschützt. Zugeordnete Lieferscheine werden
            wieder abrechenbar. Original und Stornorechnung gleichen sich aus und stehen
            danach beide auf „Storniert“.
          </p>
          {stornoFuer && Number(stornoFuer.paid_amount) > 0 && (
            <Alert variant="warning" title="Auf diese Rechnung wurde schon gezahlt">
              {Number(stornoFuer.paid_amount).toFixed(2).replace('.', ',')} € sind bereits verbucht.
              Die Zahlung bleibt am stornierten Beleg stehen — bei der Neuausstellung als
              Zahlung erfassen oder dem Kunden erstatten.
            </Alert>
          )}
          <Select label="Grund" value={stornoGrundCode}
                  onChange={(e) => setStornoGrundCode(e.target.value)}
                  options={[
                    { value: 'FALSCHER_EMPFAENGER', label: 'Falscher Empfänger' },
                    { value: 'FALSCHE_MENGE', label: 'Falsche Menge' },
                    { value: 'PREISFEHLER', label: 'Preisfehler' },
                    { value: 'FALSCHER_STEUERSATZ', label: 'Falscher Steuersatz' },
                    { value: 'LIEFERUNG_NICHT_ERFOLGT', label: 'Lieferung nicht erfolgt' },
                    { value: 'SONSTIGES', label: 'Sonstiges' },
                  ]} />
          <Input label="Erläuterung" value={stornoGrund}
                 onChange={(e) => setStornoGrund(e.target.value)}
                 placeholder="z.B. Kunde hat 5 statt 10 Schalen erhalten" />
          <div className="flex justify-end gap-2">
            <button className="btn btn-secondary" onClick={() => setStornoFuer(null)}>Abbrechen</button>
            <Button onClick={() => stornoMutation.mutate()}
                    loading={stornoMutation.isPending}
                    disabled={!stornoGrund.trim()}>
              Stornorechnung erstellen
            </Button>
          </div>
        </div>
      </Modal>

      <MonatsrechnungenDialog
        open={monatsrechnungenOffen}
        onClose={() => setMonatsrechnungenOffen(false)}
        onRechnungOeffnen={(id) => {
          setMonatsrechnungenOffen(false);
          invoicesApi.get(id).then(setSelectedInvoice)
            .catch((e) => toast.error(getErrorMessage(e, 'Rechnung konnte nicht geladen werden')));
        }}
      />

      {/* Invoice Detail Modal */}
      <Modal
        open={!!selectedInvoice && !showPaymentModal}
        onClose={() => setSelectedInvoice(null)}
        title={`Rechnung ${rechnungsnummerAnzeige(selectedInvoice?.invoice_number)}`}
        size="lg"
      >
        {selectedInvoice && <InvoiceDetail invoice={selectedInvoice} />}
      </Modal>
    </div>
  );
}

// Invoice Create Form
interface InvoiceCreateFormProps {
  customers: Customer[];
  onSubmit: () => void;
  onCancel: () => void;
}

function InvoiceCreateForm({ customers, onSubmit, onCancel }: InvoiceCreateFormProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    customer_id: '',
    invoice_type: 'RECHNUNG' as InvoiceType,
    invoice_date: new Date().toISOString().split('T')[0],
    delivery_date: '',
    due_date: '',
    header_text: '',
    footer_text: '',
    internal_notes: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.customer_id) {
      toast.error('Bitte Kunde auswählen');
      return;
    }

    setLoading(true);
    try {
      await invoicesApi.create({
        ...formData,
        delivery_date: formData.delivery_date || undefined,
        due_date: formData.due_date || undefined,
        internal_notes: formData.internal_notes || undefined,
      });
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Erstellen');
    } finally {
      setLoading(false);
    }
  };

  const customerOptions: SelectOption[] = [
    { value: '', label: 'Kunde auswählen...' },
    ...customers.map((c) => ({ value: c.id, label: c.name })),
  ];

  const typeOptions: SelectOption[] = [
    { value: 'RECHNUNG', label: 'Rechnung' },
    { value: 'GUTSCHRIFT', label: 'Gutschrift' },
    { value: 'PROFORMA', label: 'Proforma' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Select
        label="Kunde"
        required
        options={customerOptions}
        value={formData.customer_id}
        onChange={(e) => setFormData({ ...formData, customer_id: e.target.value })}
      />

      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Typ"
          options={typeOptions}
          value={formData.invoice_type}
          onChange={(e) => setFormData({ ...formData, invoice_type: e.target.value as InvoiceType })}
        />
        <Input
          label="Rechnungsdatum"
          type="date"
          value={formData.invoice_date}
          onChange={(e) => setFormData({ ...formData, invoice_date: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Lieferdatum"
          type="date"
          value={formData.delivery_date}
          onChange={(e) => setFormData({ ...formData, delivery_date: e.target.value })}
        />
        <Input
          label="Fällig am"
          type="date"
          placeholder="Automatisch..."
          value={formData.due_date}
          onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
        />
      </div>


      <Input
        label="Kopftext"
        value={formData.header_text}
        onChange={(e) => setFormData({ ...formData, header_text: e.target.value })}
        placeholder="Optionaler Text im Kopfbereich..."
      />

      <Input
        label="Interne Notizen"
        value={formData.internal_notes}
        onChange={(e) => setFormData({ ...formData, internal_notes: e.target.value })}
        placeholder="Nur intern sichtbar..."
      />

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          Erstellen
        </Button>
      </div>
    </form>
  );
}

// Payment Form
interface PaymentFormProps {
  invoice: Invoice;
  onSubmit: () => void;
  onCancel: () => void;
}

function PaymentForm({ invoice, onSubmit, onCancel }: PaymentFormProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const openAmount = invoice.total - invoice.paid_amount;

  const [formData, setFormData] = useState({
    amount: openAmount,
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'UEBERWEISUNG',
    reference: '',
    notes: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await invoicesApi.recordPayment(invoice.id, formData);
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Erfassen');
    } finally {
      setLoading(false);
    }
  };

  const methodOptions: SelectOption[] = [
    { value: 'UEBERWEISUNG', label: 'Überweisung' },
    { value: 'LASTSCHRIFT', label: 'Lastschrift' },
    { value: 'BAR', label: 'Bar' },
    { value: 'EC', label: 'EC-Karte' },
    { value: 'KREDITKARTE', label: 'Kreditkarte' },
    { value: 'PAYPAL', label: 'PayPal' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Rechnungsbetrag:</span>
          <span className="font-medium">{invoice.total.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Bereits bezahlt:</span>
          <span className="font-medium">{invoice.paid_amount.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm font-semibold mt-2 pt-2 border-t">
          <span>Offen:</span>
          <span className="text-red-600 dark:text-red-400">{openAmount.toFixed(2)} €</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Betrag"
          type="number"
          step="0.01"
          required
          max={openAmount}
          value={formData.amount}
          onChange={(e) => setFormData({ ...formData, amount: Number(e.target.value) })}
          endIcon="€"
        />
        <Input
          label="Datum"
          type="date"
          required
          value={formData.payment_date}
          onChange={(e) => setFormData({ ...formData, payment_date: e.target.value })}
        />
      </div>

      <Select
        label="Zahlungsart"
        options={methodOptions}
        value={formData.payment_method}
        onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
      />

      <Input
        label="Referenz"
        value={formData.reference}
        onChange={(e) => setFormData({ ...formData, reference: e.target.value })}
        placeholder="z.B. Transaktionsnummer..."
      />

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          Zahlung erfassen
        </Button>
      </div>
    </form>
  );
}

// DATEV Export Form
function DatevExportForm({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  // Kontenrahmen und Sperre des Mandanten (Nachtrag 09.10., D). Das Backend
  // lehnt einen gesperrten Export ohnehin mit 409 ab; der Dialog sagt es vorher.
  const { data: einstellungen, isError, error } = useQuery({
    queryKey: ['datev-einstellungen'],
    queryFn: () => invoicesApi.datevEinstellungen(),
  });
  const sperrgrund = einstellungen?.sperrgrund ?? null;
  const [formData, setFormData] = useState({
    from_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
    to_date: new Date().toISOString().split('T')[0],
    include_payments: true,
    erneut_exportieren: false,
  });

  const handleExport = async () => {
    setLoading(true);
    try {
      // Abschnitt O: Belegordner DATEV-Exporte/<Monat des Zeitraumendes>, sonst Download-Ordner
      const ergebnis = await belegHerunterladen(
        {
          art: 'DATEV-Exporte',
          datum: formData.to_date,
          ersatzname: `DATEV_Export_${formData.from_date}_${formData.to_date}.csv`,
          mime: 'text/csv',
        },
        async () => {
          const result = await invoicesApi.exportDatev(formData);
          if (result.record_count === 0) {
            // Bereits exportierte Belege kommen nur mit "erneut exportieren" wieder —
            // eine leere Datei herunterzuladen hilft niemandem.
            toast.info('Keine neuen Buchungen im Zeitraum. Bereits exportierte nur über „Erneut exportieren".');
            return null;
          }
          toast.success(`Export erfolgreich: ${result.record_count} Datensätze`);
          return { data: result.csv_content };
        },
        toast,
      );
      if (ergebnis) onClose();
    } catch (error) {
      // 409 mit Klartext: Sperre oder Sonderkonto, das nicht zum Kontenrahmen passt
      toast.error(getErrorMessage(error, 'Fehler beim Export'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {isError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          DATEV-Einstellungen ließen sich nicht laden: {getErrorMessage(error)}
        </p>
      )}
      {einstellungen && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-sm text-gray-600 dark:text-gray-300">
          <div className="font-medium text-gray-800 dark:text-gray-100">
            Kontenrahmen {einstellungen.kontenrahmen}
          </div>
          <div className="text-xs mt-1">
            {einstellungen.konten.map((k) => `${k.bezeichnung} ${k.konto}`).join(' · ')}
          </div>
        </div>
      )}
      {sperrgrund && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-900/30 dark:border-amber-700 p-3 text-sm text-amber-800 dark:text-amber-200">
          <div className="font-medium">DATEV-Export gesperrt</div>
          <div>{sperrgrund}</div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Von"
          type="date"
          value={formData.from_date}
          onChange={(e) => setFormData({ ...formData, from_date: e.target.value })}
        />
        <Input
          label="Bis"
          type="date"
          value={formData.to_date}
          onChange={(e) => setFormData({ ...formData, to_date: e.target.value })}
        />
      </div>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={formData.include_payments}
          onChange={(e) => setFormData({ ...formData, include_payments: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700 dark:text-gray-300">Zahlungen einschließen</span>
      </label>

      <label className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={formData.erneut_exportieren}
          onChange={(e) => setFormData({ ...formData, erneut_exportieren: e.target.checked })}
          className="mt-0.5 w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700 dark:text-gray-300">
          Bereits exportierte erneut exportieren
          {formData.erneut_exportieren && (
            <span className="block text-amber-700 dark:text-amber-300">
              Nur verwenden, wenn die vorige Datei nicht in DATEV importiert wurde — sonst wird doppelt gebucht.
            </span>
          )}
        </span>
      </label>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onClose}>
          Abbrechen
        </Button>
        <Button onClick={handleExport} loading={loading} disabled={!einstellungen || isError || !!sperrgrund} fullWidth icon={<Download className="w-4 h-4" />}>
          Exportieren
        </Button>
      </div>
    </div>
  );
}

// Invoice Detail — auch im Belege-Dialog der Bestellung (OrderDocumentsModal)
export function InvoiceDetail({ invoice: initial }: { invoice: Invoice }) {
  const queryClient = useQueryClient();
  const toast = useToast();

  // Refetch invoice details after every mutation so the lines list stays in sync.
  const { data: refreshed, isError: detailFehler } = useQuery({
    queryKey: ['invoice', initial.id],
    queryFn: () => invoicesApi.get(initial.id),
    initialData: initial,
    // initialData ist der Listeneintrag. GET /invoices liefert ihn ohne
    // Positionen (InvoiceResponse, kein lines). Mit staleTime 60 s aus
    // main.tsx gälte er als frisch und würde beim Öffnen nicht nachgeladen —
    // der Dialog zeigte "Keine Positionen" und keinen Löschknopf (B4).
    refetchOnMount: 'always',
  });
  const invoice = refreshed || initial;
  // Leergutbeleg (Paket 3, Q6): Positionen und Kunde ergeben sich aus dem
  // Leergutkonto, der Server lehnt Änderungen ab (409). Der Dialog zeigt ihn
  // deshalb nur an; korrigiert wird im Leergutkonto, dann verwerfen und neu anlegen.
  const isDraft = invoice.status === 'ENTWURF' && invoice.beleg_art !== 'LEERGUT';

  const { data: products = [] } = useQuery({
    queryKey: ['products', 'active'],
    queryFn: () => productsApi.list({ is_active: true }),
    enabled: isDraft,
  });

  // Header-Edit (nur ENTWURF)
  const { data: customersData } = useQuery({
    queryKey: ['customers', 'for-invoice-edit'],
    queryFn: () => salesApi.listCustomers(),
    enabled: isDraft,
  });
  const [headerEdit, setHeaderEdit] = useState({
    customer_id: '',
    invoice_date: '',
    due_date: '',
    discount_percent: '0',
  });
  const [headerDirty, setHeaderDirty] = useState(false);
  // Sync edit-state when invoice changes
  if (!headerDirty && (headerEdit.customer_id !== invoice.customer_id ||
      headerEdit.invoice_date !== invoice.invoice_date.slice(0, 10) ||
      headerEdit.due_date !== (invoice.due_date ? invoice.due_date.slice(0, 10) : '') ||
      headerEdit.discount_percent !== String(Number(invoice.discount_percent ?? 0)))) {
    setHeaderEdit({
      customer_id: invoice.customer_id,
      invoice_date: invoice.invoice_date.slice(0, 10),
      due_date: invoice.due_date ? invoice.due_date.slice(0, 10) : '',
      discount_percent: String(Number(invoice.discount_percent ?? 0)),
    });
  }
  const saveHeaderMutation = useMutation({
    mutationFn: () => invoicesApi.update(invoice.id, {
      customer_id: headerEdit.customer_id,
      invoice_date: headerEdit.invoice_date,
      due_date: headerEdit.due_date || undefined,
      // Einmalrabatt: gilt nur für diese Rechnung, der Kunden-Stammrabatt bleibt
      discount_percent: Number(headerEdit.discount_percent || 0),
    } as any),
    onSuccess: () => {
      setHeaderDirty(false);
      queryClient.invalidateQueries({ queryKey: ['invoice', invoice.id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Kopfdaten gespeichert');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Speichern fehlgeschlagen')),
  });

  const [newLine, setNewLine] = useState({
    product_id: '',
    description: '',
    quantity: 1,
    unit: 'STK',
    unit_price: 0,
    tax_rate: 'REDUZIERT' as const,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['invoices'] });
    queryClient.invalidateQueries({ queryKey: ['invoice', invoice.id] });
  };

  const addLineMutation = useMutation({
    mutationFn: () =>
      invoicesApi.addLine(invoice.id, {
        product_id: newLine.product_id || undefined,
        description: newLine.description,
        quantity: newLine.quantity,
        unit: newLine.unit,
        unit_price: newLine.unit_price,
        tax_rate: newLine.tax_rate,
      } as any),
    onSuccess: () => {
      invalidate();
      setNewLine({ product_id: '', description: '', quantity: 1, unit: 'STK', unit_price: 0, tax_rate: 'REDUZIERT' });
      toast.success('Position hinzugefügt');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Hinzufügen')),
  });

  // Menge und Einzelpreis einer Position im Entwurf ändern (Paket 4, B; G21).
  // Immer nur eine Zeile in Arbeit; der Server rechnet Zeile und Summen neu.
  const [zeileInArbeit, setZeileInArbeit] = useState<{ id: string; menge: string; preis: string } | null>(null);
  const updateLineMutation = useMutation({
    mutationFn: ({ lineId, daten }: { lineId: string; daten: { quantity?: number; unit_price?: number } }) =>
      invoicesApi.updateLine(invoice.id, lineId, daten),
    onSuccess: () => {
      invalidate();
      setZeileInArbeit(null);
      toast.success('Position geändert');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Position konnte nicht geändert werden')),
  });
  const zeileSpeichern = (line: { id: string; quantity: number; unit_price: number }) => {
    if (!zeileInArbeit) return;
    const ergebnis = positionsaenderung(line, zeileInArbeit.menge, zeileInArbeit.preis);
    if ('fehler' in ergebnis) {
      toast.error(ergebnis.fehler);
      return;
    }
    if (Object.keys(ergebnis.daten).length === 0) {
      setZeileInArbeit(null);
      return;
    }
    updateLineMutation.mutate({ lineId: line.id, daten: ergebnis.daten });
  };

  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => invoicesApi.deleteLine(invoice.id, lineId),
    onSuccess: () => {
      invalidate();
      toast.success('Position entfernt');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Position konnte nicht entfernt werden')),
  });

  const handleProductSelect = (productId: string) => {
    const product = products.find((p) => p.id === productId);
    if (product) {
      setNewLine({
        ...newLine,
        product_id: productId,
        description: product.name,
        unit_price: Number(product.base_price) || 0,
        tax_rate: (product.tax_rate as any) || 'REDUZIERT',
      });
    } else {
      setNewLine({ ...newLine, product_id: '' });
    }
  };

  return (
    <div className="space-y-6">
      {isDraft ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-500 dark:text-gray-400">Kunde *</label>
              <select
                value={headerEdit.customer_id}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, customer_id: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md focus:outline-none focus:ring-1 focus:ring-minga-500"
              >
                <option value="">Kunde wählen...</option>
                {(customersData?.items || []).map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
              <Badge variant={STATUS_COLORS[invoice.status]}>{STATUS_LABELS[invoice.status]}</Badge>
            </div>
            <div>
              <label className="text-sm text-gray-500 dark:text-gray-400">Rechnungsdatum *</label>
              <input
                type="date"
                value={headerEdit.invoice_date}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, invoice_date: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
              />
              {/* Paket 4, B: festgeschrieben wird immer mit dem Ausstellungstag */}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Beim Finalisieren gilt der Tag der Ausstellung; das Zahlungsziel in Tagen bleibt.
              </p>
            </div>
            <div>
              <label className="text-sm text-gray-500 dark:text-gray-400">Fällig am</label>
              <input
                type="date"
                value={headerEdit.due_date}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, due_date: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
              />
            </div>
            <div>
              <label className="text-sm text-gray-500 dark:text-gray-400">Einmalrabatt (%)</label>
              <input
                type="number" min="0" max="100" step="0.5"
                value={headerEdit.discount_percent}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, discount_percent: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
              />
            </div>
          </div>
          {headerDirty && (
            <div className="flex justify-end gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setHeaderEdit({
                    customer_id: invoice.customer_id,
                    invoice_date: invoice.invoice_date.slice(0, 10),
                    due_date: invoice.due_date ? invoice.due_date.slice(0, 10) : '',
                    discount_percent: String(Number(invoice.discount_percent ?? 0)),
                  });
                  setHeaderDirty(false);
                }}
              >
                Verwerfen
              </Button>
              <Button
                size="sm"
                loading={saveHeaderMutation.isPending}
                disabled={!headerEdit.customer_id || !headerEdit.invoice_date}
                onClick={() => saveHeaderMutation.mutate()}
              >
                Kopfdaten speichern
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Kunde</p>
            <p className="font-medium">{invoice.customer_name || '–'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
            <Badge variant={STATUS_COLORS[invoice.status]}>{STATUS_LABELS[invoice.status]}</Badge>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Rechnungsdatum</p>
            <p className="font-medium">{new Date(invoice.invoice_date).toLocaleDateString('de-DE')}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Fällig am</p>
            <p className="font-medium">{invoice.due_date ? new Date(invoice.due_date).toLocaleDateString('de-DE') : '–'}</p>
          </div>
        </div>
      )}

      <div className="border-t pt-4">
        <h4 className="font-medium mb-2">Positionen</h4>
        {invoice.lines && invoice.lines.length > 0 ? (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Beschreibung</th>
                <th className="text-right py-2">Menge</th>
                <th className="text-right py-2">Preis</th>
                <th className="text-right py-2">Summe</th>
                {isDraft && <th className="w-40"></th>}
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line) => (
                <tr key={line.id} className="border-b">
                  <td className="py-2">
                    {line.description}
                    {line.is_deposit && (
                      <Badge variant="info" size="sm" className="ml-2">Pfand</Badge>
                    )}
                  </td>
                  {zeileInArbeit?.id === line.id ? (
                    <>
                      <td className="text-right py-2">
                        <div className="flex items-center justify-end gap-1">
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label="Menge"
                            value={zeileInArbeit.menge}
                            onChange={(e) => setZeileInArbeit({ ...zeileInArbeit, menge: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') zeileSpeichern(line);
                              // Nur die Zeile verwerfen: Modal.tsx schließt bei Escape
                              // über einen keydown-Listener auf document den Dialog.
                              if (e.key === 'Escape') { e.stopPropagation(); setZeileInArbeit(null); }
                            }}
                            className="w-20 px-2 py-1 text-right border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
                          />
                          <span>{line.unit}</span>
                        </div>
                      </td>
                      <td className="text-right py-2">
                        <div className="flex items-center justify-end gap-1">
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label="Einzelpreis"
                            value={zeileInArbeit.preis}
                            onChange={(e) => setZeileInArbeit({ ...zeileInArbeit, preis: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') zeileSpeichern(line);
                              // Nur die Zeile verwerfen: Modal.tsx schließt bei Escape
                              // über einen keydown-Listener auf document den Dialog.
                              if (e.key === 'Escape') { e.stopPropagation(); setZeileInArbeit(null); }
                            }}
                            className="w-24 px-2 py-1 text-right border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
                          />
                          <span>€</span>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="text-right py-2">
                        {eingabeAusZahl(line.quantity)} {line.unit}
                      </td>
                      <td className="text-right py-2">{euro(line.unit_price)}</td>
                    </>
                  )}
                  <td className="text-right py-2">{euro(line.line_total)}</td>
                  {isDraft && zeileInArbeit?.id === line.id && (
                    <td className="text-right py-2 whitespace-nowrap">
                      <button
                        type="button"
                        disabled={updateLineMutation.isPending}
                        onClick={() => zeileSpeichern(line)}
                        className="mr-3 text-minga-600 hover:text-minga-800 dark:text-minga-400"
                      >
                        Speichern
                      </button>
                      <button
                        type="button"
                        onClick={() => setZeileInArbeit(null)}
                        className="text-gray-500 hover:text-gray-700 dark:text-gray-400"
                      >
                        Abbrechen
                      </button>
                    </td>
                  )}
                  {isDraft && zeileInArbeit?.id !== line.id && (
                    <td className="text-right py-2 whitespace-nowrap">
                      <button
                        type="button"
                        title="Menge und Einzelpreis ändern"
                        disabled={updateLineMutation.isPending}
                        onClick={() => setZeileInArbeit({
                          id: line.id,
                          menge: eingabeAusZahl(line.quantity),
                          preis: eingabeAusZahl(line.unit_price),
                        })}
                        className="mr-3 text-gray-600 hover:text-gray-900 dark:text-gray-300"
                      >
                        Ändern
                      </button>
                      <button
                        type="button"
                        title="Position entfernen"
                        disabled={deleteLineMutation.isPending}
                        onClick={() => {
                          if (!confirm(`Position „${line.description}" aus dem Entwurf entfernen?`)) return;
                          deleteLineMutation.mutate(line.id);
                        }}
                        className="text-red-600 hover:text-red-800 dark:text-red-400"
                      >
                        ×
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {invoice.lines
              ? 'Keine Positionen'
              : detailFehler
                ? 'Positionen konnten nicht geladen werden.'
                : 'Positionen werden geladen …'}
          </p>
        )}

        {isDraft && (
          <div className="mt-4 p-4 border border-dashed border-gray-300 dark:border-gray-700 rounded-lg space-y-3">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Position hinzufügen</p>
            <Select
              label="Produkt (optional — füllt Beschreibung/Preis)"
              options={[
                { value: '', label: '— frei eingeben —' },
                ...products.map((p) => ({ value: p.id, label: `${p.name} (${p.sku})` })),
              ]}
              value={newLine.product_id}
              onChange={(e) => handleProductSelect(e.target.value)}
            />
            <Input
              label="Beschreibung"
              required
              value={newLine.description}
              onChange={(e) => setNewLine({ ...newLine, description: e.target.value })}
              placeholder="z.B. Sonnenblume Microgreens 100g"
            />
            <div className="grid grid-cols-4 gap-2">
              <Input
                label="Menge"
                type="number"
                step="0.01"
                min={0.01}
                value={newLine.quantity}
                onChange={(e) => setNewLine({ ...newLine, quantity: Number(e.target.value) || 0 })}
              />
              <Select
                label="Einheit"
                options={[
                  { value: 'STK', label: 'Stück' },
                  { value: 'SCHALE', label: 'Schale' },
                  { value: 'TRAY', label: 'Tray' },
                  { value: 'KISTE_12', label: 'Kiste 12' },
                  { value: 'KISTE_6', label: 'Kiste 6' },
                  { value: 'KARTON_6', label: 'Karton 6' },
                  { value: 'g', label: 'g' },
                  { value: 'kg', label: 'kg' },
                ]}
                value={newLine.unit}
                onChange={(e) => setNewLine({ ...newLine, unit: e.target.value })}
              />
              <Input
                label="Einzelpreis"
                type="number"
                step="0.01"
                min={0}
                value={newLine.unit_price}
                onChange={(e) => setNewLine({ ...newLine, unit_price: Number(e.target.value) || 0 })}
                endIcon="€"
              />
              <Select
                label="MwSt"
                options={[
                  { value: 'REDUZIERT', label: '7%' },
                  { value: 'STANDARD', label: '19%' },
                  { value: 'STEUERFREI', label: '0%' },
                ]}
                value={newLine.tax_rate}
                onChange={(e) => setNewLine({ ...newLine, tax_rate: e.target.value as any })}
              />
            </div>
            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                variant="primary"
                disabled={!newLine.description || newLine.quantity <= 0}
                loading={addLineMutation.isPending}
                onClick={() => addLineMutation.mutate()}
              >
                Position hinzufügen
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="border-t pt-4">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Zwischensumme:</span>
          <span>{euro(invoice.subtotal)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">MwSt:</span>
          <span>{euro(invoice.tax_amount)}</span>
        </div>
        <div className="flex justify-between font-semibold mt-2 pt-2 border-t">
          <span>Gesamt:</span>
          <span>{euro(invoice.total)}</span>
        </div>
        {/* Pfand steckt im Gesamtbetrag, gehört aber dem Kunden — er bekommt
            es mit dem Gebinde zurück. Nachrichtlich, nicht addieren. */}
        {!!invoice.total_deposit && invoice.total_deposit > 0 && (
          <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400 mt-1">
            <span>darin enthaltenes Pfand:</span>
            <span>{euro(invoice.total_deposit)}</span>
          </div>
        )}
        {invoice.paid_amount > 0 && (
          <div className="flex justify-between text-sm text-green-600 dark:text-green-400 mt-1">
            <span>Bezahlt:</span>
            <span>{euro(invoice.paid_amount)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
