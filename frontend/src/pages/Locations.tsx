import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit2 } from 'lucide-react';
import { inventoryApi } from '../services/api';
import { InventoryLocation, LocationType } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  PageLoader,
  EmptyState,
  Badge,
  useToast,
  SelectOption,
} from '../components/ui';

const TYPE_LABELS: Record<LocationType, string> = {
  LAGER: 'Lager',
  KUEHLRAUM: 'Kühlraum',
  REGAL: 'Regal',
  KEIMRAUM: 'Keimraum',
  VERSAND: 'Versand',
};

const TYPE_VARIANTS: Record<LocationType, 'success' | 'info' | 'gray' | 'warning' | 'purple'> = {
  LAGER: 'gray',
  KUEHLRAUM: 'info',
  REGAL: 'success',
  KEIMRAUM: 'warning',
  VERSAND: 'purple',
};

export default function Locations() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<InventoryLocation | null>(null);
  const [creating, setCreating] = useState(false);
  const [filterType, setFilterType] = useState<string>('all');

  const { data: locations = [], isLoading } = useQuery({
    queryKey: ['locations', { active: true }],
    queryFn: () => inventoryApi.listLocations({ is_active: true }),
  });

  if (isLoading) return <PageLoader />;

  const filtered = filterType === 'all'
    ? locations
    : locations.filter((l) => l.location_type === filterType);

  const typeFilterOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Typen' },
    ...Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label })),
  ];

  return (
    <div>
      <PageHeader
        title="Lagerorte"
        subtitle={`${locations.length} aktive Lagerorte`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
            Neuer Lagerort
          </Button>
        }
      />

      <FilterBar>
        <Select
          options={typeFilterOptions}
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        />
      </FilterBar>

      {filtered.length === 0 ? (
        <EmptyState
          title="Keine Lagerorte"
          description="Lege deine Lagerorte an (Lager, Kühlraum, Regale, Keimraum, Versand). Sie werden für Wareneingang und Position-Auswahl benötigt."
          action={
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
              Lagerort anlegen
            </Button>
          }
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Code</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Typ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Temperatur</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Beschreibung</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {filtered.map((loc) => (
                <tr key={loc.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm font-mono text-gray-900 dark:text-white">{loc.code}</td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{loc.name}</td>
                  <td className="px-6 py-4">
                    <Badge variant={TYPE_VARIANTS[loc.location_type]}>{TYPE_LABELS[loc.location_type]}</Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    {loc.temperature_min !== null || loc.temperature_max !== null
                      ? `${loc.temperature_min ?? '-'}…${loc.temperature_max ?? '-'} °C`
                      : '–'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{loc.description || '–'}</td>
                  <td className="px-6 py-4 text-right">
                    <Button variant="ghost" size="sm" icon={<Edit2 className="w-4 h-4" />} onClick={() => setEditing(loc)} />
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
        title={editing ? 'Lagerort bearbeiten' : 'Neuer Lagerort'}
      >
        <LocationForm
          location={editing}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['locations'] });
            setCreating(false);
            setEditing(null);
            toast.success(editing ? 'Lagerort gespeichert' : 'Lagerort angelegt');
          }}
          onCancel={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      </Modal>
    </div>
  );
}

function LocationForm({
  location,
  onSubmit,
  onCancel,
}: {
  location: InventoryLocation | null;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({
    code: location?.code || '',
    name: location?.name || '',
    location_type: location?.location_type || ('LAGER' as LocationType),
    description: location?.description || '',
    temperature_min: location?.temperature_min ?? null as number | null,
    temperature_max: location?.temperature_max ?? null as number | null,
  });

  const typeOptions: SelectOption[] = Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        ...data,
        description: data.description || null,
      };
      if (location) {
        await inventoryApi.updateLocation(location.id, payload);
      } else {
        await inventoryApi.createLocation(payload);
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="Code"
          required
          value={data.code}
          onChange={(e) => setData({ ...data, code: e.target.value })}
          placeholder="z.B. LAG-01, REGAL-A1"
        />
        <Input
          label="Name"
          required
          value={data.name}
          onChange={(e) => setData({ ...data, name: e.target.value })}
          placeholder="z.B. Hauptlager"
        />
      </div>
      <Select
        label="Typ"
        options={typeOptions}
        value={data.location_type}
        onChange={(e) => setData({ ...data, location_type: e.target.value as LocationType })}
      />
      <Input
        label="Beschreibung"
        value={data.description}
        onChange={(e) => setData({ ...data, description: e.target.value })}
      />
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Temperatur min"
          type="number"
          step="0.5"
          value={data.temperature_min ?? ''}
          onChange={(e) => setData({ ...data, temperature_min: e.target.value ? Number(e.target.value) : null })}
          endIcon="°C"
        />
        <Input
          label="Temperatur max"
          type="number"
          step="0.5"
          value={data.temperature_max ?? ''}
          onChange={(e) => setData({ ...data, temperature_max: e.target.value ? Number(e.target.value) : null })}
          endIcon="°C"
        />
      </div>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          {location ? 'Speichern' : 'Anlegen'}
        </Button>
      </div>
    </form>
  );
}
