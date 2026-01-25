import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productionApi, seedsApi } from '../services/api';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { GrowBatchCard } from '../components/domain/GrowBatchCard';
import { SowingForm } from '../components/domain/SowingForm';
import { HarvestForm } from '../components/domain/HarvestForm';
import {
  Select,
  Modal,
  PageLoader,
  EmptyState,
  Tabs,
  useToast,
  SelectOption,
  Input,
} from '../components/ui';
import { Plus, Sprout, Search, LayoutGrid, List } from 'lucide-react';
import type { GrowBatch, GrowBatchStatus, Seed } from '../types';

const statusOptions: SelectOption[] = [
  { value: '', label: 'Alle Status' },
  { value: 'KEIMUNG', label: 'Keimung' },
  { value: 'WACHSTUM', label: 'Wachstum' },
  { value: 'ERNTEREIF', label: 'Erntereif' },
  { value: 'GEERNTET', label: 'Geerntet' },
  { value: 'VERLUST', label: 'Verlust' },
];

export default function Production() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [showErntereif, setShowErntereif] = useState(false);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const [isCreating, setIsCreating] = useState(false);
  const [harvestingBatch, setHarvestingBatch] = useState<GrowBatch | null>(null);

  const { data: batchesData, isLoading } = useQuery({
    queryKey: ['growBatches', statusFilter, showErntereif],
    queryFn: () =>
      productionApi.listGrowBatches({
        status: statusFilter || undefined,
        erntereif: showErntereif || undefined,
      }),
  });

  const { data: seedsData } = useQuery({
    queryKey: ['seeds', 'active'],
    queryFn: () => seedsApi.getSeeds({ aktiv: true }),
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: GrowBatchStatus }) =>
      productionApi.updateGrowBatchStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growBatches'] });
      toast.success('Status aktualisiert');
    },
    onError: () => {
      toast.error('Fehler beim Aktualisieren');
    },
  });

  const batches = batchesData?.items || [];
  const filteredBatches = batches.filter((batch: GrowBatch) =>
    batch.seed_name?.toLowerCase().includes(search.toLowerCase())
  );

  // Group batches by status for tabs view
  const batchesByStatus = {
    KEIMUNG: filteredBatches.filter((b: GrowBatch) => b.status === 'KEIMUNG'),
    WACHSTUM: filteredBatches.filter((b: GrowBatch) => b.status === 'WACHSTUM'),
    ERNTEREIF: filteredBatches.filter((b: GrowBatch) => b.status === 'ERNTEREIF'),
  };

  const tabs = [
    { id: 'all', label: 'Alle', count: filteredBatches.length },
    { id: 'KEIMUNG', label: 'Keimung', count: batchesByStatus.KEIMUNG.length },
    { id: 'WACHSTUM', label: 'Wachstum', count: batchesByStatus.WACHSTUM.length },
    { id: 'ERNTEREIF', label: 'Erntereif', count: batchesByStatus.ERNTEREIF.length },
  ];

  const [activeTab, setActiveTab] = useState('all');
  const displayedBatches =
    activeTab === 'all' ? filteredBatches : filteredBatches.filter((b: GrowBatch) => b.status === activeTab);

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Produktion"
        subtitle={`${batches.length} Wachstumschargen`}
        actions={
          <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
            <Plus className="w-4 h-4" />
            Neue Aussaat
          </button>
        }
      />

      {/* Seeds Overview */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Saatgutsorten</h3>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {seedsData?.items?.map((seed: Seed) => (
              <div
                key={seed.id}
                className="p-4 bg-gray-50 rounded-lg text-center hover:bg-minga-50 transition-colors cursor-pointer"
                onClick={() => setIsCreating(true)}
              >
                <div className="w-10 h-10 bg-minga-100 rounded-full flex items-center justify-center mx-auto mb-2">
                  <Sprout className="w-5 h-5 text-minga-600" />
                </div>
                <p className="font-medium text-gray-900">{seed.name}</p>
                <p className="text-xs text-gray-500">
                  {seed.keimdauer_tage + seed.wachstumsdauer_tage} Tage | {seed.ertrag_gramm_pro_tray}g
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Filters */}
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
          options={statusOptions}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        />
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showErntereif}
            onChange={(e) => setShowErntereif(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
          />
          <span className="text-sm text-gray-700">Nur Erntereife</span>
        </label>
        <div className="flex border border-gray-200 rounded-lg overflow-hidden">
          <button
            className={`p-2 ${viewMode === 'grid' ? 'bg-minga-100 text-minga-600' : 'bg-white text-gray-400'}`}
            onClick={() => setViewMode('grid')}
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button
            className={`p-2 ${viewMode === 'list' ? 'bg-minga-100 text-minga-600' : 'bg-white text-gray-400'}`}
            onClick={() => setViewMode('list')}
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </FilterBar>

      {/* Batches */}
      {displayedBatches.length === 0 ? (
        <EmptyState
          title="Keine Chargen gefunden"
          description={search ? 'Versuche eine andere Suche.' : 'Starte deine erste Aussaat.'}
          action={
            !search && (
              <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                <Plus className="w-4 h-4" />
                Erste Aussaat
              </button>
            )
          }
        />
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayedBatches.map((batch: GrowBatch) => (
            <GrowBatchCard
              key={batch.id}
              batch={batch}
              onStatusChange={(status) =>
                updateStatusMutation.mutate({ id: batch.id, status })
              }
              onHarvest={() => setHarvestingBatch(batch)}
            />
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Sorte</th>
                <th>Trays</th>
                <th>Aussaat</th>
                <th>Ernte (optimal)</th>
                <th>Tage</th>
                <th>Position</th>
                <th>Status</th>
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {displayedBatches.map((batch: GrowBatch) => (
                <tr
                  key={batch.id}
                  className={batch.ist_erntereif ? 'bg-green-50' : ''}
                >
                  <td className="font-medium">{batch.seed_name}</td>
                  <td>{batch.tray_anzahl}</td>
                  <td>{new Date(batch.aussaat_datum).toLocaleDateString('de-DE')}</td>
                  <td>{new Date(batch.erwartete_ernte_optimal).toLocaleDateString('de-DE')}</td>
                  <td>{batch.tage_seit_aussaat}</td>
                  <td>{batch.regal_position || '-'}</td>
                  <td>
                    <span className={`badge badge-${batch.status.toLowerCase()}`}>{batch.status}</span>
                  </td>
                  <td>
                    <div className="flex gap-2">
                      {batch.status === 'KEIMUNG' && (
                        <button
                          onClick={() =>
                            updateStatusMutation.mutate({ id: batch.id, status: 'WACHSTUM' })
                          }
                          className="text-sm text-minga-600 hover:text-minga-700"
                        >
                          Wachstum
                        </button>
                      )}
                      {batch.status === 'WACHSTUM' && (
                        <button
                          onClick={() =>
                            updateStatusMutation.mutate({ id: batch.id, status: 'ERNTEREIF' })
                          }
                          className="text-sm text-minga-600 hover:text-minga-700"
                        >
                          Erntereif
                        </button>
                      )}
                      {(batch.status === 'WACHSTUM' || batch.status === 'ERNTEREIF') && (
                        <button
                          onClick={() => setHarvestingBatch(batch)}
                          className="text-sm text-green-600 hover:text-green-700"
                        >
                          Ernten
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      <Modal open={isCreating} onClose={() => setIsCreating(false)} title="Neue Aussaat" size="lg">
        <SowingForm
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['growBatches'] });
            setIsCreating(false);
            toast.success('Aussaat angelegt');
          }}
          onCancel={() => setIsCreating(false)}
        />
      </Modal>

      {/* Harvest Modal */}
      <Modal
        open={!!harvestingBatch}
        onClose={() => setHarvestingBatch(null)}
        title={`Ernte: ${harvestingBatch?.seed_name}`}
      >
        {harvestingBatch && (
          <HarvestForm
            growBatch={harvestingBatch}
            onSubmit={() => {
              queryClient.invalidateQueries({ queryKey: ['growBatches'] });
              setHarvestingBatch(null);
              toast.success('Ernte erfasst');
            }}
            onCancel={() => setHarvestingBatch(null)}
          />
        )}
      </Modal>
    </div>
  );
}
