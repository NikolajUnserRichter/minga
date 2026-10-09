import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { subscriptionsApi, salesApi, seedsApi, productsApi } from '../services/api';
import { getErrorMessage } from '../services/errors';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
    Modal,
    EmptyState,
    Input,
    Combobox,
    useToast,
    InlineLoader,
    Badge,
} from '../components/ui';
import { Plus, RefreshCw, Calendar, User, Leaf, Trash2, Edit2, Play, X } from 'lucide-react';
import type { Subscription, SubscriptionPosition, Customer, Seed, SubscriptionInterval, ProductVariant } from '../types';

const INTERVAL_LABELS: Record<SubscriptionInterval, string> = {
    TAEGLICH: 'Täglich',
    WOECHENTLICH: 'Wöchentlich',
    ZWEIWOECHENTLICH: 'Zweiwöchentlich',
    MONATLICH: 'Monatlich',
};

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

// Einheiten der Abo-Position (wie bisher im Formular)
const EINHEITEN: Array<{ value: string; label: string }> = [
    { value: 'GRAMM', label: 'Gramm' },
    { value: 'BUND', label: 'Bund' },
    { value: 'SCHALE', label: 'Schale' },
    { value: 'STUECK', label: 'Stück' },
    { value: 'TRAY', label: 'Tray (8 Schalen)' },
    { value: 'KISTE_12', label: 'Mehrwegkiste (12 Schalen)' },
    { value: 'KISTE_6', label: 'Mehrwegkiste (6 Schalen)' },
    { value: 'KARTON_6', label: 'Karton (6 Schalen)' },
];

const einheitLabel = (code: string) => EINHEITEN.find(e => e.value === code)?.label ?? code;

// Eine Zeile im Formular. Kein Preis: der Abo-Lauf nimmt Sonderpreis,
// Variantenpreis bzw. Basispreis wie das Bestellformular (B6).
interface PositionRow {
    product_id: string;
    product_variant_id: string;
    seed_id: string;
    menge: string;
    einheit: string;
    /** Anzeigename der gespeicherten Position (nur Bearbeiten), falls ihr Produkt nicht mehr wählbar ist */
    bisher?: string;
}

const leerePosition = (): PositionRow => ({
    product_id: '',
    product_variant_id: '',
    seed_id: '',
    menge: '',
    einheit: 'STUECK',
});

const heuteIso = () => new Date().toISOString().split('T')[0];

const leeresFormular = () => ({
    kunde_id: '',
    intervall: 'WOECHENTLICH' as SubscriptionInterval,
    liefertage: [] as number[],
    gueltig_von: heuteIso(),
    gueltig_bis: '',
    // Nur im Bearbeiten-Dialog sichtbar; Speichern ändert den Status nur über diesen Schalter
    aktiv: true,
    positionen: [leerePosition()],
});

// Positionen eines Abos für Tabelle und Dialoge; ohne Positionen (vor B6) der Kopf
const positionenVon = (sub: Subscription): Array<Pick<SubscriptionPosition, 'menge' | 'einheit' | 'bezeichnung'>> =>
    sub.positionen && sub.positionen.length > 0
        ? sub.positionen
        : [{ menge: sub.menge, einheit: sub.einheit, bezeichnung: sub.product_name || sub.seed_name || null }];

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
    const [formData, setFormData] = useState(leeresFormular);
    const [variantenJeProdukt, setVariantenJeProdukt] = useState<Record<string, ProductVariant[]>>({});

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

    const { data: productsData } = useQuery({
        queryKey: ['products', 'active'],
        queryFn: () => productsApi.list({ is_active: true }),
    });
    const products = productsData || [];
    // Variable Bundles (Gastrotray mit Sortenwahl) brauchen eine Auswahl je
    // Bestellung; ein Abo hat keine, die API lehnt sie ab.
    const produktOptionen = products
        .filter((p) => !p.is_variable_bundle)
        .map((p) => ({ value: p.id, label: `${p.is_bundle ? '📦 ' : ''}${p.name}` }));
    // Ein gespeichertes Produkt, das nicht mehr wählbar ist (deaktiviert oder
    // inzwischen variables Bundle), bleibt sichtbar statt eines leeren Felds.
    const produktOptionenFuer = (pos: PositionRow) =>
        !productsData || !pos.product_id || produktOptionen.some((o) => o.value === pos.product_id)
            ? produktOptionen
            : [
                { value: pos.product_id, label: pos.bisher || 'Bisheriges Produkt', hint: 'nicht mehr wählbar', disabled: true },
                ...produktOptionen,
            ];

    const { data: seedsData } = useQuery({
        queryKey: ['seeds', 'active'],
        queryFn: () => seedsApi.list({ aktiv: true }),
    });

    const ladeVarianten = async (productId: string) => {
        if (!productId || variantenJeProdukt[productId] !== undefined) return;
        try {
            const varianten = await productsApi.listVariants(productId);
            setVariantenJeProdukt((prev) => ({ ...prev, [productId]: varianten }));
        } catch {
            setVariantenJeProdukt((prev) => ({ ...prev, [productId]: [] }));
        }
    };

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
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Fehler beim Erstellen des Abonnements'));
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
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Fehler beim Aktualisieren'));
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
        setFormData(leeresFormular());
    };

    // Positionen bearbeiten
    const setzePosition = (index: number, aenderung: Partial<PositionRow>) => {
        setFormData((prev) => ({
            ...prev,
            positionen: prev.positionen.map((p, i) => (i === index ? { ...p, ...aenderung } : p)),
        }));
    };

    const waehleProdukt = (index: number, productId: string) => {
        // Neues Produkt: Variante und Legacy-Sorte gehören nicht mehr dazu
        setzePosition(index, { product_id: productId, product_variant_id: '', seed_id: '' });
        void ladeVarianten(productId);
    };

    const waehleVariante = (index: number, productId: string, variantId: string) => {
        const variante = (variantenJeProdukt[productId] || []).find((v) => v.id === variantId);
        // Mit Variante gilt ihre Verpackungseinheit (so rechnet auch der Abo-Lauf)
        setzePosition(index, {
            product_variant_id: variantId,
            ...(variante?.packaging_unit_code ? { einheit: variante.packaging_unit_code } : {}),
        });
    };

    const positionHinzufuegen = () => {
        setFormData((prev) => ({ ...prev, positionen: [...prev.positionen, leerePosition()] }));
    };

    const positionEntfernen = (index: number) => {
        setFormData((prev) => ({
            ...prev,
            positionen: prev.positionen.length > 1 ? prev.positionen.filter((_, i) => i !== index) : prev.positionen,
        }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!editingSub && !formData.kunde_id) {
            toast.error('Bitte einen Kunden wählen');
            return;
        }
        if (formData.positionen.some((p) => !p.product_id && !p.seed_id)) {
            toast.error('Bitte in jeder Position ein Produkt wählen');
            return;
        }
        if (formData.positionen.some((p) => !(parseFloat(p.menge) > 0))) {
            toast.error('Jede Position braucht eine Menge größer 0');
            return;
        }

        const positionen = formData.positionen.map((p) => ({
            product_id: p.product_id || undefined,
            product_variant_id: p.product_variant_id || undefined,
            seed_id: p.product_id ? undefined : p.seed_id || undefined,
            menge: parseFloat(p.menge),
            einheit: p.einheit,
        }));

        if (editingSub) {
            updateMutation.mutate({
                id: editingSub.id,
                data: {
                    intervall: formData.intervall,
                    liefertage: formData.liefertage,
                    gueltig_bis: formData.gueltig_bis || undefined,
                    aktiv: formData.aktiv,
                    positionen,
                },
            });
        } else {
            createMutation.mutate({
                kunde_id: formData.kunde_id,
                intervall: formData.intervall,
                liefertage: formData.liefertage.length > 0 ? formData.liefertage : undefined,
                gueltig_von: formData.gueltig_von,
                gueltig_bis: formData.gueltig_bis || undefined,
                positionen,
            });
        }
    };

    const openEditModal = (sub: Subscription) => {
        const positionen: PositionRow[] = sub.positionen && sub.positionen.length > 0
            ? sub.positionen.map((p) => ({
                product_id: p.product_id || '',
                product_variant_id: p.product_variant_id || '',
                seed_id: p.seed_id || '',
                menge: String(p.menge),
                einheit: p.einheit,
                bisher: p.bezeichnung || undefined,
            }))
            : [{
                product_id: sub.product_id || '',
                product_variant_id: sub.product_variant_id || '',
                seed_id: sub.seed_id || '',
                menge: String(sub.menge),
                einheit: sub.einheit,
                bisher: sub.product_name || undefined,
            }];
        positionen.forEach((p) => { void ladeVarianten(p.product_id); });
        setFormData({
            kunde_id: sub.kunde_id,
            intervall: sub.intervall,
            liefertage: sub.liefertage || [],
            gueltig_von: sub.gueltig_von,
            gueltig_bis: sub.gueltig_bis || '',
            aktiv: sub.aktiv,
            positionen,
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
                // overflow-x-auto statt -hidden: sonst werden Status/Aktionen
                // auf schmalen Bildschirmen abgeschnitten statt scrollbar
                <div className="card overflow-x-auto">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Kunde</th>
                                <th>Positionen je Lieferung</th>
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
                                        <ul className="space-y-0.5">
                                            {positionenVon(sub).map((p, i) => (
                                                <li key={i} className="flex items-center gap-2">
                                                    <Leaf className="w-4 h-4 text-green-500 shrink-0" />
                                                    <span className="font-semibold tabular-nums">
                                                        {Number(p.menge).toLocaleString('de-DE')}
                                                    </span>
                                                    <span className="text-gray-500 dark:text-gray-400">{einheitLabel(p.einheit)}</span>
                                                    <span>{p.bezeichnung || '—'}</span>
                                                </li>
                                            ))}
                                        </ul>
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
                                    <td className="text-sm text-gray-500 dark:text-gray-400">
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
                                                className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                                                onClick={() => openEditModal(sub)}
                                                title="Bearbeiten"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
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
                        <Combobox
                            label="Kunde *"
                            value={formData.kunde_id}
                            onChange={(v) => setFormData({ ...formData, kunde_id: v })}
                            placeholder="Kunde suchen…"
                            options={customers.map((c: Customer) => ({ value: c.id, label: c.name }))}
                        />
                    )}

                    {/* Positionen je Lieferung (B6): mehrere Produkte, je mit Menge und Einheit */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Positionen je Lieferung *
                        </label>
                        <div className="space-y-3">
                            {formData.positionen.map((pos, index) => {
                                const varianten = variantenJeProdukt[pos.product_id] || [];
                                return (
                                    <div
                                        key={index}
                                        className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 space-y-2"
                                    >
                                        <div className="flex items-start gap-2">
                                            <div className="flex-1">
                                                {products.length === 0 && seeds.length > 0 ? (
                                                    <select
                                                        value={pos.seed_id}
                                                        onChange={(e) => setzePosition(index, { seed_id: e.target.value, product_id: '', product_variant_id: '' })}
                                                        className={selectClassName}
                                                        aria-label={`Saatgut Position ${index + 1}`}
                                                    >
                                                        <option value="">(Keine Produkte angelegt — Saatgut wählen)</option>
                                                        {seeds.map((seed: Seed) => (
                                                            <option key={seed.id} value={seed.id}>{seed.name}</option>
                                                        ))}
                                                    </select>
                                                ) : (
                                                    <Combobox
                                                        value={pos.product_id}
                                                        onChange={(v) => waehleProdukt(index, v)}
                                                        placeholder="Produkt suchen…"
                                                        options={produktOptionenFuer(pos)}
                                                    />
                                                )}
                                            </div>
                                            <button
                                                type="button"
                                                className="p-2 text-gray-500 dark:text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                                                onClick={() => positionEntfernen(index)}
                                                disabled={formData.positionen.length === 1}
                                                title="Position entfernen"
                                                aria-label={`Position ${index + 1} entfernen`}
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                            {varianten.length > 0 ? (
                                                <select
                                                    value={pos.product_variant_id}
                                                    onChange={(e) => waehleVariante(index, pos.product_id, e.target.value)}
                                                    className={selectClassName}
                                                    aria-label={`Variante Position ${index + 1}`}
                                                >
                                                    <option value="">Ohne Variante</option>
                                                    {varianten.map((v) => (
                                                        <option key={v.id} value={v.id}>
                                                            {v.name_suffix || v.packaging_unit_code || 'Variante'}
                                                        </option>
                                                    ))}
                                                </select>
                                            ) : (
                                                <div className="hidden sm:block" />
                                            )}
                                            <Input
                                                type="number"
                                                step="0.01"
                                                min="0"
                                                placeholder="Menge"
                                                aria-label={`Menge Position ${index + 1}`}
                                                value={pos.menge}
                                                onChange={(e) => setzePosition(index, { menge: e.target.value })}
                                                required
                                            />
                                            <select
                                                value={pos.einheit}
                                                onChange={(e) => setzePosition(index, { einheit: e.target.value })}
                                                className={selectClassName}
                                                disabled={!!pos.product_variant_id}
                                                title={pos.product_variant_id ? 'Einheit der Variante' : undefined}
                                                aria-label={`Einheit Position ${index + 1}`}
                                            >
                                                {!EINHEITEN.some((e) => e.value === pos.einheit) && (
                                                    <option value={pos.einheit}>{pos.einheit}</option>
                                                )}
                                                {EINHEITEN.map((e) => (
                                                    <option key={e.value} value={e.value}>{e.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        <button
                            type="button"
                            className="btn btn-secondary btn-sm mt-2"
                            onClick={positionHinzufuegen}
                        >
                            <Plus className="w-4 h-4" />
                            Position hinzufügen
                        </button>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            Alle Positionen kommen an jedem Liefertag in eine Bestellung. Preise wie im
                            Bestellformular: Sonderpreis des Kunden, sonst Varianten- bzw. Produktpreis.
                        </p>
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
                                            ? 'bg-minga-50 dark:bg-minga-900/300 text-white border-minga-500'
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

                    {editingSub && (
                        <label className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                checked={formData.aktiv}
                                onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
                                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">
                                Aktiv (wird an den Liefertagen beliefert)
                            </span>
                        </label>
                    )}

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
                        <strong>{deletingSub?.kunde_name}</strong> (
                        {deletingSub
                            ? positionenVon(deletingSub).map((p) => p.bezeichnung || '—').join(', ')
                            : '—'}
                        ) wirklich deaktivieren?
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
