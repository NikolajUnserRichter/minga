import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  Search, Package, Warehouse, Leaf, Box, AlertTriangle,
  ArrowDownCircle, ArrowUpCircle, Thermometer, Printer, Link as LinkIcon, Edit
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
import { TraceabilityView } from '../components/domain/TraceabilityView';
import { StockCorrectionModal } from '../components/domain/StockCorrectionModal';
import { TraceabilityChain, InventoryType } from '../types';

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
  const [showTraceabilityModal, setShowTraceabilityModal] = useState(false);
  const [selectedTraceItem, setSelectedTraceItem] = useState<TraceabilityChain | null>(null);
  const [showCorrectionModal, setShowCorrectionModal] = useState(false);
  const [correctionItem, setCorrectionItem] = useState<{ id: string, qty: number, unit: string, type: InventoryType, name: string } | null>(null);
  const [searchParams] = useSearchParams();
  const highlightId = searchParams.get('highlight');

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

  // Effect to handle scan redirect
  useEffect(() => {
    if (highlightId && finishedGoods.length > 0) {
      const item = finishedGoods.find(i => i.id === highlightId);
      if (item) {
        setActiveTab('finished');
        // Auto open traceability
        inventoryApi.getTraceability(item.id).then(traceData => {
          setSelectedTraceItem(traceData);
          setShowTraceabilityModal(true);
        });
      }
    }
  }, [highlightId, finishedGoods]);

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
      {activeTab === 'seeds' && (
        <SeedInventoryTab
          inventory={seedInventory}
          search={search}
          onCorrect={(item) => {
            setCorrectionItem({
              id: item.id,
              qty: item.current_quantity,
              unit: item.unit,
              type: 'SAATGUT',
              name: `${item.seed_name} (${item.batch_number})`
            });
            setShowCorrectionModal(true);
          }}
        />
      )}

      {/* Finished Goods Tab */}
      {activeTab === 'finished' && (
        <FinishedGoodsTab
          inventory={finishedGoods}
          search={search}
          onShowTraceability={(data) => {
            setSelectedTraceItem(data);
            setShowTraceabilityModal(true);
          }}
          onCorrect={(item) => {
            setCorrectionItem({
              id: item.id,
              qty: item.current_quantity,
              unit: item.unit,
              type: 'FERTIGWARE',
              name: `${item.product_name} (${item.batch_number})`
            });
            setShowCorrectionModal(true);
          }}
        />
      )}

      {/* Packaging Tab */}
      {activeTab === 'packaging' && (
        <PackagingTab
          inventory={packaging}
          search={search}
          onCorrect={(item) => {
            setCorrectionItem({
              id: item.id,
              qty: item.current_quantity,
              unit: item.unit,
              type: 'VERPACKUNG',
              name: `${item.name} (${item.article_number})`
            });
            setShowCorrectionModal(true);
          }}
        />
      )}

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

      {/* Traceability Modal */}
      <Modal
        open={showTraceabilityModal}
        onClose={() => setShowTraceabilityModal(false)}
        title="Rückverfolgbarkeit"
        size="lg"
      >
        {selectedTraceItem ? (
          <TraceabilityView data={selectedTraceItem} />
        ) : (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Lade Daten...</div>
        )}
      </Modal>

      {/* Stock Correction Modal */}
      {correctionItem && (
        <StockCorrectionModal
          open={showCorrectionModal}
          onClose={() => {
            setShowCorrectionModal(false);
            setCorrectionItem(null);
          }}
          inventoryId={correctionItem.id}
          currentQuantity={correctionItem.qty}
          unit={correctionItem.unit}
          itemType={correctionItem.type}
          itemName={correctionItem.name}
        />
      )}
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
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <Leaf className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Saatgut</p>
              <p className="text-xl font-semibold">{(totalSeedWeight / 1000).toFixed(1)} kg</p>
              <p className="text-xs text-gray-400">{seedInventory.length} Chargen</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Package className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Fertigware</p>
              <p className="text-xl font-semibold">{(totalFinishedWeight / 1000).toFixed(1)} kg</p>
              <p className="text-xs text-gray-400">{finishedGoods.length} Chargen</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
              <Box className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Verpackung</p>
              <p className="text-xl font-semibold">{packaging.length} Artikel</p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Niedrig</p>
              <p className="text-xl font-semibold">{lowStockAlerts.length}</p>
              <p className="text-xs text-gray-400">unter Mindestbestand</p>
            </div>
          </div>
        </div>
      </div>

      {/* Low Stock List */}
      {lowStockAlerts.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <h3 className="font-medium text-gray-900 dark:text-white">Niedriger Bestand</h3>
          </div>
          <div className="divide-y">
            {lowStockAlerts.slice(0, 5).map((item: any, index: number) => (
              <div key={index} className="px-6 py-3 flex justify-between items-center">
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">{item.name || item.article_number}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{item.location_name}</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-red-600 dark:text-red-400">
                    {item.current_quantity} {item.unit}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Min: {item.min_quantity}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Locations Grid */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h3 className="font-medium text-gray-900 dark:text-white">Lagerorte</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 p-6">
          {locations.map((location) => {
            const Icon = LOCATION_ICONS[location.location_type];
            return (
              <div key={location.id} className="text-center p-4 border rounded-lg hover:bg-gray-50 dark:bg-gray-700/50">
                <Icon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="font-medium text-sm">{location.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{LOCATION_TYPE_LABELS[location.location_type]}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Seed Inventory Tab
function SeedInventoryTab({ inventory, search, onCorrect }: { inventory: SeedInventory[]; search: string; onCorrect: (item: SeedInventory) => void }) {
  const filtered = inventory.filter(
    (item) =>
      item.batch_number.toLowerCase().includes(search.toLowerCase()) ||
      item.seed_name?.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Kein Saatgut gefunden" description="Keine Saatgut-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Charge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Sorte</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Bestand</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">MHD</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Bio</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {filtered.map((item) => (
            <tr key={item.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
              <td className="px-6 py-4 text-sm font-mono">{item.batch_number}</td>
              <td className="px-6 py-4 text-sm">{item.seed_name}</td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{item.location_name}</td>
              <td className="px-6 py-4">
                <span className={item.current_quantity <= (item.min_quantity || 0) ? 'text-red-600 dark:text-red-400 font-medium' : ''}>
                  {item.current_quantity} {item.unit}
                </span>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                {item.mhd ? new Date(item.mhd).toLocaleDateString('de-DE') : '-'}
              </td>
              <td className="px-6 py-4">
                {item.is_organic && <Badge variant="success">Bio</Badge>}
                <button
                  className="text-gray-400 hover:text-blue-600 dark:text-blue-400 ml-2"
                  title="Bestand korrigieren"
                  onClick={() => onCorrect(item)}
                >
                  <Edit className="w-4 h-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Finished Goods Tab
function FinishedGoodsTab({
  inventory,
  search,
  onShowTraceability,
  onCorrect
}: {
  inventory: FinishedGoodsInventory[];
  search: string;
  onShowTraceability: (data: TraceabilityChain) => void;
  onCorrect: (item: FinishedGoodsInventory) => void;
}) {
  const fgToast = useToast();
  const filtered = inventory.filter(
    (item) =>
      item.batch_number.toLowerCase().includes(search.toLowerCase()) ||
      item.product_name?.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Keine Fertigware gefunden" description="Keine Fertigwaren-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Charge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Produkt</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Verfügbar</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Reserviert</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">MHD</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Aktionen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {filtered.map((item) => {
            const isExpiringSoon = item.mhd && new Date(item.mhd) < new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
            return (
              <tr key={item.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
                <td className="px-6 py-4 text-sm font-mono">{item.batch_number}</td>
                <td className="px-6 py-4 text-sm">{item.product_name}</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{item.location_name}</td>
                <td className="px-6 py-4 text-sm font-medium">
                  {item.available_quantity} {item.unit}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                  {item.reserved_quantity} {item.unit}
                </td>
                <td className="px-6 py-4">
                  <span className={isExpiringSoon ? 'text-red-600 dark:text-red-400 font-medium' : 'text-sm text-gray-500 dark:text-gray-400'}>
                    {new Date(item.mhd).toLocaleDateString('de-DE')}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button
                    className="text-gray-400 hover:text-minga-600 dark:text-minga-400 p-1"
                    title="Etikett drucken"
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        const response = await inventoryApi.downloadLabel(item.id);
                        const url = window.URL.createObjectURL(new Blob([response.data]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.setAttribute('download', `Label_Ware_${item.batch_number || item.id}.pdf`);
                        document.body.appendChild(link);
                        link.click();
                        link.remove();
                      } catch (err) {
                        fgToast.error('Fehler beim Laden des Labels');
                      }
                    }}
                  >
                    <Printer className="w-4 h-4" />
                  </button>
                  <button
                    className="text-gray-400 hover:text-blue-600 dark:text-blue-400 p-1 ml-1"
                    title="Rückverfolgung"
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        const traceData = await inventoryApi.getTraceability(item.id);
                        onShowTraceability(traceData);
                      } catch (err) {
                        fgToast.error('Fehler beim Laden der Rückverfolgung');
                      }
                    }}
                  >
                    <LinkIcon className="w-4 h-4" />
                  </button>
                  <button
                    className="text-gray-400 hover:text-blue-600 dark:text-blue-400 p-1 ml-1"
                    title="Bestand korrigieren"
                    onClick={(e) => {
                      e.stopPropagation();
                      onCorrect(item);
                    }}
                  >
                    <Edit className="w-4 h-4" />
                  </button>
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
function PackagingTab({ inventory, search, onCorrect }: { inventory: PackagingInventory[]; search: string; onCorrect: (item: PackagingInventory) => void }) {
  const filtered = inventory.filter(
    (item) =>
      item.article_number.toLowerCase().includes(search.toLowerCase()) ||
      item.name.toLowerCase().includes(search.toLowerCase())
  );

  if (filtered.length === 0) {
    return <EmptyState title="Kein Verpackungsmaterial gefunden" description="Keine Verpackungs-Bestände vorhanden." />;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Artikelnr.</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Lagerort</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Bestand</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Mindest</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {filtered.map((item) => {
            const isLow = item.current_quantity <= (item.min_quantity || 0);
            return (
              <tr key={item.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
                <td className="px-6 py-4 text-sm font-mono">{item.article_number}</td>
                <td className="px-6 py-4 text-sm">{item.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{item.location_name}</td>
                <td className="px-6 py-4">
                  <span className={isLow ? 'text-red-600 dark:text-red-400 font-medium' : ''}>
                    {item.current_quantity} {item.unit}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                  {item.min_quantity} {item.unit}
                </td>
                <td className="px-6 py-4">
                  <Badge variant={isLow ? 'danger' : 'success'}>{isLow ? 'Niedrig' : 'OK'}</Badge>
                  <button
                    className="text-gray-400 hover:text-blue-600 dark:text-blue-400 ml-2"
                    title="Bestand korrigieren"
                    onClick={() => onCorrect(item)}
                  >
                    <Edit className="w-4 h-4" />
                  </button>
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
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Code</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Typ</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Temperatur</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Beschreibung</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {locations.map((location) => (
            <tr key={location.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
              <td className="px-6 py-4 text-sm font-mono">{location.code}</td>
              <td className="px-6 py-4 text-sm font-medium">{location.name}</td>
              <td className="px-6 py-4">
                <Badge>{LOCATION_TYPE_LABELS[location.location_type]}</Badge>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                {location.temperature_min && location.temperature_max
                  ? `${location.temperature_min}°C - ${location.temperature_max}°C`
                  : '-'}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{location.description || '-'}</td>
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
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Datum</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Typ</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Artikeltyp</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Menge</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Notizen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {movements.map((movement) => (
            <tr key={movement.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
              <td className="px-6 py-4 text-sm">
                {new Date(movement.movement_date).toLocaleDateString('de-DE')}
              </td>
              <td className="px-6 py-4">
                <Badge variant={typeColors[movement.movement_type]}>{typeLabels[movement.movement_type]}</Badge>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{movement.article_type}</td>
              <td className="px-6 py-4 text-sm font-medium">
                {movement.movement_type === 'AUSGANG' || movement.movement_type === 'VERLUST' ? '-' : '+'}
                {movement.quantity} {movement.unit}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{movement.notes || '-'}</td>
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
  const [articleType, setArticleType] = useState<'SAATGUT' | 'VERPACKUNG' | 'SUBSTRAT' | 'PFANDKISTE'>('SAATGUT');

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
    lieferdatum: new Date().toISOString().split('T')[0],
    in_production_at: '',
    lieferschein_nr: '',
    kontrollstelle: '',
    purchase_price: 0,
    is_organic: false,
  });

  const [packagingData, setPackagingData] = useState({
    sku: '',
    name: '',
    quantity: 0,
    unit: 'Stück',
    location_id: '',
    supplier_name: '',
    supplier_sku: '',
    purchase_price: 0,
    min_quantity: 0,
    reorder_quantity: 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (articleType === 'SAATGUT') {
        await inventoryApi.receiveSeedBatch({
          ...formData,
          mhd: formData.mhd || undefined,
          lieferdatum: formData.lieferdatum || undefined,
          in_production_at: formData.in_production_at || undefined,
          lieferschein_nr: formData.lieferschein_nr || undefined,
          kontrollstelle: formData.is_organic ? (formData.kontrollstelle || undefined) : undefined,
        });
        toast.success('Wareneingang erfasst (inkl. Saatgut-Charge)');
      } else if (['VERPACKUNG', 'SUBSTRAT', 'PFANDKISTE'].includes(articleType)) {
        if (!packagingData.sku || !packagingData.name || packagingData.quantity <= 0) {
          toast.error('SKU, Name und Menge sind Pflichtfelder');
          return;
        }
        await inventoryApi.receivePackaging({
          sku: packagingData.sku,
          name: packagingData.name,
          quantity: packagingData.quantity,
          unit: packagingData.unit,
          article_type: articleType as 'VERPACKUNG' | 'SUBSTRAT' | 'PFANDKISTE',
          location_id: packagingData.location_id || undefined,
          supplier_name: packagingData.supplier_name || undefined,
          supplier_sku: packagingData.supplier_sku || undefined,
          purchase_price: packagingData.purchase_price || undefined,
          min_quantity: packagingData.min_quantity || undefined,
          reorder_quantity: packagingData.reorder_quantity || undefined,
        });
        const labelMap: Record<string, string> = { VERPACKUNG: 'Verpackung', SUBSTRAT: 'Substrat', PFANDKISTE: 'Pfandkiste' };
        toast.success(`Wareneingang ${labelMap[articleType]}: ${packagingData.quantity} ${packagingData.unit} erfasst`);
      }
      onSubmit();
    } catch (error: any) {
      const detail = error?.response?.data?.detail || 'Fehler beim Erfassen';
      toast.error(detail);
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
      <div className="flex flex-wrap gap-2 mb-4">
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
        <Button
          type="button"
          variant={articleType === 'SUBSTRAT' ? 'primary' : 'secondary'}
          onClick={() => setArticleType('SUBSTRAT')}
        >
          Substrat
        </Button>
        <Button
          type="button"
          variant={articleType === 'PFANDKISTE' ? 'primary' : 'secondary'}
          onClick={() => setArticleType('PFANDKISTE')}
        >
          Pfandkiste
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

          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Anlieferungsdatum"
              type="date"
              value={formData.lieferdatum}
              onChange={(e) => setFormData({ ...formData, lieferdatum: e.target.value })}
            />
            <Input
              label="In Produktion ab"
              type="date"
              value={formData.in_production_at}
              onChange={(e) => setFormData({ ...formData, in_production_at: e.target.value })}
              hint="leer = noch im Lager"
            />
            <Input
              label="Lieferschein-Nr."
              value={formData.lieferschein_nr}
              onChange={(e) => setFormData({ ...formData, lieferschein_nr: e.target.value })}
              placeholder="z.B. LS-2026-0123"
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

          <div className="space-y-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_organic}
                onChange={(e) => setFormData({ ...formData, is_organic: e.target.checked })}
                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">BIO-zertifiziert (für Kontrollstelle dokumentieren)</span>
            </label>
            {formData.is_organic && (
              <Input
                label="Kontrollstelle"
                value={formData.kontrollstelle}
                onChange={(e) => setFormData({ ...formData, kontrollstelle: e.target.value })}
                placeholder="z.B. DE-ÖKO-006"
              />
            )}
          </div>
        </>
      )}

      {['VERPACKUNG', 'SUBSTRAT', 'PFANDKISTE'].includes(articleType) && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="SKU"
              required
              value={packagingData.sku}
              onChange={(e) => setPackagingData({ ...packagingData, sku: e.target.value })}
              placeholder={articleType === 'SUBSTRAT' ? 'z.B. SUB-HANF-50L' : articleType === 'PFANDKISTE' ? 'z.B. PK-MWK-12' : 'z.B. VP-KISTE12-001'}
              hint="Bekannte SKU → Bestand wird erhöht"
            />
            <Input
              label="Bezeichnung"
              required
              value={packagingData.name}
              onChange={(e) => setPackagingData({ ...packagingData, name: e.target.value })}
              placeholder={articleType === 'SUBSTRAT' ? 'z.B. Hanfmatte 50L' : articleType === 'PFANDKISTE' ? 'z.B. Mehrwegkiste 12er' : 'z.B. Mehrwegkiste 12 Schalen'}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Menge"
              type="number"
              required
              min={1}
              value={packagingData.quantity}
              onChange={(e) => setPackagingData({ ...packagingData, quantity: Number(e.target.value) })}
            />
            <Input
              label="Einheit"
              value={packagingData.unit}
              onChange={(e) => setPackagingData({ ...packagingData, unit: e.target.value })}
            />
            <Select
              label="Lagerort"
              options={locationOptions}
              value={packagingData.location_id}
              onChange={(e) => setPackagingData({ ...packagingData, location_id: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Lieferant"
              value={packagingData.supplier_name}
              onChange={(e) => setPackagingData({ ...packagingData, supplier_name: e.target.value })}
            />
            <Input
              label="Lieferanten-SKU"
              value={packagingData.supplier_sku}
              onChange={(e) => setPackagingData({ ...packagingData, supplier_sku: e.target.value })}
            />
            <Input
              label="Einkaufspreis"
              type="number"
              step="0.01"
              min={0}
              value={packagingData.purchase_price}
              onChange={(e) => setPackagingData({ ...packagingData, purchase_price: Number(e.target.value) })}
              endIcon="€/Stk"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Mindestbestand"
              type="number"
              min={0}
              value={packagingData.min_quantity}
              onChange={(e) => setPackagingData({ ...packagingData, min_quantity: Number(e.target.value) })}
            />
            <Input
              label="Nachbestellmenge"
              type="number"
              min={0}
              value={packagingData.reorder_quantity}
              onChange={(e) => setPackagingData({ ...packagingData, reorder_quantity: Number(e.target.value) })}
            />
          </div>
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
