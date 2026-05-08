import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { salesApi } from '../services/api';
import { Customer, CustomerType } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { CustomerCard } from '../components/domain/CustomerCard';
import { CreateOrderModal } from '../components/domain/CreateOrderModal';
import {
  Button,
  Input,
  Select,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  useToast,
  MultiSelect,
  SelectOption,
} from '../components/ui';

const typeOptions: SelectOption[] = [
  { value: 'all', label: 'Alle Typen' },
  { value: 'GASTRO', label: 'Gastronomie' },
  { value: 'HANDEL', label: 'Handel' },
  { value: 'PRIVAT', label: 'Privat' },
];

const weekdayOptions: SelectOption[] = [
  { value: '0', label: 'Montag' },
  { value: '1', label: 'Dienstag' },
  { value: '2', label: 'Mittwoch' },
  { value: '3', label: 'Donnerstag' },
  { value: '4', label: 'Freitag' },
  { value: '5', label: 'Samstag' },
  { value: '6', label: 'Sonntag' },
];

export default function Customers() {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [deletingCustomer, setDeletingCustomer] = useState<Customer | null>(null);
  const [orderForCustomer, setOrderForCustomer] = useState<Customer | null>(null);

  // Fetch customers
  const { data: customersData, isLoading } = useQuery({
    queryKey: ['customers', { typ: typeFilter }],
    queryFn: () =>
      salesApi.listCustomers({
        typ: typeFilter === 'all' ? undefined : (typeFilter as CustomerType),
      }),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => salesApi.deleteCustomer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      toast.success('Kunde gelöscht');
      setDeletingCustomer(null);
    },
    onError: () => {
      toast.error('Fehler beim Löschen');
    },
  });

  const customers = customersData?.items || [];
  const filteredCustomers = customers.filter(
    (customer) =>
      customer.name.toLowerCase().includes(search.toLowerCase()) ||
      customer.email?.toLowerCase().includes(search.toLowerCase())
  );

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Kundenverwaltung"
        subtitle={`${customers.length} Kunden`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
            Neuer Kunde
          </Button>
        }
      />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen nach Name oder E-Mail..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        <Select
          options={typeOptions}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        />
      </FilterBar>

      {filteredCustomers.length === 0 ? (
        <EmptyState
          title="Keine Kunden gefunden"
          description={search ? 'Versuche eine andere Suche.' : 'Erstelle deinen ersten Kunden.'}
          action={
            !search && (
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                Ersten Kunden anlegen
              </Button>
            )
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCustomers.map((customer) => (
            <CustomerCard
              key={customer.id}
              customer={customer}
              onEdit={() => setEditingCustomer(customer)}
              onCreateOrder={() => setOrderForCustomer(customer)}
              onManageSubscriptions={() => navigate('/subscriptions')}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={isCreating || !!editingCustomer}
        onClose={() => {
          setIsCreating(false);
          setEditingCustomer(null);
        }}
        title={editingCustomer ? 'Kunde bearbeiten' : 'Neuer Kunde'}
        size="lg"
      >
        <CustomerForm
          customer={editingCustomer}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['customers'] });
            setIsCreating(false);
            setEditingCustomer(null);
            toast.success(editingCustomer ? 'Kunde aktualisiert' : 'Kunde erstellt');
          }}
          onCancel={() => {
            setIsCreating(false);
            setEditingCustomer(null);
          }}
        />
      </Modal>

      {/* Create Order Modal */}
      <CreateOrderModal
        open={!!orderForCustomer}
        onClose={() => setOrderForCustomer(null)}
        preselectedCustomer={orderForCustomer}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deletingCustomer}
        onClose={() => setDeletingCustomer(null)}
        onConfirm={() => deletingCustomer && deleteMutation.mutate(deletingCustomer.id)}
        title="Kunde löschen?"
        message={`Möchtest du "${deletingCustomer?.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`}
        confirmLabel="Löschen"
        variant="danger"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// Customer Form Component
interface CustomerFormProps {
  customer: Customer | null;
  onSubmit: () => void;
  onCancel: () => void;
}

function CustomerForm({ customer, onSubmit, onCancel }: CustomerFormProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: customer?.name || '',
    typ: customer?.typ || ('GASTRO' as CustomerType),
    email: customer?.email || '',
    email_purchasing: customer?.email_purchasing || '',
    email_sales: customer?.email_sales || '',
    email_billing: customer?.email_billing || '',
    telefon: customer?.telefon || '',
    adresse: customer?.adresse || '',
    ansprechpartner_name: customer?.ansprechpartner_name || '',
    ansprechpartner_email: customer?.ansprechpartner_email || '',
    ansprechpartner_telefon: customer?.ansprechpartner_telefon || '',
    ust_id: customer?.ust_id || '',
    liefertage: customer?.liefertage?.map(String) || [],
    aktiv: customer?.aktiv ?? true,
  });

  const customerTypeOptions: SelectOption[] = [
    { value: 'GASTRO', label: 'Gastronomie' },
    { value: 'HANDEL', label: 'Handel' },
    { value: 'GEWERBE', label: 'Gewerbe' },
    { value: 'PRIVAT', label: 'Privat' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        liefertage: formData.liefertage.map(Number),
      };

      if (customer) {
        await salesApi.updateCustomer(customer.id, payload);
      } else {
        await salesApi.createCustomer(payload);
      }
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="Name"
          required
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="z.B. Restaurant Schumann"
        />
        <Select
          label="Kundentyp"
          required
          options={customerTypeOptions}
          value={formData.typ}
          onChange={(e) => setFormData({ ...formData, typ: e.target.value as CustomerType })}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="E-Mail (Hauptkontakt)"
          type="email"
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          placeholder="info@restaurant.de"
        />
        <Input
          label="Telefon"
          value={formData.telefon}
          onChange={(e) => setFormData({ ...formData, telefon: e.target.value })}
          placeholder="+49 89 123456"
        />
      </div>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">Abteilungs-E-Mails (optional)</legend>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="Einkauf"
            type="email"
            value={formData.email_purchasing}
            onChange={(e) => setFormData({ ...formData, email_purchasing: e.target.value })}
            placeholder="einkauf@..."
          />
          <Input
            label="Vertrieb"
            type="email"
            value={formData.email_sales}
            onChange={(e) => setFormData({ ...formData, email_sales: e.target.value })}
            placeholder="vertrieb@..."
          />
          <Input
            label="Rechnung"
            type="email"
            value={formData.email_billing}
            onChange={(e) => setFormData({ ...formData, email_billing: e.target.value })}
            placeholder="buchhaltung@..."
          />
        </div>
      </fieldset>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">Ansprechpartner</legend>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="Name"
            value={formData.ansprechpartner_name}
            onChange={(e) => setFormData({ ...formData, ansprechpartner_name: e.target.value })}
            placeholder="Max Mustermann"
          />
          <Input
            label="E-Mail"
            type="email"
            value={formData.ansprechpartner_email}
            onChange={(e) => setFormData({ ...formData, ansprechpartner_email: e.target.value })}
            placeholder="max@..."
          />
          <Input
            label="Telefon"
            value={formData.ansprechpartner_telefon}
            onChange={(e) => setFormData({ ...formData, ansprechpartner_telefon: e.target.value })}
            placeholder="+49 ..."
          />
        </div>
      </fieldset>

      <Input
        label="Adresse"
        value={formData.adresse}
        onChange={(e) => setFormData({ ...formData, adresse: e.target.value })}
        placeholder="Straße, PLZ Ort"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="USt-IdNr."
          value={formData.ust_id}
          onChange={(e) => setFormData({ ...formData, ust_id: e.target.value })}
          placeholder="DE123456789"
        />
        <MultiSelect
          label="Standard-Liefertage"
          options={weekdayOptions}
          value={formData.liefertage}
          onChange={(value) => setFormData({ ...formData, liefertage: value })}
        />
      </div>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={formData.aktiv}
          onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700 dark:text-gray-300">Aktiv</span>
      </label>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          {customer ? 'Speichern' : 'Erstellen'}
        </Button>
      </div>
    </form>
  );
}
