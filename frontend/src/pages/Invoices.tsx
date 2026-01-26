import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, FileText, Download, Euro, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { invoicesApi, salesApi } from '../services/api';
import { Invoice, InvoiceStatus, InvoiceType, Customer, Payment } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  useToast,
  Badge,
  SelectOption,
  Tabs,
  DatePicker,
} from '../components/ui';

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  ENTWURF: 'Entwurf',
  OFFEN: 'Offen',
  TEILBEZAHLT: 'Teilbezahlt',
  BEZAHLT: 'Bezahlt',
  UEBERFAELLIG: 'Überfällig',
  STORNIERT: 'Storniert',
};

const STATUS_COLORS: Record<InvoiceStatus, 'gray' | 'blue' | 'yellow' | 'green' | 'red' | 'purple'> = {
  ENTWURF: 'gray',
  OFFEN: 'blue',
  TEILBEZAHLT: 'yellow',
  BEZAHLT: 'green',
  UEBERFAELLIG: 'red',
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

  // Fetch invoices
  const { data: invoices = [], isLoading } = useQuery({
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
    return <PageLoader />;
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
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Offene Forderungen</p>
              <p className="text-xl font-semibold">{totalOpen.toFixed(2)} €</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 rounded-lg">
              <AlertCircle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Überfällig</p>
              <p className="text-xl font-semibold">{overdueInvoices.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <Clock className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Entwürfe</p>
              <p className="text-xl font-semibold">{invoices.filter((i) => i.status === 'ENTWURF').length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Bezahlt (Monat)</p>
              <p className="text-xl font-semibold">{invoices.filter((i) => i.status === 'BEZAHLT').length}</p>
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
            prefix={<Search className="w-4 h-4" />}
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
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nummer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Kunde</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Datum</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fällig</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Betrag</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {displayInvoices.map((invoice) => (
                <tr key={invoice.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{invoice.invoice_number}</div>
                    <div className="text-xs text-gray-500">{TYPE_LABELS[invoice.invoice_type]}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {invoice.customer_name || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(invoice.invoice_date).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(invoice.due_date).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{invoice.total.toFixed(2)} €</div>
                    {invoice.paid_amount > 0 && invoice.paid_amount < invoice.total && (
                      <div className="text-xs text-gray-500">Bezahlt: {invoice.paid_amount.toFixed(2)} €</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge color={STATUS_COLORS[invoice.status]}>{STATUS_LABELS[invoice.status]}</Badge>
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
      <div className="bg-gray-50 p-4 rounded-lg">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Rechnungsbetrag:</span>
          <span className="font-medium">{invoice.total.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Bereits bezahlt:</span>
          <span className="font-medium">{invoice.paid_amount.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm font-semibold mt-2 pt-2 border-t">
          <span>Offen:</span>
          <span className="text-red-600">{openAmount.toFixed(2)} €</span>
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
          suffix="€"
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
          className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700">Zahlungen einschließen</span>
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
function InvoiceDetail({ invoice }: { invoice: Invoice }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm text-gray-500">Kunde</p>
          <p className="font-medium">{invoice.customer_name}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Status</p>
          <Badge color={STATUS_COLORS[invoice.status]}>{STATUS_LABELS[invoice.status]}</Badge>
        </div>
        <div>
          <p className="text-sm text-gray-500">Rechnungsdatum</p>
          <p className="font-medium">{new Date(invoice.invoice_date).toLocaleDateString('de-DE')}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Fällig am</p>
          <p className="font-medium">{new Date(invoice.due_date).toLocaleDateString('de-DE')}</p>
        </div>
      </div>

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
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-500 text-sm">Keine Positionen</p>
        )}
      </div>

      <div className="border-t pt-4">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Zwischensumme:</span>
          <span>{invoice.subtotal.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">MwSt:</span>
          <span>{invoice.tax_amount.toFixed(2)} €</span>
        </div>
        <div className="flex justify-between font-semibold mt-2 pt-2 border-t">
          <span>Gesamt:</span>
          <span>{invoice.total.toFixed(2)} €</span>
        </div>
        {invoice.paid_amount > 0 && (
          <div className="flex justify-between text-sm text-green-600 mt-1">
            <span>Bezahlt:</span>
            <span>{invoice.paid_amount.toFixed(2)} €</span>
          </div>
        )}
      </div>
    </div>
  );
}
