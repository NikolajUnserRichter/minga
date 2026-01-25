import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { salesApi } from '../services/api';
import { Customer, CustomerType } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { CustomerCard } from '../components/domain/CustomerCard';
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
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [deletingCustomer, setDeletingCustomer] = useState<Customer | null>(null);

  // Fetch customers
  const { data: customersData, isLoading } = useQuery({
    queryKey: ['customers', { typ: typeFilter }],
    queryFn: () =>
      salesApi.getCustomers({
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
            prefix={<Search className="w-4 h-4" />}
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
              onCreateOrder={() => toast.info('Bestellung anlegen noch nicht implementiert')}
              onManageSubscriptions={() => toast.info('Abos verwalten noch nicht implementiert')}
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
    telefon: customer?.telefon || '',
    adresse: customer?.adresse || '',
    liefertage: customer?.liefertage?.map(String) || [],
    aktiv: customer?.aktiv ?? true,
  });

  const customerTypeOptions: SelectOption[] = [
    { value: 'GASTRO', label: 'Gastronomie' },
    { value: 'HANDEL', label: 'Handel' },
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
          label="E-Mail"
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

      <Input
        label="Adresse"
        value={formData.adresse}
        onChange={(e) => setFormData({ ...formData, adresse: e.target.value })}
        placeholder="Straße, PLZ Ort"
      />

      <MultiSelect
        label="Liefertage"
        options={weekdayOptions}
        value={formData.liefertage}
        onChange={(value) => setFormData({ ...formData, liefertage: value })}
      />

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={formData.aktiv}
          onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700">Aktiv</span>
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
