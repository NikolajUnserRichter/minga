import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Trash } from 'lucide-react';
import { salesApi } from '../services/api';
import { Customer, CustomerType, Contact, CustomerAddress, AddressType } from '../types';
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
          onSubmit={(saved) => {
            queryClient.invalidateQueries({ queryKey: ['customers'] });
            const wasCreating = isCreating;
            if (wasCreating && saved) {
              // Modal offen lassen und in den Edit-Mode wechseln,
              // damit der User direkt Ansprechpartner hinzufügen kann.
              setIsCreating(false);
              setEditingCustomer(saved);
              toast.success('Kunde erstellt — Ansprechpartner können jetzt hinzugefügt werden');
            } else {
              setIsCreating(false);
              setEditingCustomer(null);
              toast.success('Kunde aktualisiert');
            }
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
  onSubmit: (saved?: Customer) => void;
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

      let saved: Customer;
      if (customer) {
        saved = await salesApi.updateCustomer(customer.id, payload);
      } else {
        saved = await salesApi.createCustomer(payload);
      }
      onSubmit(saved);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Fehler beim Speichern');
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

      {customer ? (
        <>
          <AddressList customerId={customer.id} />
          <ContactList customerId={customer.id} />
        </>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 p-4 text-sm text-gray-500 dark:text-gray-400">
          Adressen (Rechnung/Lieferung) und Ansprechpartner können hinzugefügt werden,
          sobald der Kunde gespeichert ist. Nach Klick auf <span className="font-medium">Erstellen</span> öffnen sich die
          Bereiche automatisch.
        </div>
      )}

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

function AddressList({ customerId }: { customerId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: addresses = [] } = useQuery({
    queryKey: ['customer-addresses', customerId],
    queryFn: () => salesApi.listAddresses(customerId),
  });

  const [newAddr, setNewAddr] = useState<Partial<CustomerAddress>>({
    address_type: 'BOTH',
    name: '',
    strasse: '',
    hausnummer: '',
    plz: '',
    ort: '',
    land: 'DE',
    is_default: false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['customer-addresses', customerId] });

  const addMutation = useMutation({
    mutationFn: () => salesApi.createAddress(customerId, newAddr),
    onSuccess: () => {
      invalidate();
      setNewAddr({ address_type: 'BOTH', name: '', strasse: '', hausnummer: '', plz: '', ort: '', land: 'DE', is_default: false });
      toast.success('Adresse hinzugefügt');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler beim Hinzufügen'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => salesApi.deleteAddress(customerId, id),
    onSuccess: () => { invalidate(); toast.success('Adresse gelöscht'); },
  });

  const typeOptions: SelectOption[] = [
    { value: 'BILLING', label: 'Rechnungsadresse' },
    { value: 'SHIPPING', label: 'Lieferadresse' },
    { value: 'BOTH', label: 'Beides' },
  ];

  const typeLabel = (t: AddressType) =>
    t === 'BILLING' ? 'Rechnung' : t === 'SHIPPING' ? 'Lieferung' : 'Rechnung + Lieferung';

  return (
    <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        Adressen ({addresses.length})
      </legend>

      {addresses.length > 0 && (
        <div className="space-y-2">
          {addresses.map((a) => (
            <div key={a.id} className="flex items-start gap-2 text-sm bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2">
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-white">
                  {typeLabel(a.address_type)} {a.is_default && <span className="text-xs text-minga-600">★ Standard</span>}
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  {a.name && <>{a.name}<br /></>}
                  {a.strasse} {a.hausnummer || ''}<br />
                  {a.plz} {a.ort} {a.land !== 'DE' && `(${a.land})`}
                </div>
              </div>
              <Button type="button" variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => deleteMutation.mutate(a.id)} />
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <Select
          options={typeOptions}
          value={newAddr.address_type || 'BOTH'}
          onChange={(e) => setNewAddr({ ...newAddr, address_type: e.target.value as AddressType })}
        />
        <Input
          placeholder="Abweichender Name (optional)"
          value={newAddr.name || ''}
          onChange={(e) => setNewAddr({ ...newAddr, name: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Input
          placeholder="Straße"
          value={newAddr.strasse || ''}
          onChange={(e) => setNewAddr({ ...newAddr, strasse: e.target.value })}
          className="col-span-2"
        />
        <Input
          placeholder="Hausnr."
          value={newAddr.hausnummer || ''}
          onChange={(e) => setNewAddr({ ...newAddr, hausnummer: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-4 gap-2">
        <Input
          placeholder="PLZ"
          value={newAddr.plz || ''}
          onChange={(e) => setNewAddr({ ...newAddr, plz: e.target.value })}
        />
        <Input
          placeholder="Ort"
          value={newAddr.ort || ''}
          onChange={(e) => setNewAddr({ ...newAddr, ort: e.target.value })}
          className="col-span-2"
        />
        <Input
          placeholder="Land"
          value={newAddr.land || 'DE'}
          onChange={(e) => setNewAddr({ ...newAddr, land: e.target.value })}
        />
      </div>
      <div className="flex justify-between items-center">
        <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
          <input
            type="checkbox"
            checked={newAddr.is_default || false}
            onChange={(e) => setNewAddr({ ...newAddr, is_default: e.target.checked })}
            className="w-4 h-4 rounded"
          />
          Als Standard für diesen Typ
        </label>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          icon={<Plus className="w-4 h-4" />}
          disabled={!newAddr.strasse || !newAddr.plz || !newAddr.ort}
          onClick={() => addMutation.mutate()}
        >
          Hinzufügen
        </Button>
      </div>
    </fieldset>
  );
}

function ContactList({ customerId }: { customerId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: contacts = [] } = useQuery({
    queryKey: ['customer-contacts', customerId],
    queryFn: () => salesApi.listContacts(customerId),
  });

  const [newContact, setNewContact] = useState<Partial<Contact>>({
    name: '',
    email: '',
    telefon: '',
    role: 'ALLGEMEIN',
    is_primary: false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['customer-contacts', customerId] });

  const addMutation = useMutation({
    mutationFn: () => salesApi.createContact(customerId, newContact),
    onSuccess: () => {
      invalidate();
      setNewContact({ name: '', email: '', telefon: '', role: 'ALLGEMEIN', is_primary: false });
      toast.success('Ansprechpartner hinzugefügt');
    },
    onError: () => toast.error('Fehler beim Hinzufügen'),
  });

  const deleteMutation = useMutation({
    mutationFn: (contactId: string) => salesApi.deleteContact(customerId, contactId),
    onSuccess: () => {
      invalidate();
      toast.success('Ansprechpartner gelöscht');
    },
  });

  const roleOptions: SelectOption[] = [
    { value: 'ALLGEMEIN', label: 'Allgemein' },
    { value: 'EINKAUF', label: 'Einkauf' },
    { value: 'VERTRIEB', label: 'Vertrieb' },
    { value: 'BUCHHALTUNG', label: 'Buchhaltung' },
    { value: 'TECHNIK', label: 'Technik' },
  ];

  return (
    <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        Ansprechpartner ({contacts.length})
      </legend>

      {contacts.length > 0 && (
        <div className="space-y-2">
          {contacts.map((c) => (
            <div key={c.id} className="flex items-center gap-2 text-sm bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2">
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-white">
                  {c.name} {c.is_primary && <span className="text-xs text-minga-600">★</span>}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {c.role} · {c.email || '–'} · {c.telefon || '–'}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<Trash className="w-4 h-4" />}
                onClick={() => deleteMutation.mutate(c.id)}
              />
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
        <Input
          placeholder="Name"
          value={newContact.name || ''}
          onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
        />
        <Input
          type="email"
          placeholder="E-Mail"
          value={newContact.email || ''}
          onChange={(e) => setNewContact({ ...newContact, email: e.target.value })}
        />
        <Input
          placeholder="Telefon"
          value={newContact.telefon || ''}
          onChange={(e) => setNewContact({ ...newContact, telefon: e.target.value })}
        />
        <Select
          options={roleOptions}
          value={newContact.role || 'ALLGEMEIN'}
          onChange={(e) => setNewContact({ ...newContact, role: e.target.value as Contact['role'] })}
        />
      </div>
      <div className="flex justify-between items-center">
        <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
          <input
            type="checkbox"
            checked={newContact.is_primary || false}
            onChange={(e) => setNewContact({ ...newContact, is_primary: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
          />
          Hauptansprechpartner
        </label>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          icon={<Plus className="w-4 h-4" />}
          disabled={!newContact.name}
          onClick={() => addMutation.mutate()}
        >
          Hinzufügen
        </Button>
      </div>
    </fieldset>
  );
}
