import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash, Edit2 } from 'lucide-react';
import { capacityApi } from '../services/api';
import { Capacity, ResourceType } from '../types';
import { PageHeader } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  Badge,
  useToast,
  SelectOption,
} from '../components/ui';

const TYPE_LABELS: Record<ResourceType, string> = {
  REGAL: 'Regal',
  TRAY: 'Anzucht-Kiste',
  ARBEITSZEIT: 'Arbeitszeit',
};

export default function Capacities() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Capacity | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Capacity | null>(null);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['capacity'],
    queryFn: () => capacityApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => capacityApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
      toast.success('Kapazität gelöscht');
      setDeleting(null);
    },
  });

  if (isLoading) return <PageLoader />;

  return (
    <div>
      <PageHeader
        title="Kapazitäten"
        subtitle={`${items.length} Ressourcen — Regale, Anzucht-Kisten, Arbeitszeit`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
            Neue Kapazität
          </Button>
        }
      />

      {items.length === 0 ? (
        <EmptyState
          title="Keine Kapazitäten gepflegt"
          description="Lege deine Regale, Anzucht-Kisten und Arbeitsstunden an. Diese Werte werden im Aussaat-Formular für die Position-Auswahl verwendet."
          action={
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
              Erste Kapazität anlegen
            </Button>
          }
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Typ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Max</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Belegt</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Frei</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Auslastung</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <Badge variant="info">{TYPE_LABELS[c.ressource_typ]}</Badge>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{c.name || '–'}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">{c.max_kapazitaet}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{c.aktuell_belegt}</td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{c.verfuegbar}</td>
                  <td className="px-6 py-4">
                    <Badge variant={c.ist_ueberlastet ? 'danger' : c.auslastung_prozent > 80 ? 'warning' : 'success'}>
                      {c.auslastung_prozent.toFixed(0)}%
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Button variant="ghost" size="sm" icon={<Edit2 className="w-4 h-4" />} onClick={() => setEditing(c)} />
                    <Button variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => setDeleting(c)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={creating || !!editing}
        onClose={() => { setCreating(false); setEditing(null); }}
        title={editing ? 'Kapazität bearbeiten' : 'Neue Kapazität'}
      >
        <CapacityForm
          capacity={editing}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['capacity'] });
            setCreating(false);
            setEditing(null);
            toast.success(editing ? 'Kapazität gespeichert' : 'Kapazität angelegt');
          }}
          onCancel={() => { setCreating(false); setEditing(null); }}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        title="Kapazität löschen?"
        message={`"${deleting?.name || deleting?.ressource_typ}" wird gelöscht.`}
        confirmLabel="Löschen"
        variant="danger"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

function CapacityForm({
  capacity,
  onSubmit,
  onCancel,
}: {
  capacity: Capacity | null;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [d, setD] = useState({
    ressource_typ: capacity?.ressource_typ || ('REGAL' as ResourceType),
    name: capacity?.name || '',
    max_kapazitaet: capacity?.max_kapazitaet ?? 50,
    aktuell_belegt: capacity?.aktuell_belegt ?? 0,
  });

  const typeOptions: SelectOption[] = Object.entries(TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...d, name: d.name || null };
      if (capacity) {
        await capacityApi.update(capacity.id, payload);
      } else {
        await capacityApi.create(payload);
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
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Typ"
          options={typeOptions}
          value={d.ressource_typ}
          onChange={(e) => setD({ ...d, ressource_typ: e.target.value as ResourceType })}
        />
        <Input
          label="Name / Position"
          value={d.name}
          onChange={(e) => setD({ ...d, name: e.target.value })}
          placeholder={d.ressource_typ === 'REGAL' ? 'z.B. Regal A1' : d.ressource_typ === 'TRAY' ? 'z.B. Tray-Pool' : 'z.B. Tag-Schicht'}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Max. Kapazität"
          type="number"
          required
          min={1}
          value={d.max_kapazitaet}
          onChange={(e) => setD({ ...d, max_kapazitaet: Number(e.target.value) })}
          hint={d.ressource_typ === 'REGAL' ? 'Anzahl Plätze' : d.ressource_typ === 'ARBEITSZEIT' ? 'Stunden pro Tag' : 'Anzahl'}
        />
        <Input
          label="Aktuell belegt"
          type="number"
          min={0}
          value={d.aktuell_belegt}
          onChange={(e) => setD({ ...d, aktuell_belegt: Number(e.target.value) })}
          hint="Wird i.d.R. automatisch durch Aussaaten aktualisiert"
        />
      </div>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>Abbrechen</Button>
        <Button type="submit" loading={loading} fullWidth>{capacity ? 'Speichern' : 'Anlegen'}</Button>
      </div>
    </form>
  );
}
