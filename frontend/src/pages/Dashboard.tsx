import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productionApi, salesApi, forecastingApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { StatCard } from '../components/domain/StatCard';
import { GrowBatchStatusBadge, PageLoader, EmptyState, Badge, Modal, useToast } from '../components/ui';
import { HarvestForm } from '../components/domain/HarvestForm';
import {
  Sprout,
  Package,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Scale,
  Check,
  ArrowRight,
} from 'lucide-react';
import { useState } from 'react';
import type { GrowBatch, ProductionSuggestion } from '../types';

export default function Dashboard() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [harvestingBatch, setHarvestingBatch] = useState<GrowBatch | null>(null);

  const { data: dashboardData, isLoading: dashboardLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: productionApi.getDashboard,
  });

  const { data: ordersData } = useQuery({
    queryKey: ['orders', 'open'],
    queryFn: () => salesApi.listOrders({ status: 'OFFEN' }),
  });

  const { data: suggestionsData } = useQuery({
    queryKey: ['suggestions', 'pending'],
    queryFn: () => forecastingApi.listProductionSuggestions({ status: 'VORGESCHLAGEN' }),
  });

  const { data: erntereifData } = useQuery({
    queryKey: ['growBatches', 'erntereif'],
    queryFn: () => productionApi.listGrowBatches({ erntereif: true }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => forecastingApi.approveSuggestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] });
      toast.success('Vorschlag genehmigt');
    },
    onError: () => {
      toast.error('Fehler beim Genehmigen');
    },
  });

  if (dashboardLoading) {
    return <PageLoader />;
  }

  const totalChargen = Object.values(dashboardData?.chargen_nach_status || {}).reduce(
    (a: number, b: number) => a + b,
    0
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle={`Übersicht KW ${dashboardData?.woche?.start
          ? new Date(dashboardData.woche.start).toLocaleDateString('de-DE', {
            day: '2-digit',
            month: '2-digit',
          })
          : ''
          } - ${dashboardData?.woche?.ende
            ? new Date(dashboardData.woche.ende).toLocaleDateString('de-DE', {
              day: '2-digit',
              month: '2-digit',
            })
            : ''
          }`}
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Aktive Chargen"
          value={totalChargen}
          icon={<Sprout className="w-5 h-5" />}
          variant="primary"
        />
        <StatCard
          title="Erntereif"
          value={dashboardData?.erntereife_chargen || 0}
          icon={<Package className="w-5 h-5" />}
          variant="success"
        />
        <StatCard
          title="Offene Bestellungen"
          value={ordersData?.total || 0}
          icon={<Calendar className="w-5 h-5" />}
          variant="info"
        />
        <StatCard
          title="Warnungen"
          value={suggestionsData?.warnungen_gesamt || 0}
          icon={<AlertTriangle className="w-5 h-5" />}
          variant="warning"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Erntereife Chargen */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Erntereife Chargen</h3>
            {erntereifData?.items && erntereifData.items.length > 0 && (
              <Badge variant="success">{erntereifData.items.length}</Badge>
            )}
          </div>
          <div className="card-body">
            {erntereifData?.items?.length ? (
              <div className="space-y-3">
                {erntereifData.items.slice(0, 5).map((batch: GrowBatch) => (
                  <div
                    key={batch.id}
                    className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200"
                  >
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{batch.seed_name}</p>
                      <p className="text-sm text-gray-500">
                        {batch.tray_anzahl} Trays | Optimal:{' '}
                        {new Date(batch.erwartete_ernte_optimal).toLocaleDateString('de-DE')}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <GrowBatchStatusBadge status={batch.status} />
                      <button
                        className="btn btn-success btn-sm"
                        onClick={() => setHarvestingBatch(batch)}
                      >
                        Ernten
                      </button>
                    </div>
                  </div>
                ))}
                {erntereifData.items.length > 5 && (
                  <a href="/production" className="flex items-center gap-1 text-sm text-minga-600 hover:text-minga-700">
                    Alle {erntereifData.items.length} anzeigen <ArrowRight className="w-4 h-4" />
                  </a>
                )}
              </div>
            ) : (
              <EmptyState
                title="Keine erntereife Chargen"
                description="Aktuell sind keine Chargen erntereif."
              />
            )}
          </div>
        </div>

        {/* Produktionsvorschläge */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Produktionsvorschläge</h3>
            {(suggestionsData?.warnungen_gesamt || 0) > 0 && (
              <Badge variant="warning">{suggestionsData?.warnungen_gesamt} Warnungen</Badge>
            )}
          </div>
          <div className="card-body">
            {suggestionsData?.items?.length ? (
              <div className="space-y-3">
                {suggestionsData.items.slice(0, 5).map((suggestion: ProductionSuggestion) => (
                  <div
                    key={suggestion.id}
                    className={`flex items-center justify-between p-3 rounded-lg border ${suggestion.warnungen?.length
                      ? 'bg-amber-50 border-amber-200'
                      : 'bg-gray-50 border-gray-200'
                      }`}
                  >
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{suggestion.seed_name}</p>
                      <p className="text-sm text-gray-500">
                        {suggestion.empfohlene_trays} Trays | Aussaat:{' '}
                        {new Date(suggestion.aussaat_datum).toLocaleDateString('de-DE')}
                      </p>
                      {suggestion.warnungen?.map((w, i) => (
                        <p key={i} className="text-xs text-amber-600 mt-1">
                          {w.nachricht}
                        </p>
                      ))}
                    </div>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => approveMutation.mutate(suggestion.id)}
                      disabled={approveMutation.isPending}
                    >
                      <Check className="w-4 h-4" />
                      Genehmigen
                    </button>
                  </div>
                ))}
                {suggestionsData.items.length > 5 && (
                  <a href="/suggestions" className="flex items-center gap-1 text-sm text-minga-600 hover:text-minga-700">
                    Alle {suggestionsData.items.length} anzeigen <ArrowRight className="w-4 h-4" />
                  </a>
                )}
              </div>
            ) : (
              <EmptyState
                title="Keine offenen Vorschläge"
                description="Alle Produktionsvorschläge wurden bearbeitet."
              />
            )}
          </div>
        </div>

        {/* Wochenzusammenfassung */}
        <div className="card col-span-1 lg:col-span-2">
          <div className="card-header">
            <h3 className="card-title">Diese Woche</h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div className="text-center p-4 bg-minga-50 rounded-lg">
                <Scale className="w-8 h-8 text-minga-600 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900">
                  {((dashboardData?.ernten_diese_woche_gramm || 0) / 1000).toFixed(1)} kg
                </p>
                <p className="text-sm text-gray-500">Ernte diese Woche</p>
              </div>
              <div className="text-center p-4 bg-red-50 rounded-lg">
                <AlertTriangle className="w-8 h-8 text-red-600 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900">
                  {((dashboardData?.verluste_diese_woche_gramm || 0) / 1000).toFixed(1)} kg
                </p>
                <p className="text-sm text-gray-500">Verluste</p>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <TrendingUp className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900">
                  {dashboardData?.erntereife_chargen || 0}
                </p>
                <p className="text-sm text-gray-500">Chargen bereit</p>
              </div>
            </div>
          </div>
        </div>
      </div >

      {/* Harvest Modal */}
      < Modal
        open={!!harvestingBatch
        }
        onClose={() => setHarvestingBatch(null)}
        title={`Ernte: ${harvestingBatch?.seed_name}`}
      >
        {harvestingBatch && (
          <HarvestForm
            batch={harvestingBatch}
            onSubmit={() => {
              queryClient.invalidateQueries({ queryKey: ['growBatches'] });
              queryClient.invalidateQueries({ queryKey: ['dashboard'] });
              setHarvestingBatch(null);
              toast.success('Ernte erfasst');
            }}
            onCancel={() => setHarvestingBatch(null)}
          />
        )}
      </Modal >
    </div >
  );
}
