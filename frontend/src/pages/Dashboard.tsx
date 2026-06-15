import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productionApi, salesApi, forecastingApi, invoicesApi } from '../services/api';
import { PageHeader, useUser } from '../components/common/Layout';
import { StatCard } from '../components/domain/StatCard';
import { GrowBatchStatusBadge, EmptyState, Badge, Modal, useToast } from '../components/ui';
import { DashboardSkeleton } from '../components/ui/Skeleton';
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
  Receipt,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import type { GrowBatch, ProductionSuggestion } from '../types';

export default function Dashboard() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [harvestingBatch, setHarvestingBatch] = useState<GrowBatch | null>(null);
  const { user } = useUser();
  const role = user.role;

  // Mock data for demo mode (no backend)
  const MOCK_DASHBOARD = {
    chargen_nach_status: { KEIMUNG: 8, WACHSTUM: 12, ERNTEREIF: 3, GEERNTET: 45 },
    erntereife_chargen: 3,
    ernten_diese_woche_gramm: 14200,
    verluste_diese_woche_gramm: 800,
    woche: {
      start: new Date(Date.now() - 3 * 86400000).toISOString(),
      ende: new Date(Date.now() + 4 * 86400000).toISOString(),
    },
  };

  const { data: rawDashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: productionApi.getDashboard,
    retry: 1,
  });
  const isDemo = !rawDashboard && !dashboardLoading;
  const dashboardData = rawDashboard || MOCK_DASHBOARD;

  const { data: ordersData } = useQuery({
    queryKey: ['orders', 'open'],
    queryFn: () => salesApi.listOrders({ status: 'BESTAETIGT' }),
    retry: 0,
  });

  const { data: suggestionsData } = useQuery({
    queryKey: ['suggestions', 'pending'],
    queryFn: () => forecastingApi.listProductionSuggestions({ status: 'VORGESCHLAGEN' }),
    retry: 0,
  });

  const { data: erntereifData } = useQuery({
    queryKey: ['growBatches', 'erntereif'],
    queryFn: () => productionApi.listGrowBatches({ erntereif: true }),
    retry: 0,
  });

  // Sales / Accounting role: invoice stats
  const showSalesSection = ['ADMIN', 'SALES', 'ACCOUNTING'].includes(role);
  const { data: invoicesData } = useQuery({
    queryKey: ['invoices', 'open'],
    queryFn: () => invoicesApi.list({ status: 'OFFEN' }),
    enabled: showSalesSection,
    retry: 0,
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
    return <DashboardSkeleton />;
  }



  const totalChargen = Object.values(dashboardData?.chargen_nach_status || {}).reduce(
    (a: number, b: number) => a + b,
    0
  );

  return (
    <div className="space-y-6">
      {isDemo && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>Backend nicht erreichbar — es werden Demo-Daten angezeigt.</span>
        </div>
      )}
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
            {erntereifData && erntereifData.length > 0 && (
              <Badge variant="success">{erntereifData.length}</Badge>
            )}
          </div>
          <div className="card-body">
            {erntereifData?.length ? (
              <div className="space-y-3">
                {erntereifData.slice(0, 5).map((batch: GrowBatch) => (
                  <div
                    key={batch.id}
                    className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700"
                  >
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white">{batch.seed_name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {batch.tray_anzahl} Kisten | Optimal:{' '}
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
                {erntereifData.length > 5 && (
                  <a href="/production" className="flex items-center gap-1 text-sm text-minga-600 dark:text-minga-400 hover:text-minga-700">
                    Alle {erntereifData.length} anzeigen <ArrowRight className="w-4 h-4" />
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
                      ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700'
                      : 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-700'
                      }`}
                  >
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white">{suggestion.seed_name}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {suggestion.empfohlene_trays} Kisten | Aussaat:{' '}
                        {new Date(suggestion.aussaat_datum).toLocaleDateString('de-DE')}
                      </p>
                      {suggestion.warnungen?.map((w, i) => (
                        <p key={i} className="text-xs text-amber-600 dark:text-amber-400 mt-1">
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
                  <a href="/suggestions" className="flex items-center gap-1 text-sm text-minga-600 dark:text-minga-400 hover:text-minga-700">
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
              <div className="text-center p-4 bg-minga-50 dark:bg-minga-900/20 rounded-lg">
                <Scale className="w-8 h-8 text-minga-600 dark:text-minga-400 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {((dashboardData?.ernten_diese_woche_gramm || 0) / 1000).toFixed(1)} kg
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Ernte diese Woche</p>
              </div>
              <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {((dashboardData?.verluste_diese_woche_gramm || 0) / 1000).toFixed(1)} kg
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Verluste</p>
              </div>
              <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <TrendingUp className="w-8 h-8 text-blue-600 dark:text-blue-400 mx-auto mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {dashboardData?.erntereife_chargen || 0}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Chargen bereit</p>
              </div>
            </div>
          </div>
        </div>
      </div >

      {/* Role-Specific Section */}
      {showSalesSection && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Vertrieb & Finanzen</h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <Receipt className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                <div>
                  <p className="text-xl font-bold text-gray-900 dark:text-white">
                    {invoicesData?.length || 0}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Offene Rechnungen</p>
                </div>
              </div>
              <a href="/orders" className="flex items-center gap-3 p-4 bg-minga-50 dark:bg-minga-900/20 rounded-lg hover:bg-minga-100 dark:hover:bg-minga-900/30 transition-colors">
                <Calendar className="w-8 h-8 text-minga-600 dark:text-minga-400" />
                <div>
                  <p className="text-xl font-bold text-gray-900 dark:text-white">
                    {ordersData?.total || 0}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Offene Bestellungen</p>
                </div>
              </a>
              <a href="/customers" className="flex items-center gap-3 p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors">
                <Users className="w-8 h-8 text-purple-600 dark:text-purple-400" />
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">Kunden verwalten</span>
                  <ArrowRight className="w-4 h-4 text-gray-400" />
                </div>
              </a>
            </div>
          </div>
        </div>
      )}

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
