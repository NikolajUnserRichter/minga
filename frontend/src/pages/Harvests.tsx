import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productionApi } from '../services/api';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { HarvestForm } from '../components/domain/HarvestForm';
import {
    Modal,
    EmptyState,
    Input,
    useToast,
    InlineLoader,
} from '../components/ui';
import { Plus, Scissors, Star, TrendingDown, Scale, Calendar } from 'lucide-react';
import type { Harvest, GrowBatch } from '../types';

export default function Harvests() {
    const toast = useToast();
    const queryClient = useQueryClient();

    // Date filters - default to last 30 days
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const [fromDate, setFromDate] = useState(thirtyDaysAgo.toISOString().split('T')[0]);
    const [toDate, setToDate] = useState(today.toISOString().split('T')[0]);

    // Modal state
    const [isCreating, setIsCreating] = useState(false);
    const [selectedBatch, setSelectedBatch] = useState<GrowBatch | null>(null);

    // Data queries
    const { data: harvestsData, isLoading } = useQuery({
        queryKey: ['harvests', fromDate, toDate],
        queryFn: () =>
            productionApi.listHarvests({
                von_datum: fromDate || undefined,
                bis_datum: toDate || undefined,
            }),
    });

    // Grow batches for creating new harvests
    const { data: batchesData } = useQuery({
        queryKey: ['growBatches', 'harvestable'],
        queryFn: () =>
            productionApi.listGrowBatches({
                status: 'ERNTEREIF',
            }),
        enabled: isCreating,
    });

    // Create mutation
    const createMutation = useMutation({
        mutationFn: (data: {
            grow_batch_id: string;
            ernte_datum: string;
            menge_gramm: number;
            verlust_gramm?: number;
            qualitaet_note?: number;
        }) => productionApi.createHarvest(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['harvests'] });
            queryClient.invalidateQueries({ queryKey: ['growBatches'] });
            setIsCreating(false);
            setSelectedBatch(null);
            toast.success('Ernte erfolgreich erfasst');
        },
        onError: () => {
            toast.error('Fehler beim Speichern der Ernte');
        },
    });

    // Derived data
    const harvests = harvestsData?.items || harvestsData || [];
    const harvestableMatches = batchesData?.items || [];

    // Statistics
    const totalHarvestKg = (Array.isArray(harvests) ? harvests : []).reduce(
        (sum: number, h: Harvest) => sum + (h.menge_gramm || 0),
        0
    ) / 1000;

    const totalLossKg = (Array.isArray(harvests) ? harvests : []).reduce(
        (sum: number, h: Harvest) => sum + (h.verlust_gramm || 0),
        0
    ) / 1000;

    const avgQuality = (Array.isArray(harvests) ? harvests : []).reduce(
        (sum: number, h: Harvest) => sum + (h.qualitaet_note || 0),
        0
    ) / ((Array.isArray(harvests) && harvests.length > 0) ? harvests.filter((h: Harvest) => h.qualitaet_note).length : 1) || 0;

    const avgLossPercent = totalHarvestKg > 0
        ? (totalLossKg / (totalHarvestKg + totalLossKg)) * 100
        : 0;

    // Render quality stars
    const renderStars = (rating: number | null) => {
        if (!rating) return <span className="text-gray-400">-</span>;
        return (
            <div className="flex gap-0.5">
                {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                        key={star}
                        className={`w-4 h-4 ${star <= rating ? 'text-amber-400 fill-amber-400' : 'text-gray-300'
                            }`}
                    />
                ))}
            </div>
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Ernten"
                subtitle={`${(Array.isArray(harvests) ? harvests : []).length} Ernten im Zeitraum`}
                actions={
                    <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                        <Plus className="w-4 h-4" />
                        Neue Ernte
                    </button>
                }
            />

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-green-100 rounded-lg">
                            <Scale className="w-6 h-6 text-green-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Gesamtertrag</p>
                            <p className="text-2xl font-bold text-green-600">{totalHarvestKg.toFixed(1)} kg</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-red-100 rounded-lg">
                            <TrendingDown className="w-6 h-6 text-red-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Gesamtverlust</p>
                            <p className="text-2xl font-bold text-red-600">{totalLossKg.toFixed(2)} kg</p>
                            <p className="text-xs text-gray-400">{avgLossPercent.toFixed(1)}%</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-amber-100 rounded-lg">
                            <Star className="w-6 h-6 text-amber-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Ø Qualität</p>
                            <p className="text-2xl font-bold text-amber-600">{avgQuality.toFixed(1)}</p>
                            <div className="flex gap-0.5 mt-1">
                                {renderStars(Math.round(avgQuality))}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-blue-100 rounded-lg">
                            <Scissors className="w-6 h-6 text-blue-600" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500">Anzahl Ernten</p>
                            <p className="text-2xl font-bold text-blue-600">{(Array.isArray(harvests) ? harvests : []).length}</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Date Filters */}
            <FilterBar>
                <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">Von:</span>
                    <Input
                        type="date"
                        value={fromDate}
                        onChange={(e) => setFromDate(e.target.value)}
                        className="w-auto"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">Bis:</span>
                    <Input
                        type="date"
                        value={toDate}
                        onChange={(e) => setToDate(e.target.value)}
                        className="w-auto"
                    />
                </div>
                <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                        const newToday = new Date();
                        const newThirtyDaysAgo = new Date(newToday);
                        newThirtyDaysAgo.setDate(newThirtyDaysAgo.getDate() - 30);
                        setFromDate(newThirtyDaysAgo.toISOString().split('T')[0]);
                        setToDate(newToday.toISOString().split('T')[0]);
                    }}
                >
                    Letzte 30 Tage
                </button>
            </FilterBar>

            {/* Harvests Table */}
            {isLoading ? (
                <div className="flex items-center justify-center h-64">
                    <InlineLoader text="Lade Ernten..." />
                </div>
            ) : (Array.isArray(harvests) ? harvests : []).length === 0 ? (
                <EmptyState
                    title="Keine Ernten gefunden"
                    description="Im ausgewählten Zeitraum wurden keine Ernten erfasst."
                    action={
                        <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                            <Plus className="w-4 h-4" />
                            Erste Ernte erfassen
                        </button>
                    }
                />
            ) : (
                <div className="card overflow-hidden">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Datum</th>
                                <th>Charge ID</th>
                                <th className="text-right">Menge</th>
                                <th className="text-right">Verlust</th>
                                <th className="text-right">Verlustquote</th>
                                <th>Qualität</th>
                                <th>Erfasst am</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(Array.isArray(harvests) ? harvests : []).map((harvest: Harvest) => (
                                <tr key={harvest.id} className="hover:bg-gray-50">
                                    <td className="font-medium">
                                        {new Date(harvest.ernte_datum).toLocaleDateString('de-DE', {
                                            weekday: 'short',
                                            day: '2-digit',
                                            month: '2-digit',
                                            year: 'numeric',
                                        })}
                                    </td>
                                    <td>
                                        <a
                                            href={`/production?highlight=${harvest.grow_batch_id}`}
                                            className="text-minga-600 hover:text-minga-700 hover:underline font-mono text-sm"
                                        >
                                            {harvest.grow_batch_id.slice(0, 8)}...
                                        </a>
                                    </td>
                                    <td className="text-right font-semibold text-green-600">
                                        {(harvest.menge_gramm / 1000).toFixed(2)} kg
                                    </td>
                                    <td className="text-right text-red-600">
                                        {harvest.verlust_gramm > 0
                                            ? `${(harvest.verlust_gramm / 1000).toFixed(3)} kg`
                                            : '-'}
                                    </td>
                                    <td className="text-right">
                                        {harvest.verlustquote > 0 ? (
                                            <span
                                                className={`${harvest.verlustquote > 10 ? 'text-red-600' : 'text-gray-600'
                                                    }`}
                                            >
                                                {Number(harvest.verlustquote).toFixed(1)}%
                                            </span>
                                        ) : (
                                            '-'
                                        )}
                                    </td>
                                    <td>{renderStars(harvest.qualitaet_note)}</td>
                                    <td className="text-gray-500 text-sm">
                                        {new Date(harvest.created_at).toLocaleString('de-DE', {
                                            day: '2-digit',
                                            month: '2-digit',
                                            hour: '2-digit',
                                            minute: '2-digit',
                                        })}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create Harvest Modal */}
            <Modal
                open={isCreating && !selectedBatch}
                onClose={() => setIsCreating(false)}
                title="Ernte erfassen"
                size="lg"
            >
                <div className="space-y-4">
                    <p className="text-gray-600">
                        Wähle eine erntereife Charge aus:
                    </p>

                    {harvestableMatches.length === 0 ? (
                        <EmptyState
                            title="Keine erntereifen Chargen"
                            description="Es gibt aktuell keine Chargen mit Status 'Erntereif'."
                        />
                    ) : (
                        <div className="grid gap-3 max-h-96 overflow-y-auto">
                            {harvestableMatches.map((batch: GrowBatch) => (
                                <button
                                    key={batch.id}
                                    onClick={() => setSelectedBatch(batch)}
                                    className="p-4 border border-gray-200 rounded-lg hover:border-minga-300 hover:bg-minga-50 transition-colors text-left"
                                >
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <p className="font-semibold text-gray-900">{batch.seed_name || 'Unbekannt'}</p>
                                            <p className="text-sm text-gray-500">
                                                {batch.tray_anzahl} Trays | Position: {batch.regal_position || '-'}
                                            </p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-sm font-medium text-green-600">
                                                Erntereif
                                            </p>
                                            <p className="text-xs text-gray-400">
                                                Tag {batch.tage_seit_aussaat}
                                            </p>
                                        </div>
                                    </div>
                                    <p className="text-xs text-gray-400 mt-2 font-mono">
                                        ID: {batch.id.slice(0, 8)}...
                                    </p>
                                </button>
                            ))}
                        </div>
                    )}

                    <div className="flex justify-end pt-4 border-t">
                        <button className="btn btn-secondary" onClick={() => setIsCreating(false)}>
                            Abbrechen
                        </button>
                    </div>
                </div>
            </Modal>

            {/* Harvest Form Modal */}
            <Modal
                open={!!selectedBatch}
                onClose={() => setSelectedBatch(null)}
                title={`Ernte: ${selectedBatch?.seed_name || 'Charge'}`}
            >
                {selectedBatch && (
                    <HarvestForm
                        batch={selectedBatch as any}
                        loading={createMutation.isPending}
                        onSubmit={(data) => {
                            createMutation.mutate({
                                grow_batch_id: selectedBatch.id,
                                ernte_datum: data.ernte_datum,
                                menge_gramm: data.menge_gramm,
                                verlust_gramm: data.verlust_gramm,
                                qualitaet_note: data.qualitaet_note,
                            });
                        }}
                        onCancel={() => setSelectedBatch(null)}
                    />
                )}
            </Modal>
        </div>
    );
}
