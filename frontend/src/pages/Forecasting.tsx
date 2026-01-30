import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { forecastingApi, seedsApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { StatCard } from '../components/domain/StatCard';
import { ForecastOverrideForm } from '../components/domain/ForecastOverrideForm';
import {
  Select,
  Modal,
  PageLoader,
  EmptyState,
  Badge,
  useToast,
  SelectOption,
  Button,
} from '../components/ui';
import {
  TrendingUp,
  RefreshCw,
  Check,
  X,
  AlertTriangle,
  BarChart3,
  Edit2,
} from 'lucide-react';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';
import type { Forecast, ProductionSuggestion, Seed } from '../types';

export default function Forecasting() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [selectedSeed, setSelectedSeed] = useState<string>('');
  const [overrideForecast, setOverrideForecast] = useState<Forecast | null>(null);

  const { data: seedsData } = useQuery({
    queryKey: ['seeds', 'active'],
    queryFn: () => seedsApi.list({ aktiv: true }),
  });

  const { data: suggestionsData, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['suggestions'],
    queryFn: () => forecastingApi.listProductionSuggestions(),
  });

  const { data: forecastsData, isLoading: forecastsLoading } = useQuery({
    queryKey: ['forecasts', selectedSeed],
    queryFn: () =>
      forecastingApi.listForecasts({
        seed_id: selectedSeed || undefined,
      }),
    enabled: !!selectedSeed,
  });

  const { data: accuracyData } = useQuery({
    queryKey: ['accuracy'],
    queryFn: () => forecastingApi.getAccuracySummary(),
  });

  const generateMutation = useMutation({
    mutationFn: () => forecastingApi.generateProductionSuggestions(14),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] });
      queryClient.invalidateQueries({ queryKey: ['forecasts'] });
      toast.success('Forecasts generiert');
    },
    onError: () => {
      toast.error('Fehler beim Generieren');
    },
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

  const rejectMutation = useMutation({
    mutationFn: (id: string) => forecastingApi.rejectSuggestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] });
      toast.success('Vorschlag abgelehnt');
    },
    onError: () => {
      toast.error('Fehler beim Ablehnen');
    },
  });

  const seedOptions: SelectOption[] = [
    { value: '', label: 'Produkt wählen...' },
    ...(seedsData?.items?.map((seed: Seed) => ({
      value: seed.id,
      label: seed.name,
    })) || []),
  ];

  // Chart data
  const chartData =
    forecastsData?.items?.map((f: Forecast) => ({
      datum: new Date(f.datum).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }),
      prognose: f.effektive_menge || f.prognostizierte_menge,
      untergrenze: f.konfidenz_untergrenze,
      obergrenze: f.konfidenz_obergrenze,
      override: f.override_menge,
    })) || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Forecasting"
        subtitle="Absatzprognosen und Produktionsplanung"
        actions={
          <Button
            onClick={() => generateMutation.mutate()}
            loading={generateMutation.isPending}
            icon={<RefreshCw className="w-4 h-4" />}
          >
            Forecasts generieren
          </Button>
        }
      />

      {/* Accuracy Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Ø MAPE"
          value={`${accuracyData?.durchschnitt_mape?.toFixed(1) || '-'}%`}
          icon={<BarChart3 className="w-5 h-5" />}
          variant="primary"
        />
        <StatCard
          title="Beste Genauigkeit"
          value={`${accuracyData?.beste_genauigkeit?.toFixed(1) || '-'}%`}
          icon={<TrendingUp className="w-5 h-5" />}
          variant="success"
        />
        <StatCard
          title="Warnungen"
          value={suggestionsData?.warnungen_gesamt || 0}
          icon={<AlertTriangle className="w-5 h-5" />}
          variant="warning"
        />
        <StatCard
          title="Offene Vorschläge"
          value={suggestionsData?.items?.filter((s: ProductionSuggestion) => s.status === 'VORGESCHLAGEN').length || 0}
          icon={<Check className="w-5 h-5" />}
          variant="info"
        />
      </div>

      {/* Forecast Chart */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Absatzprognose</h3>
          <Select
            options={seedOptions}
            value={selectedSeed}
            onChange={(e) => setSelectedSeed(e.target.value)}
            className="w-48"
          />
        </div>
        <div className="card-body">
          {selectedSeed && !forecastsLoading ? (
            chartData.length > 0 ? (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="datum" tick={{ fontSize: 12 }} stroke="#9ca3af" />
                    <YAxis tick={{ fontSize: 12 }} unit="g" stroke="#9ca3af" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                      }}
                      formatter={(value: number, name: string) => [
                        `${value?.toFixed(0) || '-'}g`,
                        name === 'prognose'
                          ? 'Prognose'
                          : name === 'override'
                            ? 'Override'
                            : name,
                      ]}
                      labelFormatter={(label) => `Datum: ${label}`}
                    />
                    <Area
                      type="monotone"
                      dataKey="obergrenze"
                      stroke="none"
                      fill="#dcfce7"
                      name="Konfidenz oben"
                    />
                    <Area
                      type="monotone"
                      dataKey="untergrenze"
                      stroke="none"
                      fill="#ffffff"
                      name="Konfidenz unten"
                    />
                    <Line
                      type="monotone"
                      dataKey="prognose"
                      stroke="#16a34a"
                      strokeWidth={2}
                      dot={{ fill: '#16a34a', r: 4 }}
                      name="prognose"
                    />
                    <Line
                      type="monotone"
                      dataKey="override"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={{ fill: '#f59e0b', r: 4 }}
                      name="override"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState
                title="Keine Forecast-Daten"
                description="Klicken Sie auf 'Forecasts generieren' um Prognosen zu erstellen."
                action={
                  <Button
                    onClick={() => generateMutation.mutate()}
                    loading={generateMutation.isPending}
                  >
                    Forecasts generieren
                  </Button>
                }
              />
            )
          ) : (
            <div className="flex items-center justify-center h-80 text-gray-500">
              Wählen Sie ein Produkt um die Prognose anzuzeigen
            </div>
          )}
        </div>
      </div>

      {/* Forecasts Table with Override */}
      {selectedSeed && (forecastsData?.items || []).length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Forecast-Details</h3>
          </div>
          <div className="card-body overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Prognose</th>
                  <th>Konfidenz</th>
                  <th>Override</th>
                  <th>Effektiv</th>
                  <th>Modell</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {(forecastsData?.items || []).map((forecast: Forecast) => (
                  <tr key={forecast.id} className={forecast.override_menge ? 'bg-amber-50' : ''}>
                    <td>{new Date(forecast.datum).toLocaleDateString('de-DE')}</td>
                    <td>{forecast.prognostizierte_menge?.toFixed(0)}g</td>
                    <td className="text-gray-500 text-sm">
                      {forecast.konfidenz_untergrenze?.toFixed(0)} -{' '}
                      {forecast.konfidenz_obergrenze?.toFixed(0)}g
                    </td>
                    <td>
                      {forecast.override_menge ? (
                        <span className="text-amber-600 font-medium">
                          {forecast.override_menge.toFixed(0)}g
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="font-medium">
                      {(forecast.effektive_menge || forecast.prognostizierte_menge)?.toFixed(0)}g
                    </td>
                    <td>
                      <Badge variant="gray">{forecast.modell_typ}</Badge>
                    </td>
                    <td>
                      <button
                        onClick={() => setOverrideForecast(forecast)}
                        className="text-minga-600 hover:text-minga-700"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Production Suggestions */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Produktionsvorschläge ({suggestionsData?.total || 0})</h3>
          {(suggestionsData?.warnungen_gesamt || 0) > 0 && (
            <Badge variant="warning">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {suggestionsData?.warnungen_gesamt || 0} Warnungen
            </Badge>
          )}
        </div>
        <div className="card-body">
          {suggestionsLoading ? (
            <PageLoader />
          ) : suggestionsData?.items?.length ? (
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Produkt</th>
                    <th>Trays</th>
                    <th>Aussaat</th>
                    <th>Ernte</th>
                    <th>Status</th>
                    <th>Warnungen</th>
                    <th>Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {suggestionsData.items.map((suggestion: ProductionSuggestion) => (
                    <tr
                      key={suggestion.id}
                      className={suggestion.warnungen?.length ? 'bg-amber-50' : ''}
                    >
                      <td className="font-medium">{suggestion.seed_name}</td>
                      <td>{suggestion.empfohlene_trays}</td>
                      <td>{new Date(suggestion.aussaat_datum).toLocaleDateString('de-DE')}</td>
                      <td>{new Date(suggestion.erwartete_ernte_datum).toLocaleDateString('de-DE')}</td>
                      <td>
                        <Badge
                          variant={
                            suggestion.status === 'GENEHMIGT'
                              ? 'success'
                              : suggestion.status === 'ABGELEHNT'
                                ? 'danger'
                                : 'gray'
                          }
                        >
                          {suggestion.status}
                        </Badge>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {suggestion.warnungen?.map((w, i) => (
                            <Badge key={i} variant="warning" size="sm">
                              {w.typ}
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td>
                        {suggestion.status === 'VORGESCHLAGEN' && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => approveMutation.mutate(suggestion.id)}
                              disabled={approveMutation.isPending}
                              className="p-1 text-green-600 hover:bg-green-100 rounded"
                              title="Genehmigen"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => rejectMutation.mutate(suggestion.id)}
                              disabled={rejectMutation.isPending}
                              className="p-1 text-red-600 hover:bg-red-100 rounded"
                              title="Ablehnen"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="Keine Produktionsvorschläge"
              description="Generieren Sie Forecasts um Produktionsvorschläge zu erhalten."
            />
          )}
        </div>
      </div>

      {/* Override Modal */}
      <Modal
        open={!!overrideForecast}
        onClose={() => setOverrideForecast(null)}
        title="Forecast Override"
      >
        {overrideForecast && (
          <ForecastOverrideForm
            forecast={overrideForecast}
            onSubmit={() => {
              queryClient.invalidateQueries({ queryKey: ['forecasts'] });
              setOverrideForecast(null);
              toast.success('Override gespeichert');
            }}
            onCancel={() => setOverrideForecast(null)}
          />
        )}
      </Modal>
    </div>
  );
}
