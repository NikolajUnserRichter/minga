import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Trash2 } from 'lucide-react';
import { seedsApi, suppliersApi } from '../services/api';
import { Seed } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { SeedCard } from '../components/domain/SeedCard';
import { ExcelImport } from '../components/common/ExcelImport';
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
import { getErrorMessage } from '../services/errors';

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
          <div className="flex gap-2 items-center">
            <ExcelImport entity="seeds" onImported={() => queryClient.invalidateQueries({ queryKey: ['seeds'] })} />
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
              Neue Sorte
            </Button>
          </div>
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
          alleSorten={seeds}
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
  /** Für das Mischrezept: aus diesen Sorten wird eine Mischung zusammengesetzt. */
  alleSorten: Seed[];
  onSubmit: () => void;
  onCancel: () => void;
}

function SeedForm({ seed, alleSorten, onSubmit, onCancel }: SeedFormProps) {
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
    substrat: seed?.substrat || '',
    winter_extra_tage: seed?.winter_extra_tage ?? 0,
    // Winter-Parametersatz: null = Sommerwert gilt weiter
    winter_keimdauer_tage: seed?.winter_keimdauer_tage ?? null as number | null,
    winter_wachstumsdauer_tage: seed?.winter_wachstumsdauer_tage ?? null as number | null,
    winter_erntefenster_min_tage: seed?.winter_erntefenster_min_tage ?? null as number | null,
    winter_erntefenster_optimal_tage: seed?.winter_erntefenster_optimal_tage ?? null as number | null,
    winter_erntefenster_max_tage: seed?.winter_erntefenster_max_tage ?? null as number | null,
    aktiv: seed?.aktiv ?? true,
    is_mix: seed?.is_mix ?? false,
  });

  // Rezept einer Mischsorte: Sorte + Menge je Kiste. Wird getrennt vom
  // Stammsatz gehalten, weil die Zeilen einzeln hinzukommen und wegfallen.
  const [rezept, setRezept] = useState<Array<{ seed_id: string; gramm_pro_tray: number }>>(
    (seed?.mix_components ?? []).map((k) => ({
      seed_id: k.seed_id,
      gramm_pro_tray: Number(k.gramm_pro_tray),
    }))
  );

  const processOptions: SelectOption[] = [
    { value: 'STANDARD', label: 'Standard (Erde/Substrat)' },
    { value: 'PLATTE', label: 'Platte' },
    { value: 'PLATTE_STEINE', label: 'Platte und Steine' },
  ];

  // Eine Mischung aus Mischungen wäre nicht auflösbar — nur echte Sorten.
  const komponentenOptions: SelectOption[] = alleSorten
    .filter((s) => !s.is_mix && s.id !== seed?.id)
    .map((s) => ({ value: s.id, label: `${s.name}${s.sorte ? ` - ${s.sorte}` : ''}` }));

  const rezeptSumme = rezept.reduce((summe, z) => summe + (Number(z.gramm_pro_tray) || 0), 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const zeilen = rezept.filter((z) => z.seed_id && z.gramm_pro_tray > 0);
    if (formData.is_mix && zeilen.length === 0) {
      toast.error('Eine Mischung braucht mindestens eine Ausgangssorte mit Menge.');
      return;
    }

    setLoading(true);
    try {
      const payload = { ...formData, mix_components: formData.is_mix ? zeilen : [] };
      if (seed) {
        await seedsApi.update(seed.id, payload);
      } else {
        await seedsApi.create(payload);
      }
      onSubmit();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Fehler beim Speichern'));
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

      {/* Mischsorte (z.B. Brotzeitmix): kein Wareneingang, sondern ein Rezept.
          Gemischt wird bei jeder Aussaat aus dem Bestand der Ausgangssorten. */}
      <div className="border rounded-lg p-3 dark:border-gray-700 bg-gray-50/40 dark:bg-gray-800/40 space-y-3">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={formData.is_mix}
            onChange={(e) => setFormData({ ...formData, is_mix: e.target.checked })}
            className="rounded"
          />
          Mischung aus mehreren Sorten (z.B. Brotzeitmix)
        </label>

        {formData.is_mix && (
          <div className="space-y-2">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Die Mischung wird nicht eingekauft: Bei der Aussaat zieht das System
              die Mengen von den Ausgangssorten ab und hält fest, welche Chargen
              darin stecken.
            </p>

            {rezept.map((zeile, index) => (
              <div key={index} className="flex gap-2 items-end">
                <div className="flex-1">
                  <Select
                    options={komponentenOptions}
                    value={zeile.seed_id}
                    onChange={(e) => setRezept(rezept.map((z, i) =>
                      i === index ? { ...z, seed_id: e.target.value } : z))}
                    placeholder="Sorte wählen..."
                  />
                </div>
                <div className="w-40">
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    value={zeile.gramm_pro_tray || ''}
                    onChange={(e) => setRezept(rezept.map((z, i) =>
                      i === index ? { ...z, gramm_pro_tray: Number(e.target.value) } : z))}
                    endIcon="g/Kiste"
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setRezept(rezept.filter((_, i) => i !== index))}
                  aria-label="Zeile entfernen"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}

            <div className="flex items-center justify-between">
              <Button
                type="button"
                variant="secondary"
                icon={<Plus className="w-4 h-4" />}
                onClick={() => setRezept([...rezept, { seed_id: '', gramm_pro_tray: 0 }])}
              >
                Sorte hinzufügen
              </Button>
              <span className="text-sm text-gray-600 dark:text-gray-300">
                Summe: <b>{rezeptSumme} g</b> je Kiste
              </span>
            </div>
          </div>
        )}
      </div>

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

      <Input
        label="Substrat"
        value={formData.substrat}
        onChange={(e) => setFormData({ ...formData, substrat: e.target.value })}
        placeholder="z.B. Hanfmatte, Erde"
        hint="Wird in der Aussaat-Arbeitsanweisung angezeigt"
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

      <div className="divider" />

      <div>
        <h4 className="font-medium text-gray-900 dark:text-white">Winterzyklus</h4>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Eigener Parametersatz für den Winterbetrieb (Einstellungen → Saisonzyklus = WINTER).
          Die Verzögerung kann in der Keimung oder im Growroom entstehen — deshalb beides
          getrennt pflegen. Leere Felder übernehmen den Sommerwert.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Input
          label="Keimdauer Winter"
          type="number"
          min={1}
          value={formData.winter_keimdauer_tage ?? ''}
          onChange={(e) => setFormData({ ...formData, winter_keimdauer_tage: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
        <Input
          label="Wachstum Winter"
          type="number"
          min={1}
          value={formData.winter_wachstumsdauer_tage ?? ''}
          onChange={(e) => setFormData({ ...formData, winter_wachstumsdauer_tage: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
        <Input
          label="Erntefenster Min"
          type="number"
          min={1}
          value={formData.winter_erntefenster_min_tage ?? ''}
          onChange={(e) => setFormData({ ...formData, winter_erntefenster_min_tage: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
        <Input
          label="Erntefenster Optimal"
          type="number"
          min={1}
          value={formData.winter_erntefenster_optimal_tage ?? ''}
          onChange={(e) => setFormData({ ...formData, winter_erntefenster_optimal_tage: e.target.value ? Number(e.target.value) : null })}
          endIcon="Tage"
        />
        <Input
          label="Erntefenster Max"
          type="number"
          min={1}
          value={formData.winter_erntefenster_max_tage ?? ''}
          onChange={(e) => setFormData({ ...formData, winter_erntefenster_max_tage: e.target.value ? Number(e.target.value) : null })}
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
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler')),
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
