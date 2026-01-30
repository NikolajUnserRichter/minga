import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Search, Package, Warehouse, Leaf, Box, AlertTriangle,
  ArrowDownCircle, ArrowUpCircle, Thermometer
} from 'lucide-react';
import { inventoryApi, seedsApi } from '../services/api';
import {
  SeedInventory, FinishedGoodsInventory, PackagingInventory,
  InventoryLocation, InventoryMovement, LocationType
} from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  PageLoader,
  EmptyState,
  useToast,
  Badge,
  SelectOption,
  Tabs,
  Alert,
} from '../components/ui';

const LOCATION_TYPE_LABELS: Record<LocationType, string> = {
  LAGER: 'Lager',
  KUEHLRAUM: 'Kühlraum',
  REGAL: 'Regal',
  KEIMRAUM: 'Keimraum',
  VERSAND: 'Versand',
};

const LOCATION_ICONS: Record<LocationType, typeof Warehouse> = {
  LAGER: Warehouse,
  KUEHLRAUM: Thermometer,
  REGAL: Package,
  KEIMRAUM: Leaf,
  VERSAND: Box,
};

export default function Inventory() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('overview');
  const [search, setSearch] = useState('');
  const [filterLocation, setFilterLocation] = useState<string>('all');
  const [showReceiveModal, setShowReceiveModal] = useState(false);
  const [showMovementModal, setShowMovementModal] = useState(false);

  // Fetch data
  const { data: locations = [] } = useQuery({
    queryKey: ['inventory-locations'],
    queryFn: () => inventoryApi.listLocations(),
  });

  const { data: seedInventory = [], isLoading: loadingSeeds } = useQuery({
    queryKey: ['seed-inventory', filterLocation],
    queryFn: () =>
      inventoryApi.listSeedInventory({
        location_id: filterLocation === 'all' ? undefined : filterLocation,
      }),
  });

  const { data: finishedGoods = [], isLoading: loadingGoods } = useQuery({
    queryKey: ['finished-goods-inventory', filterLocation],
    queryFn: () =>
      inventoryApi.listFinishedGoods({
        location_id: filterLocation === 'all' ? undefined : filterLocation,
      }),
  });

  const { data: packaging = [], isLoading: loadingPackaging } = useQuery({
    queryKey: ['packaging-inventory', filterLocation],
    queryFn: () =>
      inventoryApi.listPackaging({
        location_id: filterLocation === 'all' ? undefined : filterLocation,
      }),
  });

  const { data: lowStockAlerts = [] } = useQuery({
    queryKey: ['low-stock-alerts'],
    queryFn: () => inventoryApi.getLowStockAlerts(),
  });

  const { data: movements = [] } = useQuery({
    queryKey: ['inventory-movements'],
    queryFn: () => inventoryApi.listMovements(),
  });

  const isLoading = loadingSeeds || loadingGoods || loadingPackaging;

  const tabs = [
    { id: 'overview', label: 'Übersicht' },
    { id: 'seeds', label: 'Saatgut', count: seedInventory.length },
    { id: 'finished', label: 'Fertigware', count: finishedGoods.length },
    { id: 'packaging', label: 'Verpackung', count: packaging.length },
    { id: 'locations', label: 'Lagerorte', count: locations.length },
    { id: 'movements', label: 'Bewegungen' },
  ];

  const locationOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Lagerorte' },
    ...locations.map((l) => ({ value: l.id, label: l.name })),
  ];

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Lagerverwaltung"
        subtitle="Bestandsübersicht und Bewegungen"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" icon={<ArrowDownCircle className="w-4 h-4" />} onClick={() => setShowReceiveModal(true)}>
              Wareneingang
            </Button>
            <Button icon={<ArrowUpCircle className="w-4 h-4" />} onClick={() => setShowMovementModal(true)}>
              Bewegung
            </Button>
          </div>
        }
      />

      {/* Low Stock Alerts */}
      {lowStockAlerts.length > 0 && (
        <Alert variant="warning" className="mb-6">
          <AlertTriangle className="w-4 h-4" />
          <span className="ml-2">
            <strong>{lowStockAlerts.length} Artikel</strong> mit niedrigem Bestand
          </span>
        </Alert>
      )}

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="mb-6" />

      {activeTab !== 'overview' && activeTab !== 'locations' && activeTab !== 'movements' && (
        <FilterBar>
          <div className="flex-1 max-w-md">
            <Input
              placeholder="Suchen..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              startIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <Select options={locationOptions} value={filterLocation} onChange={(e) => setFilterLocation(e.target.value)} />
        </FilterBar>
      )}

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <OverviewTab
          seedInventory={seedInventory}
          finishedGoods={finishedGoods}
          packaging={packaging}
          locations={locations}
          lowStockAlerts={lowStockAlerts}
        />
      )}

      {/* Seeds Tab */}
      {activeTab === 'seeds' && <SeedInventoryTab inventory={seedInventory} search={search} />}

      {/* Finished Goods Tab */}
      {activeTab === 'finished' && <FinishedGoodsTab inventory={finishedGoods} search={search} />}

      {/* Packaging Tab */}
      {activeTab === 'packaging' && <PackagingTab inventory={packaging} search={search} />}

      {/* Locations Tab */}
      {activeTab === 'locations' && <LocationsTab locations={locations} />}

      {/* Movements Tab */}
      {activeTab === 'movements' && <MovementsTab movements={movements} />}

      {/* Receive Modal */}
      <Modal open={showReceiveModal} onClose={() => setShowReceiveModal(false)} title="Wareneingang" size="lg">
        <ReceiveForm
          locations={locations}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['seed-inventory'] });
            queryClient.invalidateQueries({ queryKey: ['packaging-inventory'] });
            setShowReceiveModal(false);
            toast.success('Wareneingang erfasst');
          }}
          onCancel={() => setShowReceiveModal(false)}
        />
      </Modal>

      {/* Movement Modal */}
      <Modal open={showMovementModal} onClose={() => setShowMovementModal(false)} title="Lagerbewegung">
        <MovementForm
          seedInventory={seedInventory}
          finishedGoods={finishedGoods}
          onSubmit={() => {
            queryClient.invalidateQueries();
            setShowMovementModal(false);
            toast.success('Bewegung erfasst');
          }}
          onCancel={() => setShowMovementModal(false)}
        />
      </Modal>
    </div>
  );
}

// Overview Tab
function OverviewTab({
  seedInventory,
  finishedGoods,
  packaging,
  locations,
  lowStockAlerts,
}: {
  seedInventory: SeedInventory[];
  finishedGoods: FinishedGoodsInventory[];
  packaging: PackagingInventory[];
  locations: InventoryLocation[];
  lowStockAlerts: any[];
}) {
  const totalSeedWeight = seedInventory.reduce((sum, s) => sum + s.current_quantity, 0);
  const totalFinishedWeight = finishedGoods.reduce((sum, f) => sum + f.current_quantity, 0);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Leaf className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Saatgut</p>
              <p className="text-xl font-semibold">{(totalSeedWeight / 1000).toFixed(1)} kg</p>
              <p className="text-xs text-gray-400">{seedInventory.length} Chargen</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Package className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Fertigware</p>
              <p className="text-xl font-semibold">{(totalFinishedWeight / 1000).toFixed(1)} kg</p>
              <p className="text-xs text-gray-400">{finishedGoods.length} Chargen</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-100 rounded-lg">
              <Box className="w-5 h-5 text-gray-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Verpackung</p>
              <p className="text-xl font-semibold">{packaging.length} Artikel</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Niedrig</p>
              <p className="text-xl font-semibold">{lowStockAlerts.length}</p>
              <p className="text-xs text-gray-400">unter Mindestbestand</p>
            </div>
          </div>
        </div>
      </div>

      {/* Low Stock List */}
      {lowStockAlerts.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <h3 className="font-medium text-gray-900">Niedriger Bestand</h3>
          </div>
          <div className="divide-y">
            {lowStockAlerts.slice(0, 5).map((item: any, index: number) => (
              <div key={index} className="px-6 py-3 flex justify-between items-center">
                <div>
                  <p className="font-medium text-gray-900">{item.name || item.article_number}</p>
                  <p className="text-sm text-gray-500">{item.location_name}</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-red-600">
                    {item.current_quantity} {item.unit}
                  </p>
                  <p className="text-xs text-gray-500">Min: {item.min_quantity}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Locations Grid */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h3 className="font-medium text-gray-900">Lagerorte</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 p-6">
          {locations.map((location) => {
            const Icon = LOCATION_ICONS[location.location_type];
            return (
              <div key={location.id} className="text-center p-4 border rounded-lg hover:bg-gray-50">
                <Icon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="font-medium text-sm">{location.name}</p>
                <p className="text-xs text-gray-500">{LOCATION_TYPE_LABELS[location.location_type]}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Seed Inventory Tab
function SeedInventoryTab({ inventory, search }: { inventory: SeedInventory[]; search: string }) {
  const filtered = inventory.filter(
    (item) =>
      item.batch_number.toLowerCase().includes(search.toLowerCase()) ||
      item.seed_name?.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Kein Saatgut gefunden" description="Keine Saatgut-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Charge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sorte</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bestand</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MHD</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bio</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {filtered.map((item) => (
            <tr key={item.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-mono">{item.batch_number}</td>
              <td className="px-6 py-4 text-sm">{item.seed_name}</td>
              <td className="px-6 py-4 text-sm text-gray-500">{item.location_name}</td>
              <td className="px-6 py-4">
                <span className={item.current_quantity <= (item.min_quantity || 0) ? 'text-red-600 font-medium' : ''}>
                  {item.current_quantity} {item.unit}
                </span>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {item.mhd ? new Date(item.mhd).toLocaleDateString('de-DE') : '-'}
              </td>
              <td className="px-6 py-4">
                {item.is_organic && <Badge variant="success">Bio</Badge>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Finished Goods Tab
function FinishedGoodsTab({ inventory, search }: { inventory: FinishedGoodsInventory[]; search: string }) {
  const filtered = inventory.filter(
    (item) =>
      item.batch_number.toLowerCase().includes(search.toLowerCase()) ||
      item.product_name?.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Keine Fertigware gefunden" description="Keine Fertigwaren-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Charge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Produkt</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Verfügbar</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reserviert</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MHD</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {filtered.map((item) => {
            const isExpiringSoon = item.mhd && new Date(item.mhd) < new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
            return (
              <tr key={item.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 text-sm font-mono">{item.batch_number}</td>
                <td className="px-6 py-4 text-sm">{item.product_name}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{item.location_name}</td>
                <td className="px-6 py-4 text-sm font-medium">
                  {item.available_quantity} {item.unit}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {item.reserved_quantity} {item.unit}
                </td>
                <td className="px-6 py-4">
                  <span className={isExpiringSoon ? 'text-red-600 font-medium' : 'text-sm text-gray-500'}>
                    {new Date(item.mhd).toLocaleDateString('de-DE')}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Packaging Tab
function PackagingTab({ inventory, search }: { inventory: PackagingInventory[]; search: string }) {
  const filtered = inventory.filter(
    (item) =>
      item.article_number.toLowerCase().includes(search.toLowerCase()) ||
      item.name.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Kein Verpackungsmaterial gefunden" description="Keine Verpackungs-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Artikelnr.</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bestand</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mindest</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {filtered.map((item) => {
            const isLow = item.current_quantity <= (item.min_quantity || 0);
            return (
              <tr key={item.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 text-sm font-mono">{item.article_number}</td>
                <td className="px-6 py-4 text-sm">{item.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{item.location_name}</td>
                <td className="px-6 py-4">
                  <span className={isLow ? 'text-red-600 font-medium' : ''}>
                    {item.current_quantity} {item.unit}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {item.min_quantity} {item.unit}
                </td>
                <td className="px-6 py-4">
                  <Badge variant={isLow ? 'danger' : 'success'}>{isLow ? 'Niedrig' : 'OK'}</Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Locations Tab
function LocationsTab({ locations }: { locations: InventoryLocation[] }) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Typ</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Temperatur</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Beschreibung</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {locations.map((location) => (
            <tr key={location.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-mono">{location.code}</td>
              <td className="px-6 py-4 text-sm font-medium">{location.name}</td>
              <td className="px-6 py-4">
                <Badge>{LOCATION_TYPE_LABELS[location.location_type]}</Badge>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {location.temperature_min && location.temperature_max
                  ? `${location.temperature_min}°C - ${location.temperature_max}°C`
                  : '-'}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">{location.description || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Movements Tab
function MovementsTab({ movements }: { movements: InventoryMovement[] }) {
  const typeLabels: Record<string, string> = {
    EINGANG: 'Eingang',
    AUSGANG: 'Ausgang',
    PRODUKTION: 'Produktion',
    ERNTE: 'Ernte',
    VERLUST: 'Verlust',
    KORREKTUR: 'Korrektur',
  };

  const typeColors: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'gray' | 'purple'> = {
    EINGANG: 'success',
    AUSGANG: 'danger',
    PRODUKTION: 'info',
    ERNTE: 'success',
    VERLUST: 'danger',
    KORREKTUR: 'warning',
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Datum</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Typ</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Artikeltyp</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Menge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notizen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {movements.map((movement) => (
            <tr key={movement.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm">
                {new Date(movement.movement_date).toLocaleDateString('de-DE')}
              </td>
              <td className="px-6 py-4">
                <Badge variant={typeColors[movement.movement_type]}>{typeLabels[movement.movement_type]}</Badge>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">{movement.article_type}</td>
              <td className="px-6 py-4 text-sm font-medium">
                {movement.movement_type === 'AUSGANG' || movement.movement_type === 'VERLUST' ? '-' : '+'}
                {movement.quantity} {movement.unit}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">{movement.notes || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Receive Form
function ReceiveForm({
  locations,
  onSubmit,
  onCancel,
}: {
  locations: InventoryLocation[];
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [articleType, setArticleType] = useState<'SAATGUT' | 'VERPACKUNG'>('SAATGUT');

  const { data: seedsData } = useQuery({
    queryKey: ['seeds'],
    queryFn: () => seedsApi.list(),
  });
  const seeds = seedsData?.items || [];

  const [formData, setFormData] = useState({
    seed_id: '',
    batch_number: '',
    quantity: 0,
    unit: 'G',
    location_id: '',
    supplier: '',
    mhd: '',
    purchase_price: 0,
    is_organic: false,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (articleType === 'SAATGUT') {
        await inventoryApi.receiveSeedBatch({
          ...formData,
          mhd: formData.mhd || undefined,
        });
      }
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Erfassen');
    } finally {
      setLoading(false);
    }
  };

  const seedOptions: SelectOption[] = [
    { value: '', label: 'Saatgut auswählen...' },
    ...seeds.map((s: any) => ({ value: s.id, label: s.name })),
  ];

  const locationOptions: SelectOption[] = [
    { value: '', label: 'Lagerort auswählen...' },
    ...locations.map((l) => ({ value: l.id, label: l.name })),
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2 mb-4">
        <Button
          type="button"
          variant={articleType === 'SAATGUT' ? 'primary' : 'secondary'}
          onClick={() => setArticleType('SAATGUT')}
        >
          Saatgut
        </Button>
        <Button
          type="button"
          variant={articleType === 'VERPACKUNG' ? 'primary' : 'secondary'}
          onClick={() => setArticleType('VERPACKUNG')}
        >
          Verpackung
        </Button>
      </div>

      {articleType === 'SAATGUT' && (
        <>
          <Select
            label="Saatgut"
            required
            options={seedOptions}
            value={formData.seed_id}
            onChange={(e) => setFormData({ ...formData, seed_id: e.target.value })}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Chargennummer"
              required
              value={formData.batch_number}
              onChange={(e) => setFormData({ ...formData, batch_number: e.target.value })}
              placeholder="z.B. SB-2026-001"
            />
            <Select
              label="Lagerort"
              required
              options={locationOptions}
              value={formData.location_id}
              onChange={(e) => setFormData({ ...formData, location_id: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Menge"
              type="number"
              required
              min={0}
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: Number(e.target.value) })}
              endIcon="g"
            />
            <Input
              label="MHD"
              type="date"
              value={formData.mhd}
              onChange={(e) => setFormData({ ...formData, mhd: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Lieferant"
              value={formData.supplier}
              onChange={(e) => setFormData({ ...formData, supplier: e.target.value })}
            />
            <Input
              label="Einkaufspreis"
              type="number"
              step="0.01"
              min={0}
              value={formData.purchase_price}
              onChange={(e) => setFormData({ ...formData, purchase_price: Number(e.target.value) })}
              endIcon="€/g"
            />
          </div>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.is_organic}
              onChange={(e) => setFormData({ ...formData, is_organic: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
            />
            <span className="text-sm text-gray-700">Bio-zertifiziert</span>
          </label>
        </>
      )}

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          Erfassen
        </Button>
      </div>
    </form>
  );
}

// Movement Form
function MovementForm({
  seedInventory,
  finishedGoods,
  onSubmit,
  onCancel,
}: {
  seedInventory: SeedInventory[];
  finishedGoods: FinishedGoodsInventory[];
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [movementType, setMovementType] = useState<'consume' | 'ship' | 'loss'>('consume');

  const [formData, setFormData] = useState({
    inventory_id: '',
    product_id: '',
    quantity: 0,
    reason: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (movementType === 'consume') {
        await inventoryApi.consumeSeed(formData.inventory_id, { quantity: formData.quantity });
      } else if (movementType === 'ship') {
        await inventoryApi.shipGoods({ product_id: formData.product_id, quantity: formData.quantity });
      } else if (movementType === 'loss') {
        await inventoryApi.recordLoss(formData.inventory_id, {
          quantity: formData.quantity,
          reason: formData.reason,
        });
      }
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Erfassen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2 mb-4">
        <Button
          type="button"
          size="sm"
          variant={movementType === 'consume' ? 'primary' : 'secondary'}
          onClick={() => setMovementType('consume')}
        >
          Aussaat
        </Button>
        <Button
          type="button"
          size="sm"
          variant={movementType === 'ship' ? 'primary' : 'secondary'}
          onClick={() => setMovementType('ship')}
        >
          Versand
        </Button>
        <Button
          type="button"
          size="sm"
          variant={movementType === 'loss' ? 'primary' : 'secondary'}
          onClick={() => setMovementType('loss')}
        >
          Verlust
        </Button>
      </div>

      {movementType === 'consume' && (
        <Select
          label="Saatgut-Charge"
          required
          options={[
            { value: '', label: 'Charge auswählen...' },
            ...seedInventory.map((s) => ({
              value: s.id,
              label: `${s.batch_number} - ${s.seed_name} (${s.current_quantity}g)`,
            })),
          ]}
          value={formData.inventory_id}
          onChange={(e) => setFormData({ ...formData, inventory_id: e.target.value })}
        />
      )}

      {movementType === 'ship' && (
        <Select
          label="Produkt"
          required
          options={[
            { value: '', label: 'Produkt auswählen...' },
            ...finishedGoods.map((f) => ({
              value: f.product_id,
              label: `${f.product_name} (${f.available_quantity}${f.unit} verfügbar)`,
            })),
          ]}
          value={formData.product_id}
          onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
        />
      )}

      {movementType === 'loss' && (
        <>
          <Select
            label="Bestand"
            required
            options={[
              { value: '', label: 'Bestand auswählen...' },
              ...finishedGoods.map((f) => ({
                value: f.id,
                label: `${f.batch_number} - ${f.product_name}`,
              })),
            ]}
            value={formData.inventory_id}
            onChange={(e) => setFormData({ ...formData, inventory_id: e.target.value })}
          />
          <Input
            label="Grund"
            required
            value={formData.reason}
            onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
            placeholder="z.B. Verderb, Beschädigung..."
          />
        </>
      )}

      <Input
        label="Menge"
        type="number"
        required
        min={0}
        value={formData.quantity}
        onChange={(e) => setFormData({ ...formData, quantity: Number(e.target.value) })}
        endIcon={movementType === 'consume' ? 'g' : 'Stk'}
      />

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          Erfassen
        </Button>
      </div>
    </form>
  );
}
