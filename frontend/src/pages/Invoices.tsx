import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, FileText, Download, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { invoicesApi, salesApi, productsApi } from '../services/api';
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
} from '../components/ui';
import { ListPageSkeleton } from '../components/ui/Skeleton';

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
  const [activeTab, setActiveTab] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // Fetch invoices
  const { data: invoices = [], isLoading, isError } = useQuery({
    queryKey: ['invoices', { status: filterStatus, invoice_type: filterType }],
    queryFn: () =>
      invoicesApi.list({
        status: filterStatus === 'all' ? undefined : filterStatus as InvoiceStatus,
        invoice_type: filterType === 'all' ? undefined : filterType as InvoiceType,
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
    queryKey: ['invoices-overdue'],
    queryFn: () => invoicesApi.getOverdue(),
  });

  // Finalize mutation
  const finalizeMutation = useMutation({
    mutationFn: (id: string) => invoicesApi.finalize(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Rechnung finalisiert');
    },
    onError: () => {
      toast.error('Fehler beim Finalisieren');
    },
  });

  const filteredInvoices = invoices.filter(
    (invoice) =>
      invoice.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
      invoice.customer_name?.toLowerCase().includes(search.toLowerCase())
  );

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

  const tabs = [
    { id: 'all', label: 'Alle', count: invoices.length },
    { id: 'open', label: 'Offen', count: invoices.filter((i) => i.status === 'OFFEN').length },
    { id: 'overdue', label: 'Überfällig', count: overdueInvoices.length },
    { id: 'paid', label: 'Bezahlt', count: invoices.filter((i) => i.status === 'BEZAHLT').length },
  ];

  const displayInvoices =
    activeTab === 'overdue'
      ? overdueInvoices
      : activeTab === 'open'
        ? invoices.filter((i) => i.status === 'OFFEN')
        : activeTab === 'paid'
          ? invoices.filter((i) => i.status === 'BEZAHLT')
          : filteredInvoices;

  if (isLoading) {
    return <ListPageSkeleton />;
  }

  if (isError) {
    return (
      <div className="p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Rechnungen konnten nicht geladen werden</h2>
        <p className="text-gray-500 dark:text-gray-400">Bitte prüfe die Verbindung zum Server und versuche es erneut.</p>
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
        subtitle={`${invoices.length} Rechnungen`}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" icon={<Download className="w-4 h-4" />} onClick={() => setShowDatevExport(true)}>
              DATEV Export
            </Button>
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
              Neue Rechnung
            </Button>
          </div>
        }
      />

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

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="mb-6" />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen nach Nummer oder Kunde..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        <Select options={statusOptions} value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} />
        <Select options={typeOptions} value={filterType} onChange={(e) => setFilterType(e.target.value)} />
      </FilterBar>

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
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{invoice.invoice_number}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{TYPE_LABELS[invoice.invoice_type]}</div>
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
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {invoice.status === 'ENTWURF' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => finalizeMutation.mutate(invoice.id)}
                        loading={finalizeMutation.isPending}
                      >
                        Finalisieren
                      </Button>
                    )}
                    {['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG', 'BEZAHLT'].includes(invoice.status) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Download className="w-4 h-4" />}
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            const response = await invoicesApi.downloadPdf(invoice.id);
                            const url = window.URL.createObjectURL(new Blob([response.data]));
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `Rechnung_${invoice.invoice_number}.pdf`;
                            a.click();
                            window.URL.revokeObjectURL(url);
                          } catch (err) {
                            toast.error('Fehler beim Laden des PDFs');
                          }
                        }}
                      >
                        PDF
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
                    <Button variant="ghost" size="sm" onClick={() => setSelectedInvoice(invoice)}>
                      Details
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
      <Modal open={showDatevExport} onClose={() => setShowDatevExport(false)} title="DATEV Export">
        <DatevExportForm onClose={() => setShowDatevExport(false)} />
      </Modal>

      {/* Invoice Detail Modal */}
      <Modal
        open={!!selectedInvoice && !showPaymentModal}
        onClose={() => setSelectedInvoice(null)}
        title={`Rechnung ${selectedInvoice?.invoice_number}`}
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
    buchungskonto: '',
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
        buchungskonto: formData.buchungskonto || undefined,
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
        label="Buchungskonto"
        placeholder="Standard (z.B. 8400)..."
        value={formData.buchungskonto}
        onChange={(e) => setFormData({ ...formData, buchungskonto: e.target.value })}
      />

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
    { value: 'KARTE', label: 'Karte' },
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
  const [formData, setFormData] = useState({
    from_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
    to_date: new Date().toISOString().split('T')[0],
    include_payments: true,
  });

  const handleExport = async () => {
    setLoading(true);
    try {
      const result = await invoicesApi.exportDatev(formData);
      toast.success(`Export erfolgreich: ${result.record_count} Datensätze`);

      // Download CSV
      const blob = new Blob([result.csv_content], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `DATEV_Export_${formData.from_date}_${formData.to_date}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);

      onClose();
    } catch (error) {
      toast.error('Fehler beim Export');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
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

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onClose}>
          Abbrechen
        </Button>
        <Button onClick={handleExport} loading={loading} fullWidth icon={<Download className="w-4 h-4" />}>
          Exportieren
        </Button>
      </div>
    </div>
  );
}

// Invoice Detail
function InvoiceDetail({ invoice: initial }: { invoice: Invoice }) {
  const queryClient = useQueryClient();
  const toast = useToast();

  // Refetch invoice details after every mutation so the lines list stays in sync.
  const { data: refreshed } = useQuery({
    queryKey: ['invoice', initial.id],
    queryFn: () => invoicesApi.get(initial.id),
    initialData: initial,
  });
  const invoice = refreshed || initial;
  const isDraft = invoice.status === 'ENTWURF';

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
  });
  const [headerDirty, setHeaderDirty] = useState(false);
  // Sync edit-state when invoice changes
  if (!headerDirty && (headerEdit.customer_id !== invoice.customer_id ||
      headerEdit.invoice_date !== invoice.invoice_date.slice(0, 10) ||
      headerEdit.due_date !== (invoice.due_date ? invoice.due_date.slice(0, 10) : ''))) {
    setHeaderEdit({
      customer_id: invoice.customer_id,
      invoice_date: invoice.invoice_date.slice(0, 10),
      due_date: invoice.due_date ? invoice.due_date.slice(0, 10) : '',
    });
  }
  const saveHeaderMutation = useMutation({
    mutationFn: () => invoicesApi.update(invoice.id, {
      customer_id: headerEdit.customer_id,
      invoice_date: headerEdit.invoice_date,
      due_date: headerEdit.due_date || undefined,
    } as any),
    onSuccess: () => {
      setHeaderDirty(false);
      queryClient.invalidateQueries({ queryKey: ['invoice', invoice.id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Kopfdaten gespeichert');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Speichern fehlgeschlagen'),
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
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Hinzufügen'),
  });

  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => invoicesApi.deleteLine(invoice.id, lineId),
    onSuccess: () => {
      invalidate();
      toast.success('Position entfernt');
    },
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
            <p className="font-medium">{invoice.customer_name}</p>
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
                {isDraft && <th className="w-8"></th>}
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line) => (
                <tr key={line.id} className="border-b">
                  <td className="py-2">{line.description}</td>
                  <td className="text-right py-2">
                    {line.quantity} {line.unit}
                  </td>
                  <td className="text-right py-2">{line.unit_price.toFixed(2)} €</td>
                  <td className="text-right py-2">{line.line_total.toFixed(2)} €</td>
                  {isDraft && (
                    <td className="text-right py-2">
                      <button
                        type="button"
                        title="Position entfernen"
                        onClick={() => deleteLineMutation.mutate(line.id)}
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
          <p className="text-gray-500 dark:text-gray-400 text-sm">Keine Positionen</p>
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
          <span>{invoice.subtotal.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">MwSt:</span>
          <span>{invoice.tax_amount.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between font-semibold mt-2 pt-2 border-t">
          <span>Gesamt:</span>
          <span>{invoice.total.toFixed(2)} €</span>
        </div>
        {invoice.paid_amount > 0 && (
          <div className="flex justify-between text-sm text-green-600 dark:text-green-400 mt-1">
            <span>Bezahlt:</span>
            <span>{invoice.paid_amount.toFixed(2)} €</span>
          </div>
        )}
      </div>
    </div>
  );
}
