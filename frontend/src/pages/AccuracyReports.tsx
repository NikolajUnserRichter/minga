import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { accuracyApi, seedsApi } from '../services/api';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
    EmptyState,
    Input,
    InlineLoader,
    Badge,
} from '../components/ui';
import {
    BarChart3,
    TrendingUp,
    TrendingDown,
    Target,
    Calendar,
    Leaf,
    CheckCircle,
    AlertTriangle,
} from 'lucide-react';
import type { AccuracyDetail, AccuracySummary, Seed } from '../types';

export default function AccuracyReports() {
    // Date filters - default to last 30 days
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const [fromDate, setFromDate] = useState(thirtyDaysAgo.toISOString().split('T')[0]);
    const [toDate, setToDate] = useState(today.toISOString().split('T')[0]);
    const [seedFilter, setSeedFilter] = useState<string>('');

    // Data queries
    const { data: summaryData, isLoading: summaryLoading } = useQuery({
        queryKey: ['accuracy-summary', fromDate, toDate],
        queryFn: () =>
            accuracyApi.getSummary({
                von_datum: fromDate,
                bis_datum: toDate,
            }),
    });

    const { data: detailsData, isLoading: detailsLoading } = useQuery({
        queryKey: ['accuracy-details', fromDate, toDate, seedFilter],
        queryFn: () =>
            accuracyApi.getDetails({
                von_datum: fromDate,
                bis_datum: toDate,
                seed_id: seedFilter || undefined,
            }),
    });

    const { data: seedsData } = useQuery({
        queryKey: ['seeds', 'active'],
        queryFn: () => seedsApi.list({ aktiv: true }),
    });

    const seeds = seedsData?.items || [];
    const details = detailsData?.items || [];
    const summary = summaryData as AccuracySummary | undefined;

    const isLoading = summaryLoading || detailsLoading;

    // Helper to get accuracy badge color
    const getAccuracyBadge = (mape: number) => {
        if (mape <= 10) return <Badge variant="success">Sehr gut</Badge>;
        if (mape <= 20) return <Badge variant="info">Gut</Badge>;
        if (mape <= 30) return <Badge variant="warning">Mittel</Badge>;
        return <Badge variant="danger">Schlecht</Badge>;
    };

    // Helper to format percentage
    const formatPercent = (value: number | null | undefined) => {
        if (value === null || value === undefined) return '-';
        return `${value.toFixed(1)}%`;
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Accuracy Reports"
                subtitle="Forecast-Genauigkeit und Abweichungsanalyse"
            />

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                            <Target className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Durchschn. MAPE</p>
                            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                                {summary ? formatPercent(summary.durchschnittliche_mape) : '-'}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                            <TrendingUp className="w-6 h-6 text-green-600 dark:text-green-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Beste Genauigkeit</p>
                            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                                {summary ? formatPercent(summary.beste_genauigkeit) : '-'}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                            <TrendingDown className="w-6 h-6 text-red-600 dark:text-red-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Schlechteste</p>
                            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                                {summary ? formatPercent(summary.schlechteste_genauigkeit) : '-'}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                            <BarChart3 className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Anzahl Forecasts</p>
                            <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                                {summary?.anzahl_forecasts || 0}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <FilterBar>
                <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600 dark:text-gray-400">Von:</span>
                    <Input
                        type="date"
                        value={fromDate}
                        onChange={(e) => setFromDate(e.target.value)}
                        className="w-auto"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Bis:</span>
                    <Input
                        type="date"
                        value={toDate}
                        onChange={(e) => setToDate(e.target.value)}
                        className="w-auto"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <Leaf className="w-4 h-4 text-gray-400" />
                    <select
                        value={seedFilter}
                        onChange={(e) => setSeedFilter(e.target.value)}
                        className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-minga-500 focus:border-minga-500"
                    >
                        <option value="">Alle Produkte</option>
                        {seeds.map((seed: Seed) => (
                            <option key={seed.id} value={seed.id}>
                                {seed.name}
                            </option>
                        ))}
                    </select>
                </div>
                <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                        const newToday = new Date();
                        const newThirtyDaysAgo = new Date(newToday);
                        newThirtyDaysAgo.setDate(newThirtyDaysAgo.getDate() - 30);
                        setFromDate(newThirtyDaysAgo.toISOString().split('T')[0]);
                        setToDate(newToday.toISOString().split('T')[0]);
                        setSeedFilter('');
                    }}
                >
                    Zurücksetzen
                </button>
            </FilterBar>

            {/* Details Table */}
            {isLoading ? (
                <div className="flex items-center justify-center h-64">
                    <InlineLoader text="Lade Accuracy-Daten..." />
                </div>
            ) : details.length === 0 ? (
                <EmptyState
                    title="Keine Accuracy-Daten gefunden"
                    description="Im ausgewählten Zeitraum wurden keine Forecasts evaluiert."
                />
            ) : (
                <div className="card overflow-hidden">
                    <div className="p-4 border-b dark:border-gray-700">
                        <h3 className="font-semibold text-gray-900 dark:text-white">
                            Detaillierte Abweichungen
                        </h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {details.length} Forecasts im Zeitraum
                        </p>
                    </div>
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Datum</th>
                                <th>Produkt</th>
                                <th className="text-right">Prognose</th>
                                <th className="text-right">Effektiv</th>
                                <th className="text-right">Ist</th>
                                <th className="text-right">Abweichung</th>
                                <th className="text-center">MAPE</th>
                                <th className="text-center">Anpassung</th>
                                <th>Bewertung</th>
                            </tr>
                        </thead>
                        <tbody>
                            {details.map((detail: AccuracyDetail) => (
                                <tr key={detail.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                    <td className="font-medium">
                                        {new Date(detail.datum).toLocaleDateString('de-DE', {
                                            weekday: 'short',
                                            day: '2-digit',
                                            month: '2-digit',
                                        })}
                                    </td>
                                    <td>
                                        <div className="flex items-center gap-2">
                                            <Leaf className="w-4 h-4 text-green-500" />
                                            {detail.seed_name || '-'}
                                        </div>
                                    </td>
                                    <td className="text-right text-gray-500">
                                        {detail.prognostizierte_menge.toFixed(0)}g
                                    </td>
                                    <td className="text-right font-medium">
                                        {detail.effektive_menge.toFixed(0)}g
                                    </td>
                                    <td className="text-right font-semibold text-blue-600 dark:text-blue-400">
                                        {detail.ist_menge.toFixed(0)}g
                                    </td>
                                    <td className="text-right">
                                        <span
                                            className={
                                                detail.abweichung_absolut > 0
                                                    ? 'text-red-600 dark:text-red-400'
                                                    : detail.abweichung_absolut < 0
                                                    ? 'text-green-600 dark:text-green-400'
                                                    : 'text-gray-500'
                                            }
                                        >
                                            {detail.abweichung_absolut > 0 ? '+' : ''}
                                            {detail.abweichung_absolut.toFixed(0)}g
                                        </span>
                                    </td>
                                    <td className="text-center font-semibold">
                                        {formatPercent(detail.mape)}
                                    </td>
                                    <td className="text-center">
                                        {detail.hatte_manuelle_anpassung ? (
                                            <div className="flex justify-center" title="Mit manueller Anpassung">
                                                <CheckCircle className="w-4 h-4 text-blue-500" />
                                            </div>
                                        ) : (
                                            <span className="text-gray-400">-</span>
                                        )}
                                    </td>
                                    <td>{getAccuracyBadge(detail.mape)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Improvement Analysis */}
            {summary && summary.anzahl_mit_anpassung !== undefined && summary.anzahl_mit_anpassung > 0 && (
                <div className="card">
                    <div className="card-body">
                        <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-amber-500" />
                            Analyse: Manuelle Anpassungen
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Forecasts mit Anpassung
                                </p>
                                <p className="text-xl font-bold text-gray-900 dark:text-white">
                                    {summary.anzahl_mit_anpassung} / {summary.anzahl_forecasts}
                                </p>
                            </div>
                            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Anteil angepasst
                                </p>
                                <p className="text-xl font-bold text-gray-900 dark:text-white">
                                    {summary.anzahl_forecasts > 0
                                        ? ((summary.anzahl_mit_anpassung / summary.anzahl_forecasts) * 100).toFixed(1)
                                        : 0}
                                    %
                                </p>
                            </div>
                            <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Verbesserung durch Anpassung
                                </p>
                                <p className={`text-xl font-bold ${
                                    (summary.verbesserung_durch_anpassung || 0) > 0
                                        ? 'text-green-600 dark:text-green-400'
                                        : 'text-gray-900 dark:text-white'
                                }`}>
                                    {summary.verbesserung_durch_anpassung !== undefined
                                        ? `${summary.verbesserung_durch_anpassung > 0 ? '+' : ''}${summary.verbesserung_durch_anpassung.toFixed(1)}%`
                                        : '-'}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
