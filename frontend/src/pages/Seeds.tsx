import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { seedsApi } from '../services/api';
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
  Textarea,
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
      seedsApi.getSeeds({
        aktiv: filterAktiv === 'all' ? undefined : filterAktiv === 'true',
      }),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => seedsApi.deleteSeed(id),
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
            prefix={<Search className="w-4 h-4" />}
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
    keimdauer_tage: seed?.keimdauer_tage || 2,
    wachstumsdauer_tage: seed?.wachstumsdauer_tage || 8,
    erntefenster_min_tage: seed?.erntefenster_min_tage || 8,
    erntefenster_optimal_tage: seed?.erntefenster_optimal_tage || 10,
    erntefenster_max_tage: seed?.erntefenster_max_tage || 14,
    ertrag_gramm_pro_tray: seed?.ertrag_gramm_pro_tray || 350,
    verlustquote_prozent: seed?.verlustquote_prozent || 5,
    aktiv: seed?.aktiv ?? true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (seed) {
        await seedsApi.updateSeed(seed.id, formData);
      } else {
        await seedsApi.createSeed(formData);
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
        label="Lieferant"
        value={formData.lieferant}
        onChange={(e) => setFormData({ ...formData, lieferant: e.target.value })}
        placeholder="z.B. Bio-Saatgut München GmbH"
      />

      <div className="divider" />

      <h4 className="font-medium text-gray-900">Wachstumsparameter</h4>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Input
          label="Keimdauer"
          type="number"
          required
          min={1}
          value={formData.keimdauer_tage}
          onChange={(e) => setFormData({ ...formData, keimdauer_tage: Number(e.target.value) })}
          suffix="Tage"
        />
        <Input
          label="Wachstumsdauer"
          type="number"
          required
          min={1}
          value={formData.wachstumsdauer_tage}
          onChange={(e) => setFormData({ ...formData, wachstumsdauer_tage: Number(e.target.value) })}
          suffix="Tage"
        />
        <Input
          label="Ertrag/Tray"
          type="number"
          required
          min={1}
          value={formData.ertrag_gramm_pro_tray}
          onChange={(e) => setFormData({ ...formData, ertrag_gramm_pro_tray: Number(e.target.value) })}
          suffix="g"
        />
        <Input
          label="Verlustquote"
          type="number"
          required
          min={0}
          max={100}
          value={formData.verlustquote_prozent}
          onChange={(e) => setFormData({ ...formData, verlustquote_prozent: Number(e.target.value) })}
          suffix="%"
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
          suffix="Tage"
        />
        <Input
          label="Erntefenster Optimal"
          type="number"
          required
          min={1}
          value={formData.erntefenster_optimal_tage}
          onChange={(e) => setFormData({ ...formData, erntefenster_optimal_tage: Number(e.target.value) })}
          suffix="Tage"
        />
        <Input
          label="Erntefenster Max"
          type="number"
          required
          min={1}
          value={formData.erntefenster_max_tage}
          onChange={(e) => setFormData({ ...formData, erntefenster_max_tage: Number(e.target.value) })}
          suffix="Tage"
        />
      </div>

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
          {seed ? 'Speichern' : 'Erstellen'}
        </Button>
      </div>
    </form>
  );
}
