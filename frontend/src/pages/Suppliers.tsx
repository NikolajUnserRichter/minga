import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash, Edit2 } from 'lucide-react';
import { suppliersApi } from '../services/api';
import { Supplier } from '../types';
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

export default function Suppliers() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Supplier | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['suppliers', 'all'],
    queryFn: () => suppliersApi.list({ is_active: true }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success('Lieferant deaktiviert');
      setDeleting(null);
    },
    onError: () => toast.error('Fehler beim Deaktivieren'),
  });

  if (isLoading) return <PageLoader />;

  const suppliers = data?.items || [];

  return (
    <div>
      <PageHeader
        title="Lieferanten"
        subtitle={`${suppliers.length} aktive Lieferanten`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
            Neuer Lieferant
          </Button>
        }
      />

      {suppliers.length === 0 ? (
        <EmptyState
          title="Keine Lieferanten"
          description="Lege deinen ersten Lieferanten an. Lieferanten werden für Saatgut-Stammdaten verwendet (Standard- und Backup-Lieferant pro Sorte)."
          action={
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
              Lieferant anlegen
            </Button>
          }
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">E-Mail</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Telefon</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">USt-IdNr.</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {suppliers.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{s.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{s.email || '–'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{s.telefon || '–'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{s.ust_id || '–'}</td>
                  <td className="px-6 py-4">
                    <Badge variant={s.is_active ? 'success' : 'gray'}>{s.is_active ? 'Aktiv' : 'Inaktiv'}</Badge>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Button variant="ghost" size="sm" icon={<Edit2 className="w-4 h-4" />} onClick={() => setEditing(s)} />
                    <Button variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => setDeleting(s)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={creating || !!editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        title={editing ? 'Lieferant bearbeiten' : 'Neuer Lieferant'}
      >
        <SupplierForm
          supplier={editing}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['suppliers'] });
            setCreating(false);
            setEditing(null);
            toast.success(editing ? 'Lieferant gespeichert' : 'Lieferant angelegt');
          }}
          onCancel={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        title="Lieferant deaktivieren?"
        message={`"${deleting?.name}" wird auf inaktiv gesetzt.`}
        confirmLabel="Deaktivieren"
        variant="danger"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

function SupplierForm({
  supplier,
  onSubmit,
  onCancel,
}: {
  supplier: Supplier | null;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({
    name: supplier?.name || '',
    email: supplier?.email || '',
    telefon: supplier?.telefon || '',
    adresse: supplier?.adresse || '',
    ust_id: supplier?.ust_id || '',
    notizen: supplier?.notizen || '',
    product_group: supplier?.product_group || '',
    is_organic: supplier?.is_organic ?? false,
    bio_certificate_url: supplier?.bio_certificate_url || '',
    bio_certificate_valid_until: supplier?.bio_certificate_valid_until || '',
    bio_kontrollstelle: supplier?.bio_kontrollstelle || '',
  });

  const productGroupOptions: SelectOption[] = [
    { value: '', label: '— keine —' },
    { value: 'SAATGUT', label: 'Saatgut' },
    { value: 'SUBSTRAT', label: 'Substrat (Erde, Hanfmatten, Wolle)' },
    { value: 'VERPACKUNG', label: 'Verpackung' },
    { value: 'ARBEITSMATERIAL', label: 'Arbeitsmaterial' },
    { value: 'SONSTIGES', label: 'Sonstiges' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload: any = {
        ...data,
        // empty string -> null for nullable fields
        email: data.email || null,
        telefon: data.telefon || null,
        adresse: data.adresse || null,
        ust_id: data.ust_id || null,
        notizen: data.notizen || null,
        product_group: data.product_group || null,
        bio_certificate_url: data.bio_certificate_url || null,
        bio_certificate_valid_until: data.bio_certificate_valid_until || null,
        bio_kontrollstelle: data.bio_kontrollstelle || null,
      };
      if (supplier) {
        await suppliersApi.update(supplier.id, payload);
      } else {
        await suppliersApi.create(payload);
      }
      onSubmit();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Name"
        required
        value={data.name}
        onChange={(e) => setData({ ...data, name: e.target.value })}
        placeholder="z.B. Bio-Saatgut München GmbH"
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="E-Mail"
          type="email"
          value={data.email}
          onChange={(e) => setData({ ...data, email: e.target.value })}
        />
        <Input
          label="Telefon"
          value={data.telefon}
          onChange={(e) => setData({ ...data, telefon: e.target.value })}
        />
      </div>
      <Input
        label="Adresse"
        value={data.adresse}
        onChange={(e) => setData({ ...data, adresse: e.target.value })}
        placeholder="Straße, PLZ Ort"
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="USt-IdNr."
          value={data.ust_id}
          onChange={(e) => setData({ ...data, ust_id: e.target.value })}
          placeholder="DE123456789"
        />
        <Select
          label="Produktgruppe"
          options={productGroupOptions}
          value={data.product_group}
          onChange={(e) => setData({ ...data, product_group: e.target.value as any })}
        />
      </div>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">BIO-Daten</legend>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={data.is_organic}
            onChange={(e) => setData({ ...data, is_organic: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">BIO-zertifiziert</span>
        </label>
        {data.is_organic && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Kontrollstelle"
                value={data.bio_kontrollstelle}
                onChange={(e) => setData({ ...data, bio_kontrollstelle: e.target.value })}
                placeholder="z.B. DE-ÖKO-006"
              />
              <Input
                label="Zertifikat gültig bis"
                type="date"
                value={data.bio_certificate_valid_until}
                onChange={(e) => setData({ ...data, bio_certificate_valid_until: e.target.value })}
              />
            </div>
            <Input
              label="Zertifikat-URL (Upload folgt später)"
              type="url"
              value={data.bio_certificate_url}
              onChange={(e) => setData({ ...data, bio_certificate_url: e.target.value })}
              placeholder="https://..."
            />
          </>
        )}
      </fieldset>

      <Input
        label="Notizen"
        value={data.notizen}
        onChange={(e) => setData({ ...data, notizen: e.target.value })}
      />

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          {supplier ? 'Speichern' : 'Anlegen'}
        </Button>
      </div>
    </form>
  );
}
