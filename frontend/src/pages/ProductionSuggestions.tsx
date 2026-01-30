import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, AlertTriangle, Calendar, Printer } from 'lucide-react';
import { forecastingApi } from '../services/api';
import { ProductionSuggestion, SuggestionStatus } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { ProductionSuggestionCard } from '../components/domain/ProductionSuggestionCard';
import { StatCard } from '../components/domain/StatCard';
import {
  Button,
  Select,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  useToast,
  SelectOption,
  formatDate,
  Badge,
  Alert,
} from '../components/ui';

const statusOptions: SelectOption[] = [
  { value: 'all', label: 'Alle Status' },
  { value: 'VORGESCHLAGEN', label: 'Vorgeschlagen' },
  { value: 'GENEHMIGT', label: 'Genehmigt' },
  { value: 'ABGELEHNT', label: 'Abgelehnt' },
  { value: 'UMGESETZT', label: 'Umgesetzt' },
];

export default function ProductionSuggestions() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('VORGESCHLAGEN');
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  // Fetch suggestions
  const { data: suggestionsData, isLoading } = useQuery({
    queryKey: ['production-suggestions', { status: statusFilter }],
    queryFn: () =>
      forecastingApi.listProductionSuggestions({
        status: statusFilter === 'all' ? undefined : (statusFilter as SuggestionStatus),
      }),
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (id: string) => forecastingApi.approveSuggestion(id),
    onSuccess: (data: ProductionSuggestion) => {
      queryClient.invalidateQueries({ queryKey: ['production-suggestions'] });

      if (data.generated_batch_id) {
        toast.success(
          <span>
            Produktionsvorschlag genehmigt.{' '}
            <a href="/production" className="underline font-bold">
              Zur Charge
            </a>
          </span>
        );
      } else {
        toast.success('Produktionsvorschlag genehmigt');
      }
      setApprovingId(null);
    },
    onError: () => {
      toast.error('Fehler beim Genehmigen');
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: (id: string) => forecastingApi.rejectSuggestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['production-suggestions'] });
      toast.info('Produktionsvorschlag abgelehnt');
      setRejectingId(null);
    },
    onError: () => {
      toast.error('Fehler beim Ablehnen');
    },
  });

  const suggestions = suggestionsData?.items || [];
  const pendingSuggestions = suggestions.filter((s) => s.status === 'VORGESCHLAGEN');
  const totalWarnings = suggestions.filter(
    (s) => s.warnungen && s.warnungen.length > 0
  ).length;

  // Group suggestions by sowing date
  const groupedBySowDate = suggestions.reduce((acc, suggestion) => {
    const date = suggestion.aussaat_datum;
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(suggestion);
    return acc;
  }, {} as Record<string, ProductionSuggestion[]>);

  const sortedDates = Object.keys(groupedBySowDate).sort();

  const handleApproveAll = async () => {
    for (const suggestion of pendingSuggestions) {
      await forecastingApi.approveSuggestion(suggestion.id);
    }
    queryClient.invalidateQueries({ queryKey: ['production-suggestions'] });
    toast.success(`${pendingSuggestions.length} Vorschläge genehmigt`);
  };

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Produktionsvorschläge"
        subtitle="Basierend auf Absatzprognosen"
        actions={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              icon={<Printer className="w-4 h-4" />}
              onClick={() => toast.info('Druckfunktion noch nicht implementiert')}
            >
              Aussaat-Liste drucken
            </Button>
            {pendingSuggestions.length > 0 && (
              <Button
                icon={<Check className="w-4 h-4" />}
                onClick={handleApproveAll}
              >
                Alle genehmigen ({pendingSuggestions.length})
              </Button>
            )}
          </div>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard
          title="Offene Vorschläge"
          value={pendingSuggestions.length}
          icon={<Calendar className="w-6 h-6" />}
        />
        <StatCard
          title="Mit Warnungen"
          value={totalWarnings}
          icon={<AlertTriangle className="w-6 h-6" />}
          className={totalWarnings > 0 ? 'border-amber-300 bg-amber-50/30' : ''}
        />
        <StatCard
          title="Diese Woche umgesetzt"
          value={suggestions.filter((s) => s.status === 'UMGESETZT').length}
          icon={<Check className="w-6 h-6" />}
        />
      </div>

      {totalWarnings > 0 && (
        <Alert variant="warning" className="mb-6">
          <strong>{totalWarnings} Vorschläge</strong> haben Warnungen. Bitte prüfe diese sorgfältig
          vor der Genehmigung.
        </Alert>
      )}

      <FilterBar>
        <Select
          options={statusOptions}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        />
      </FilterBar>

      {suggestions.length === 0 ? (
        <EmptyState
          title="Keine Produktionsvorschläge"
          description="Es gibt aktuell keine Vorschläge in dieser Kategorie."
        />
      ) : (
        <div className="space-y-8">
          {sortedDates.map((date) => (
            <div key={date}>
              <div className="flex items-center gap-3 mb-4">
                <Calendar className="w-5 h-5 text-gray-400" />
                <h2 className="text-lg font-semibold text-gray-900">
                  Aussaat: {formatDate(date, 'long')}
                </h2>
                <Badge variant="gray">{groupedBySowDate[date].length} Vorschläge</Badge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {groupedBySowDate[date].map((suggestion) => (
                  <ProductionSuggestionCard
                    key={suggestion.id}
                    suggestion={{
                      ...suggestion,
                      seed: { name: suggestion.seed_name } as any,
                    }}
                    onApprove={
                      suggestion.status === 'VORGESCHLAGEN'
                        ? () => setApprovingId(suggestion.id)
                        : undefined
                    }
                    onReject={
                      suggestion.status === 'VORGESCHLAGEN'
                        ? () => setRejectingId(suggestion.id)
                        : undefined
                    }
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Approve Confirmation */}
      <ConfirmDialog
        open={!!approvingId}
        onClose={() => setApprovingId(null)}
        onConfirm={() => approvingId && approveMutation.mutate(approvingId)}
        title="Vorschlag genehmigen?"
        message="Möchtest du diesen Produktionsvorschlag genehmigen? Die Aussaat kann dann gestartet werden."
        confirmLabel="Genehmigen"
        variant="info"
        loading={approveMutation.isPending}
      />

      {/* Reject Confirmation */}
      <ConfirmDialog
        open={!!rejectingId}
        onClose={() => setRejectingId(null)}
        onConfirm={() => rejectingId && rejectMutation.mutate(rejectingId)}
        title="Vorschlag ablehnen?"
        message="Möchtest du diesen Produktionsvorschlag ablehnen? Dies kann Auswirkungen auf die Lieferfähigkeit haben."
        confirmLabel="Ablehnen"
        variant="danger"
        loading={rejectMutation.isPending}
      />
    </div>
  );
}
