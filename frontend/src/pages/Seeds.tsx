import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { seedsApi, suppliersApi } from '../services/api';
import { Seed } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { SeedCard } from '../components/domain/SeedCard';
import {
  Button,
  Input,
  Select,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  useToast,
  SelectOption,
} from '../components/ui';

export default function Seeds() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [filterAktiv, setFilterAktiv] = useState<string>('all');
  const [editingSeed, setEditingSeed] = useState<Seed | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [deletingSeed, setDeletingSeed] = useState<Seed | null>(null);

  // Fetch seeds
  const { data: seedsData, isLoading } = useQuery({
    queryKey: ['seeds', { aktiv: filterAktiv }],
    queryFn: () =>
      seedsApi.list({
        aktiv: filterAktiv === 'all' ? undefined : filterAktiv === 'true',
      }),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => seedsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['seeds'] });
      toast.success('Saatgut gelöscht');
      setDeletingSeed(null);
    },
    onError: () => {
      toast.error('Fehler beim Löschen');
    },
  });

  const seeds = seedsData?.items || [];
  const filteredSeeds = seeds.filter(
    (seed) =>
      seed.name.toLowerCase().includes(search.toLowerCase()) ||
      seed.sorte?.toLowerCase().includes(search.toLowerCase())
  );

  const filterOptions: SelectOption[] = [
    { value: 'all', label: 'Alle' },
    { value: 'true', label: 'Nur aktive' },
    { value: 'false', label: 'Nur inaktive' },
  ];

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Saatgutverwaltung"
        subtitle={`${seeds.length} Sorten`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
            Neue Sorte
          </Button>
        }
      />

      <FilterBar>
        <div className="flex-1 max-w-md">
          <Input
            placeholder="Suchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="w-4 h-4" />}
          />
        </div>
        <Select
          options={filterOptions}
          value={filterAktiv}
          onChange={(e) => setFilterAktiv(e.target.value)}
        />
      </FilterBar>

      {filteredSeeds.length === 0 ? (
        <EmptyState
          title="Keine Saatgutsorten gefunden"
          description={search ? 'Versuche eine andere Suche.' : 'Erstelle deine erste Saatgutsorte.'}
          action={
            !search && (
              <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                Erste Sorte anlegen
              </Button>
            )
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSeeds.map((seed) => (
            <SeedCard
              key={seed.id}
              seed={seed}
              onEdit={() => setEditingSeed(seed)}
              onDelete={() => setDeletingSeed(seed)}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={isCreating || !!editingSeed}
        onClose={() => {
          setIsCreating(false);
          setEditingSeed(null);
        }}
        title={editingSeed ? 'Saatgut bearbeiten' : 'Neue Saatgutsorte'}
        size="lg"
      >
        <SeedForm
          seed={editingSeed}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['seeds'] });
            setIsCreating(false);
            setEditingSeed(null);
            toast.success(editingSeed ? 'Saatgut aktualisiert' : 'Saatgut erstellt');
          }}
          onCancel={() => {
            setIsCreating(false);
            setEditingSeed(null);
          }}
        />
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deletingSeed}
        onClose={() => setDeletingSeed(null)}
        onConfirm={() => deletingSeed && deleteMutation.mutate(deletingSeed.id)}
        title="Saatgut löschen?"
        message={`Möchtest du "${deletingSeed?.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`}
        confirmLabel="Löschen"
        variant="danger"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// Seed Form Component
interface SeedFormProps {
  seed: Seed | null;
  onSubmit: () => void;
  onCancel: () => void;
}

function SeedForm({ seed, onSubmit, onCancel }: SeedFormProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    name: seed?.name || '',
    sorte: seed?.sorte || '',
    lieferant: seed?.lieferant || '',
    cooling_days: seed?.cooling_days ?? null as number | null,
    cooling_shelf_life_days: seed?.cooling_shelf_life_days ?? null as number | null,
    process_type: seed?.process_type || 'STANDARD',
    saatgut_pro_einheit_gramm: seed?.saatgut_pro_einheit_gramm ?? null as number | null,
    keimdauer_tage: seed?.keimdauer_tage || 2,
    wachstumsdauer_tage: seed?.wachstumsdauer_tage || 8,
    erntefenster_min_tage: seed?.erntefenster_min_tage || 8,
    erntefenster_optimal_tage: seed?.erntefenster_optimal_tage || 10,
    erntefenster_max_tage: seed?.erntefenster_max_tage || 14,
    ertrag_gramm_pro_tray: seed?.ertrag_gramm_pro_tray || 350,
    verlustquote_prozent: seed?.verlustquote_prozent || 5,
    aktiv: seed?.aktiv ?? true,
  });

  const processOptions: SelectOption[] = [
    { value: 'STANDARD', label: 'Standard (Erde/Substrat)' },
    { value: 'PLATTE', label: 'Platte' },
    { value: 'PLATTE_STEINE', label: 'Platte und Steine' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (seed) {
        await seedsApi.update(seed.id, formData);
      } else {
        await seedsApi.create(formData);
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
          placeholder="z.B. Sonnenblume"
        />
        <Input
          label="Sorte"
          value={formData.sorte}
          onChange={(e) => setFormData({ ...formData, sorte: e.target.value })}
          placeholder="z.B. Black Oil"
        />
      </div>

      <Input
        label="Lieferant (Notiz, falls nicht im System)"
        value={formData.lieferant}
        onChange={(e) => setFormData({ ...formData, lieferant: e.target.value })}
        placeholder="z.B. Bio-Saatgut München GmbH"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Select
          label="Prozess"
          options={processOptions}
          value={formData.process_type}
          onChange={(e) => setFormData({ ...formData, process_type: e.target.value })}
        />
        <Input
          label="Kühlung nach Ernte"
          type="number"
          min={0}
          value={formData.cooling_days ?? ''}
          onChange={(e) => setFormData({ ...formData, cooling_days: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
        <Input
          label="Haltbarkeit in Kühlung"
          type="number"
          min={0}
          value={formData.cooling_shelf_life_days ?? ''}
          onChange={(e) => setFormData({ ...formData, cooling_shelf_life_days: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
      </div>

      {seed && <SeedSupplierList seedId={seed.id} />}

      <div className="divider" />

      <h4 className="font-medium text-gray-900 dark:text-white">Wachstumsparameter</h4>

      <Input
        label="Saatgut pro Anzucht-Einheit (Kiste)"
        type="number"
        step="0.1"
        min={0}
        value={formData.saatgut_pro_einheit_gramm ?? ''}
        onChange={(e) => setFormData({ ...formData, saatgut_pro_einheit_gramm: e.target.value ? Number(e.target.value) : null })}
        endIcon="g"
        hint="Wird beim Aussaat-Formular als Standardmenge vorgeschlagen"
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Input
          label="Keimdauer"
          type="number"
          required
          min={1}
          value={formData.keimdauer_tage}
          onChange={(e) => setFormData({ ...formData, keimdauer_tage: Number(e.target.value) })}
          endIcon="Tage"
        />
        <Input
          label="Wachstumsdauer"
          type="number"
          required
          min={1}
          value={formData.wachstumsdauer_tage}
          onChange={(e) => setFormData({ ...formData, wachstumsdauer_tage: Number(e.target.value) })}
          endIcon="Tage"
        />
        <Input
          label="Ertrag/Tray"
          type="number"
          required
          min={1}
          value={formData.ertrag_gramm_pro_tray}
          onChange={(e) => setFormData({ ...formData, ertrag_gramm_pro_tray: Number(e.target.value) })}
          endIcon="g"
        />
        <Input
          label="Verlustquote"
          type="number"
          required
          min={0}
          max={100}
          value={formData.verlustquote_prozent}
          onChange={(e) => setFormData({ ...formData, verlustquote_prozent: Number(e.target.value) })}
          endIcon="%"
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Input
          label="Erntefenster Min"
          type="number"
          required
          min={1}
          value={formData.erntefenster_min_tage}
          onChange={(e) => setFormData({ ...formData, erntefenster_min_tage: Number(e.target.value) })}
          endIcon="Tage"
        />
        <Input
          label="Erntefenster Optimal"
          type="number"
          required
          min={1}
          value={formData.erntefenster_optimal_tage}
          onChange={(e) => setFormData({ ...formData, erntefenster_optimal_tage: Number(e.target.value) })}
          endIcon="Tage"
        />
        <Input
          label="Erntefenster Max"
          type="number"
          required
          min={1}
          value={formData.erntefenster_max_tage}
          onChange={(e) => setFormData({ ...formData, erntefenster_max_tage: Number(e.target.value) })}
          endIcon="Tage"
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
          {seed ? 'Speichern' : 'Erstellen'}
        </Button>
      </div>
    </form>
  );
}

function SeedSupplierList({ seedId }: { seedId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: links = [] } = useQuery({
    queryKey: ['seed-suppliers', seedId],
    queryFn: () => seedsApi.listSuppliers(seedId),
  });
  const { data: supplierData } = useQuery({
    queryKey: ['suppliers', { is_active: true }],
    queryFn: () => suppliersApi.list({ is_active: true }),
  });
  const allSuppliers = supplierData?.items || [];
  const linkedIds = new Set(links.map((l) => l.supplier_id));
  const availableSuppliers = allSuppliers.filter((s) => !linkedIds.has(s.id));
  const [pickedSupplierId, setPickedSupplierId] = useState('');
  const [pickedAsDefault, setPickedAsDefault] = useState(false);
  const [pickedNotes, setPickedNotes] = useState('');

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['seed-suppliers', seedId] });

  const addMutation = useMutation({
    mutationFn: () =>
      seedsApi.addSupplier(seedId, {
        supplier_id: pickedSupplierId,
        is_default: pickedAsDefault,
        notizen: pickedNotes || undefined,
      }),
    onSuccess: () => {
      invalidate();
      setPickedSupplierId('');
      setPickedAsDefault(false);
      setPickedNotes('');
      toast.success('Lieferant verknüpft');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Fehler'),
  });

  const removeMutation = useMutation({
    mutationFn: (sid: string) => seedsApi.removeSupplier(seedId, sid),
    onSuccess: () => { invalidate(); toast.success('Lieferant entfernt'); },
  });

  const setDefaultMutation = useMutation({
    mutationFn: (sid: string) => seedsApi.setDefaultSupplier(seedId, sid),
    onSuccess: () => { invalidate(); toast.success('Standard-Lieferant gesetzt'); },
  });

  const supplierOptions: SelectOption[] = [
    { value: '', label: 'Lieferant wählen…' },
    ...availableSuppliers.map((s) => ({ value: s.id, label: s.name })),
  ];

  return (
    <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        Lieferanten ({links.length})
      </legend>

      {links.length > 0 && (
        <div className="space-y-2">
          {links.map((l) => (
            <div key={l.supplier_id} className="flex items-center gap-2 text-sm bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2">
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-white">
                  {l.supplier_name} {l.is_default && <span className="text-xs text-minga-600">★ Standard</span>}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {l.supplier_email || '–'}{l.notizen ? ` · ${l.notizen}` : ''}
                </div>
              </div>
              {!l.is_default && (
                <Button type="button" size="sm" variant="ghost" onClick={() => setDefaultMutation.mutate(l.supplier_id)}>
                  Als Standard
                </Button>
              )}
              <Button type="button" size="sm" variant="ghost" onClick={() => removeMutation.mutate(l.supplier_id)}>
                Entfernen
              </Button>
            </div>
          ))}
        </div>
      )}

      {availableSuppliers.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Select
            options={supplierOptions}
            value={pickedSupplierId}
            onChange={(e) => setPickedSupplierId(e.target.value)}
          />
          <Input
            placeholder="Notiz (optional)"
            value={pickedNotes}
            onChange={(e) => setPickedNotes(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 flex-1">
              <input
                type="checkbox"
                checked={pickedAsDefault}
                onChange={(e) => setPickedAsDefault(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              Standard
            </label>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              icon={<Plus className="w-4 h-4" />}
              disabled={!pickedSupplierId}
              onClick={() => addMutation.mutate()}
            >
              Verknüpfen
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Alle aktiven Lieferanten sind verknüpft. <a href="/suppliers" className="text-minga-600 hover:underline">Neuen Lieferanten anlegen →</a>
        </p>
      )}
    </fieldset>
  );
}
