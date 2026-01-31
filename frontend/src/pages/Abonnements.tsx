import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { subscriptionsApi, salesApi, seedsApi } from '../services/api';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
    Modal,
    EmptyState,
    Input,
    useToast,
    InlineLoader,
    Badge,
} from '../components/ui';
import { Plus, RefreshCw, Calendar, User, Leaf, Trash2, Edit2, Play } from 'lucide-react';
import type { Subscription, Customer, Seed, SubscriptionInterval } from '../types';

const INTERVAL_LABELS: Record<SubscriptionInterval, string> = {
    TAEGLICH: 'Täglich',
    WOECHENTLICH: 'Wöchentlich',
    ZWEIWOECHENTLICH: 'Zweiwöchentlich',
    MONATLICH: 'Monatlich',
};

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

export default function Abonnements() {
    const toast = useToast();
    const queryClient = useQueryClient();

    // Filter state
    const [kundeFilter, setKundeFilter] = useState<string>('');
    const [aktivFilter, setAktivFilter] = useState<string>('');

    // Modal state
    const [isCreating, setIsCreating] = useState(false);
    const [editingSub, setEditingSub] = useState<Subscription | null>(null);
    const [deletingSub, setDeletingSub] = useState<Subscription | null>(null);

    // Form state
    const [formData, setFormData] = useState({
        kunde_id: '',
        seed_id: '',
        menge: '',
        einheit: 'GRAMM',
        intervall: 'WOECHENTLICH' as SubscriptionInterval,
        liefertage: [] as number[],
        gueltig_von: new Date().toISOString().split('T')[0],
        gueltig_bis: '',
    });

    // Data queries
    const { data: subscriptionsData, isLoading } = useQuery({
        queryKey: ['subscriptions', kundeFilter, aktivFilter],
        queryFn: () =>
            subscriptionsApi.list({
                kunde_id: kundeFilter || undefined,
                aktiv: aktivFilter === '' ? undefined : aktivFilter === 'true',
            }),
    });

    const { data: customersData } = useQuery({
        queryKey: ['customers', 'active'],
        queryFn: () => salesApi.listCustomers({ aktiv: true }),
    });

    const { data: seedsData } = useQuery({
        queryKey: ['seeds', 'active'],
        queryFn: () => seedsApi.list({ aktiv: true }),
    });

    // Mutations
    const createMutation = useMutation({
        mutationFn: (data: Parameters<typeof subscriptionsApi.create>[0]) =>
            subscriptionsApi.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setIsCreating(false);
            resetForm();
            toast.success('Abonnement erfolgreich erstellt');
        },
        onError: () => {
            toast.error('Fehler beim Erstellen des Abonnements');
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Parameters<typeof subscriptionsApi.update>[1] }) =>
            subscriptionsApi.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setEditingSub(null);
            resetForm();
            toast.success('Abonnement aktualisiert');
        },
        onError: () => {
            toast.error('Fehler beim Aktualisieren');
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => subscriptionsApi.update(id, { aktiv: false }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setDeletingSub(null);
            toast.success('Abonnement deaktiviert');
        },
        onError: () => {
            toast.error('Fehler beim Deaktivieren');
        },
    });

    const processMutation = useMutation({
        mutationFn: () => subscriptionsApi.processToday(),
        onSuccess: (result) => {
            toast.success(`Abonnements verarbeitet: ${result?.message || 'Erfolgreich'}`);
        },
        onError: () => {
            toast.error('Fehler bei der Verarbeitung');
        },
    });

    const resetForm = () => {
        setFormData({
            kunde_id: '',
            seed_id: '',
            menge: '',
            einheit: 'GRAMM',
            intervall: 'WOECHENTLICH',
            liefertage: [],
            gueltig_von: new Date().toISOString().split('T')[0],
            gueltig_bis: '',
        });
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (editingSub) {
            updateMutation.mutate({
                id: editingSub.id,
                data: {
                    menge: parseFloat(formData.menge),
                    einheit: formData.einheit,
                    intervall: formData.intervall,
                    liefertage: formData.liefertage,
                    gueltig_bis: formData.gueltig_bis || undefined,
                    aktiv: true,
                },
            });
        } else {
            createMutation.mutate({
                kunde_id: formData.kunde_id,
                seed_id: formData.seed_id,
                menge: parseFloat(formData.menge),
                einheit: formData.einheit,
                intervall: formData.intervall,
                liefertage: formData.liefertage.length > 0 ? formData.liefertage : undefined,
                gueltig_von: formData.gueltig_von,
                gueltig_bis: formData.gueltig_bis || undefined,
            });
        }
    };

    const openEditModal = (sub: Subscription) => {
        setFormData({
            kunde_id: sub.kunde_id,
            seed_id: sub.seed_id,
            menge: sub.menge.toString(),
            einheit: sub.einheit,
            intervall: sub.intervall,
            liefertage: sub.liefertage || [],
            gueltig_von: sub.gueltig_von,
            gueltig_bis: sub.gueltig_bis || '',
        });
        setEditingSub(sub);
    };

    const toggleLiefertag = (day: number) => {
        setFormData(prev => ({
            ...prev,
            liefertage: prev.liefertage.includes(day)
                ? prev.liefertage.filter(d => d !== day)
                : [...prev.liefertage, day].sort(),
        }));
    };

    // Derived data
    const subscriptions = subscriptionsData?.items || [];
    const customers = customersData?.items || [];
    const seeds = seedsData?.items || [];

    // Statistics
    const totalActive = subscriptions.filter(s => s.ist_aktiv).length;
    const totalInactive = subscriptions.filter(s => !s.ist_aktiv).length;

    const selectClassName = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-minga-500 focus:border-minga-500";

    return (
        <div className="space-y-6">
            <PageHeader
                title="Abonnements"
                subtitle={`${subscriptions.length} Abonnements, ${totalActive} aktiv`}
                actions={
                    <div className="flex gap-2">
                        <button
                            className="btn btn-secondary"
                            onClick={() => processMutation.mutate()}
                            disabled={processMutation.isPending}
                        >
                            <Play className="w-4 h-4" />
                            Heute verarbeiten
                        </button>
                        <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                            <Plus className="w-4 h-4" />
                            Neues Abonnement
                        </button>
                    </div>
                }
            />

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                            <RefreshCw className="w-6 h-6 text-green-600 dark:text-green-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Aktive Abonnements</p>
                            <p className="text-2xl font-bold text-green-600 dark:text-green-400">{totalActive}</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
                            <RefreshCw className="w-6 h-6 text-gray-600 dark:text-gray-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Inaktive Abonnements</p>
                            <p className="text-2xl font-bold text-gray-600 dark:text-gray-400">{totalInactive}</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                            <User className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Kunden mit Abo</p>
                            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                                {new Set(subscriptions.map(s => s.kunde_id)).size}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <FilterBar>
                <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-400" />
                    <select
                        value={kundeFilter}
                        onChange={(e) => setKundeFilter(e.target.value)}
                        className={`${selectClassName} w-48`}
                    >
                        <option value="">Alle Kunden</option>
                        {customers.map((customer: Customer) => (
                            <option key={customer.id} value={customer.id}>
                                {customer.name}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={aktivFilter}
                        onChange={(e) => setAktivFilter(e.target.value)}
                        className={`${selectClassName} w-40`}
                    >
                        <option value="">Alle Status</option>
                        <option value="true">Nur Aktive</option>
                        <option value="false">Nur Inaktive</option>
                    </select>
                </div>
            </FilterBar>

            {/* Subscriptions Table */}
            {isLoading ? (
                <div className="flex items-center justify-center h-64">
                    <InlineLoader text="Lade Abonnements..." />
                </div>
            ) : subscriptions.length === 0 ? (
                <EmptyState
                    title="Keine Abonnements gefunden"
                    description="Erstellen Sie ein neues Abonnement für wiederkehrende Bestellungen."
                    action={
                        <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                            <Plus className="w-4 h-4" />
                            Erstes Abonnement erstellen
                        </button>
                    }
                />
            ) : (
                <div className="card overflow-hidden">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Kunde</th>
                                <th>Produkt</th>
                                <th className="text-right">Menge</th>
                                <th>Intervall</th>
                                <th>Liefertage</th>
                                <th>Gültigkeit</th>
                                <th>Status</th>
                                <th className="text-right">Aktionen</th>
                            </tr>
                        </thead>
                        <tbody>
                            {subscriptions.map((sub: Subscription) => (
                                <tr key={sub.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                    <td className="font-medium">
                                        <div className="flex items-center gap-2">
                                            <User className="w-4 h-4 text-gray-400" />
                                            {sub.kunde_name || sub.kunde_id.slice(0, 8)}
                                        </div>
                                    </td>
                                    <td>
                                        <div className="flex items-center gap-2">
                                            <Leaf className="w-4 h-4 text-green-500" />
                                            {sub.seed_name || sub.seed_id.slice(0, 8)}
                                        </div>
                                    </td>
                                    <td className="text-right font-semibold">
                                        {sub.menge} {sub.einheit}
                                    </td>
                                    <td>
                                        <Badge variant="info">
                                            {INTERVAL_LABELS[sub.intervall]}
                                        </Badge>
                                    </td>
                                    <td>
                                        {sub.liefertage && sub.liefertage.length > 0 ? (
                                            <div className="flex gap-1">
                                                {sub.liefertage.map(day => (
                                                    <span
                                                        key={day}
                                                        className="px-1.5 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 rounded"
                                                    >
                                                        {WEEKDAYS[day]}
                                                    </span>
                                                ))}
                                            </div>
                                        ) : (
                                            <span className="text-gray-400">-</span>
                                        )}
                                    </td>
                                    <td className="text-sm text-gray-500">
                                        <div className="flex items-center gap-1">
                                            <Calendar className="w-3 h-3" />
                                            {new Date(sub.gueltig_von).toLocaleDateString('de-DE')}
                                            {sub.gueltig_bis && (
                                                <> - {new Date(sub.gueltig_bis).toLocaleDateString('de-DE')}</>
                                            )}
                                        </div>
                                    </td>
                                    <td>
                                        <Badge variant={sub.ist_aktiv ? 'success' : 'gray'}>
                                            {sub.ist_aktiv ? 'Aktiv' : 'Inaktiv'}
                                        </Badge>
                                    </td>
                                    <td className="text-right">
                                        <div className="flex justify-end gap-1">
                                            <button
                                                className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                                                onClick={() => openEditModal(sub)}
                                                title="Bearbeiten"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                                                onClick={() => setDeletingSub(sub)}
                                                title="Deaktivieren"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create/Edit Modal */}
            <Modal
                open={isCreating || !!editingSub}
                onClose={() => {
                    setIsCreating(false);
                    setEditingSub(null);
                    resetForm();
                }}
                title={editingSub ? 'Abonnement bearbeiten' : 'Neues Abonnement'}
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    {!editingSub && (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Kunde *
                                </label>
                                <select
                                    value={formData.kunde_id}
                                    onChange={(e) => setFormData({ ...formData, kunde_id: e.target.value })}
                                    required
                                    className={selectClassName}
                                >
                                    <option value="">Kunde auswählen...</option>
                                    {customers.map((customer: Customer) => (
                                        <option key={customer.id} value={customer.id}>
                                            {customer.name}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Produkt *
                                </label>
                                <select
                                    value={formData.seed_id}
                                    onChange={(e) => setFormData({ ...formData, seed_id: e.target.value })}
                                    required
                                    className={selectClassName}
                                >
                                    <option value="">Produkt auswählen...</option>
                                    {seeds.map((seed: Seed) => (
                                        <option key={seed.id} value={seed.id}>
                                            {seed.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Menge *
                            </label>
                            <Input
                                type="number"
                                step="0.01"
                                min="0"
                                value={formData.menge}
                                onChange={(e) => setFormData({ ...formData, menge: e.target.value })}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Einheit *
                            </label>
                            <select
                                value={formData.einheit}
                                onChange={(e) => setFormData({ ...formData, einheit: e.target.value })}
                                className={selectClassName}
                            >
                                <option value="GRAMM">Gramm</option>
                                <option value="BUND">Bund</option>
                                <option value="SCHALE">Schale</option>
                                <option value="STUECK">Stück</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Intervall *
                        </label>
                        <select
                            value={formData.intervall}
                            onChange={(e) => setFormData({ ...formData, intervall: e.target.value as SubscriptionInterval })}
                            className={selectClassName}
                        >
                            {Object.entries(INTERVAL_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Liefertage
                        </label>
                        <div className="flex gap-2">
                            {WEEKDAYS.map((day, index) => (
                                <button
                                    key={index}
                                    type="button"
                                    onClick={() => toggleLiefertag(index)}
                                    className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                                        formData.liefertage.includes(index)
                                            ? 'bg-minga-500 text-white border-minga-500'
                                            : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-minga-300'
                                    }`}
                                >
                                    {day}
                                </button>
                            ))}
                        </div>
                    </div>

                    {!editingSub && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Gültig ab *
                            </label>
                            <Input
                                type="date"
                                value={formData.gueltig_von}
                                onChange={(e) => setFormData({ ...formData, gueltig_von: e.target.value })}
                                required
                            />
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Gültig bis (optional)
                        </label>
                        <Input
                            type="date"
                            value={formData.gueltig_bis}
                            onChange={(e) => setFormData({ ...formData, gueltig_bis: e.target.value })}
                        />
                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t dark:border-gray-700">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => {
                                setIsCreating(false);
                                setEditingSub(null);
                                resetForm();
                            }}
                        >
                            Abbrechen
                        </button>
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={createMutation.isPending || updateMutation.isPending}
                        >
                            {editingSub ? 'Speichern' : 'Erstellen'}
                        </button>
                    </div>
                </form>
            </Modal>

            {/* Delete Confirmation Modal */}
            <Modal
                open={!!deletingSub}
                onClose={() => setDeletingSub(null)}
                title="Abonnement deaktivieren"
            >
                <div className="space-y-4">
                    <p className="text-gray-600 dark:text-gray-400">
                        Möchten Sie das Abonnement für{' '}
                        <strong>{deletingSub?.kunde_name}</strong> ({deletingSub?.seed_name}) wirklich
                        deaktivieren?
                    </p>
                    <div className="flex justify-end gap-3">
                        <button className="btn btn-secondary" onClick={() => setDeletingSub(null)}>
                            Abbrechen
                        </button>
                        <button
                            className="btn btn-danger"
                            onClick={() => deletingSub && deleteMutation.mutate(deletingSub.id)}
                            disabled={deleteMutation.isPending}
                        >
                            Deaktivieren
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}
