import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../ui/Modal';
import { Input, Select, Button, useToast } from '../ui';
import { salesApi, productsApi, seedsApi } from '../../services/api';
import { Customer } from '../../types';
import { Plus, Trash } from 'lucide-react';

interface CreateOrderModalProps {
    open: boolean;
    onClose: () => void;
    preselectedCustomer?: Customer | null;
}

interface OrderLineRow {
    product_id: string;
    product_variant_id: string;
    product_name: string;
    quantity: number;
    unit: string;
    unit_price: number;
    variable_bundle_selections: Array<{ product_id: string; quantity: number }>;
}

const emptyLine = (): OrderLineRow => ({
    product_id: '',
    product_variant_id: '',
    product_name: '',
    quantity: 1,
    unit: 'g',
    unit_price: 0,
    variable_bundle_selections: [],
});

export function CreateOrderModal({ open, onClose, preselectedCustomer }: CreateOrderModalProps) {
    const queryClient = useQueryClient();
    const toast = useToast();

    const [customerId, setCustomerId] = useState('');
    const [deliveryDate, setDeliveryDate] = useState('');
    const [lines, setLines] = useState<OrderLineRow[]>([emptyLine()]);
    const [variantsByProduct, setVariantsByProduct] = useState<Record<string, Array<{ id: string; name_suffix: string | null; packaging_unit_code: string | null; price_override: number | null; items_per_pack: number }>>>({});
    const [notes, setNotes] = useState('');
    const [customerReference, setCustomerReference] = useState('');

    // Fetch Customers if not preselected
    const { data: customersData } = useQuery({
        queryKey: ['customers'],
        queryFn: () => salesApi.listCustomers(),
        enabled: open,
    });

    // Fetch Products for selection
    const { data: productsData } = useQuery({
        queryKey: ['products', { is_active: true }],
        queryFn: () => productsApi.list({ is_active: true }),
        enabled: open,
    });

    // Fallback to Seeds if no products are available
    const { data: seedsData } = useQuery({
        queryKey: ['seeds', { aktiv: true }],
        queryFn: () => seedsApi.list({ aktiv: true }),
        enabled: open && (!productsData || productsData.length === 0),
    });

    // Determine available items (prefer products, fallback to seeds)
    const availableItems = productsData && productsData.length > 0
        ? productsData.map(p => ({
            id: p.id,
            name: p.name,
            price: p.base_price || 0,
            unit: 'g',
            is_variable_bundle: p.is_variable_bundle,
            variable_bundle_min_slots: p.variable_bundle_min_slots,
            variable_bundle_max_slots: p.variable_bundle_max_slots,
        }))
        : (seedsData?.items || []).map(s => ({
            id: s.id,
            name: s.name,
            price: 10,
            unit: 'g',
            is_variable_bundle: false,
            variable_bundle_min_slots: null as number | null,
            variable_bundle_max_slots: null as number | null,
        }));

    // Picker-Auswahl: Nur Nicht-Bundle-Produkte (vermeidet rekursive Bundles)
    const pickableSorten = (productsData || []).filter(p => !p.is_bundle && !p.is_variable_bundle && p.is_active);

    useEffect(() => {
        if (open) {
            // Reset form
            setCustomerId(preselectedCustomer?.id || '');
            setDeliveryDate(new Date().toISOString().split('T')[0]); // Today (same-day allowed)
            setLines([emptyLine()]);
            setNotes('');
            setCustomerReference('');
            setVariantsByProduct({});
        }
    }, [open, preselectedCustomer]);

    const loadVariantsForProduct = async (productId: string) => {
        if (variantsByProduct[productId] !== undefined) return;
        try {
            const variants = await productsApi.listVariants(productId);
            setVariantsByProduct((prev) => ({ ...prev, [productId]: variants as any }));
        } catch {
            setVariantsByProduct((prev) => ({ ...prev, [productId]: [] }));
        }
    };

    const createOrderMutation = useMutation({
        mutationFn: (data: Parameters<typeof salesApi.createOrder>[0]) => salesApi.createOrder(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['orders'] });
            toast.success('Bestellung erfolgreich erstellt');
            onClose();
        },
        onError: (error: any) => {
            const message = error?.response?.data?.detail || 'Fehler beim Erstellen der Bestellung';
            toast.error(message);
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!customerId) return toast.error('Bitte einen Kunden wählen');
        if (lines.some(l => !l.product_id && !l.product_name)) return toast.error('Bitte Produkte auswählen');
        const todayStr = new Date().toISOString().split('T')[0];
        if (deliveryDate < todayStr) return toast.error('Lieferdatum darf nicht in der Vergangenheit liegen');
        if (lines.some(l => l.quantity <= 0)) return toast.error('Alle Mengen müssen größer als 0 sein');
        if (lines.some(l => l.unit_price < 0)) return toast.error('Preise dürfen nicht negativ sein');

        // Variable-Bundle: Sorten-Auswahl validieren
        for (const l of lines) {
            const item = availableItems.find(i => i.id === l.product_id);
            if (!item?.is_variable_bundle) continue;
            const sels = l.variable_bundle_selections;
            if (sels.length === 0 || sels.some(s => !s.product_id || s.quantity <= 0)) {
                return toast.error(`'${item.name}': Bitte Sorten auswählen`);
            }
            const total = sels.reduce((sum, s) => sum + Number(s.quantity || 0), 0);
            const min = item.variable_bundle_min_slots ?? 1;
            const max = item.variable_bundle_max_slots ?? 99;
            if (total < min || total > max) {
                return toast.error(`'${item.name}' braucht ${min}–${max} Sorten, gewählt: ${total}`);
            }
        }

        const orderLines = lines.map(l => {
            const item = availableItems.find(i => i.id === l.product_id);
            const isVB = !!item?.is_variable_bundle;
            return {
                product_id: l.product_id || undefined,
                product_variant_id: l.product_variant_id || undefined,
                product_name: l.product_name,
                quantity: l.quantity,
                unit: l.unit,
                unit_price: l.unit_price,
                tax_rate: 'REDUZIERT' as const, // Food products use reduced tax rate (7%)
                variable_bundle_selections: isVB && l.variable_bundle_selections.length > 0
                    ? l.variable_bundle_selections.map(s => ({ product_id: s.product_id, quantity: Number(s.quantity) }))
                    : undefined,
            };
        });

        createOrderMutation.mutate({
            customer_id: customerId,
            requested_delivery_date: deliveryDate,
            lines: orderLines,
            notes: notes || undefined,
            customer_reference: customerReference || undefined,
        });
    };

    const updateLine = (index: number, field: keyof OrderLineRow, value: any) => {
        const newLines = [...lines];
        newLines[index] = { ...newLines[index], [field]: value };

        if (field === 'product_id') {
            const selectedItem = availableItems.find(p => p.id === value);
            if (selectedItem) {
                newLines[index].product_name = selectedItem.name;
                newLines[index].unit_price = selectedItem.price;
                newLines[index].unit = selectedItem.unit || 'g';
                newLines[index].product_variant_id = '';
            }
            if (value) loadVariantsForProduct(value);
        }

        if (field === 'product_variant_id' && value) {
            const variants = variantsByProduct[newLines[index].product_id] || [];
            const variant = variants.find((v) => v.id === value);
            if (variant) {
                if (variant.packaging_unit_code) newLines[index].unit = variant.packaging_unit_code;
                if (variant.price_override !== null) newLines[index].unit_price = Number(variant.price_override);
                if (variant.name_suffix) {
                    newLines[index].product_name = `${availableItems.find(p => p.id === newLines[index].product_id)?.name || ''} — ${variant.name_suffix}`;
                }
            }
        }

        setLines(newLines);
    };

    const removeLine = (index: number) => {
        if (lines.length > 1) {
            setLines(lines.filter((_, i) => i !== index));
        }
    };

    const addLine = () => {
        setLines([...lines, emptyLine()]);
    };

    const updateBundleSelection = (
        lineIndex: number,
        selIndex: number,
        field: 'product_id' | 'quantity',
        value: string | number,
    ) => {
        const newLines = [...lines];
        const sels = [...newLines[lineIndex].variable_bundle_selections];
        sels[selIndex] = { ...sels[selIndex], [field]: value } as { product_id: string; quantity: number };
        newLines[lineIndex] = { ...newLines[lineIndex], variable_bundle_selections: sels };
        setLines(newLines);
    };

    const addBundleSelection = (lineIndex: number) => {
        const newLines = [...lines];
        newLines[lineIndex] = {
            ...newLines[lineIndex],
            variable_bundle_selections: [
                ...newLines[lineIndex].variable_bundle_selections,
                { product_id: '', quantity: 1 },
            ],
        };
        setLines(newLines);
    };

    const removeBundleSelection = (lineIndex: number, selIndex: number) => {
        const newLines = [...lines];
        newLines[lineIndex] = {
            ...newLines[lineIndex],
            variable_bundle_selections: newLines[lineIndex].variable_bundle_selections.filter((_, i) => i !== selIndex),
        };
        setLines(newLines);
    };

    const calculateTotal = () => {
        return lines.reduce((sum, line) => sum + (line.quantity * line.unit_price), 0).toFixed(2);
    };

    return (
        <Modal
            open={open}
            onClose={onClose}
            title="Neue Bestellung aufnehmen"
            size="lg"
            footer={
                <>
                    <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
                    <Button onClick={handleSubmit} loading={createOrderMutation.isPending}>Bestellung erstellen</Button>
                </>
            }
        >
            <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Select
                        label="Kunde"
                        value={customerId}
                        onChange={(e) => setCustomerId(e.target.value)}
                        disabled={!!preselectedCustomer}
                        options={[
                            { value: '', label: 'Kunde wählen...' },
                            ...(customersData?.items || []).map(c => ({ value: c.id, label: c.name }))
                        ]}
                    />
                    <Input
                        label="Lieferdatum"
                        type="date"
                        value={deliveryDate}
                        onChange={(e) => setDeliveryDate(e.target.value)}
                        required
                    />
                </div>

                <Input
                    label="Kundenbestellnummer (optional)"
                    value={customerReference}
                    onChange={(e) => setCustomerReference(e.target.value)}
                    placeholder="z.B. PO-12345"
                />

                <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Positionen</label>
                    {lines.map((line, index) => {
                        const variants = variantsByProduct[line.product_id] || [];
                        const hasVariants = variants.length > 0;
                        const selectedItem = availableItems.find(i => i.id === line.product_id);
                        const isVariableBundle = !!selectedItem?.is_variable_bundle;
                        const vbMin = selectedItem?.variable_bundle_min_slots ?? 1;
                        const vbMax = selectedItem?.variable_bundle_max_slots ?? 99;
                        const vbTotal = line.variable_bundle_selections.reduce((s, x) => s + Number(x.quantity || 0), 0);
                        return (
                        <div key={index} className="space-y-2">
                        <div className="flex gap-2 items-end">
                            <div className="flex-1">
                                <Select
                                    value={line.product_id}
                                    onChange={(e) => updateLine(index, 'product_id', e.target.value)}
                                    options={[
                                        { value: '', label: 'Produkt wählen...' },
                                        ...availableItems.map(p => ({ value: p.id, label: p.name }))
                                    ]}
                                />
                            </div>
                            {hasVariants && (
                                <div className="w-44">
                                    <Select
                                        value={line.product_variant_id}
                                        onChange={(e) => updateLine(index, 'product_variant_id', e.target.value)}
                                        options={[
                                            { value: '', label: 'Variante (opt.)' },
                                            ...variants.map((v) => ({
                                                value: v.id,
                                                label: v.name_suffix || v.packaging_unit_code || 'Variante',
                                            })),
                                        ]}
                                    />
                                </div>
                            )}
                            <div className="w-20">
                                <Input
                                    type="number"
                                    value={line.quantity}
                                    onChange={(e) => updateLine(index, 'quantity', parseFloat(e.target.value) || 0)}
                                    min={0.1}
                                    step={0.1}
                                    placeholder="Menge"
                                />
                            </div>
                            <div className="w-20">
                                <Select
                                    value={line.unit}
                                    onChange={(e) => updateLine(index, 'unit', e.target.value)}
                                    options={[
                                        { value: 'g', label: 'g' },
                                        { value: 'kg', label: 'kg' },
                                        { value: 'STK', label: 'Stk' },
                                        { value: 'SCHALE', label: 'Schale' },
                                        { value: 'TRAY', label: 'Tray (8 Schalen)' },
                                        { value: 'KISTE_12', label: 'Mehrwegkiste (12 Schalen)' },
                                        { value: 'KISTE_6', label: 'Mehrwegkiste (6 Schalen)' },
                                        { value: 'KARTON_6', label: 'Karton (6 Schalen)' },
                                    ]}
                                />
                            </div>
                            <div className="w-24">
                                <Input
                                    type="number"
                                    value={line.unit_price}
                                    onChange={(e) => updateLine(index, 'unit_price', parseFloat(e.target.value) || 0)}
                                    min={0}
                                    step={0.01}
                                    placeholder="€/Einheit"
                                />
                            </div>
                            <Button
                                type="button"
                                variant="danger"
                                onClick={() => removeLine(index)}
                                disabled={lines.length === 1}
                                icon={<Trash className="w-4 h-4" />}
                            />
                        </div>
                        {isVariableBundle && (
                            <div className="ml-2 pl-3 border-l-2 border-emerald-300 dark:border-emerald-700 space-y-2">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-medium text-gray-700 dark:text-gray-300">
                                        Sorten für „{selectedItem?.name}" auswählen
                                    </span>
                                    <span className={`tabular-nums ${vbTotal < vbMin || vbTotal > vbMax ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-500 dark:text-gray-400'}`}>
                                        {vbTotal} / {vbMin === vbMax ? vbMin : `${vbMin}–${vbMax}`} Slots
                                    </span>
                                </div>
                                {line.variable_bundle_selections.length === 0 && (
                                    <div className="text-xs text-gray-500 dark:text-gray-400 italic">
                                        Noch keine Sorte gewählt
                                    </div>
                                )}
                                {line.variable_bundle_selections.map((sel, sIdx) => (
                                    <div key={sIdx} className="flex gap-2 items-end">
                                        <div className="flex-1">
                                            <Select
                                                value={sel.product_id}
                                                onChange={(e) => updateBundleSelection(index, sIdx, 'product_id', e.target.value)}
                                                options={[
                                                    { value: '', label: 'Sorte wählen...' },
                                                    ...pickableSorten.map(p => ({ value: p.id, label: p.name })),
                                                ]}
                                            />
                                        </div>
                                        <div className="w-20">
                                            <Input
                                                type="number"
                                                value={sel.quantity}
                                                onChange={(e) => updateBundleSelection(index, sIdx, 'quantity', parseInt(e.target.value) || 1)}
                                                min={1}
                                                step={1}
                                                placeholder="Slots"
                                            />
                                        </div>
                                        <Button
                                            type="button"
                                            variant="danger"
                                            size="sm"
                                            onClick={() => removeBundleSelection(index, sIdx)}
                                            icon={<Trash className="w-3 h-3" />}
                                        />
                                    </div>
                                ))}
                                <Button
                                    type="button"
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => addBundleSelection(index)}
                                    disabled={vbTotal >= vbMax}
                                    icon={<Plus className="w-3 h-3" />}
                                >
                                    Sorte hinzufügen
                                </Button>
                            </div>
                        )}
                        </div>
                        );
                    })}
                    <Button type="button" variant="secondary" size="sm" onClick={addLine} icon={<Plus className="w-3 h-3" />}>
                        Position hinzufügen
                    </Button>
                </div>

                <div className="flex justify-end text-lg font-semibold text-gray-900 dark:text-white">
                    Gesamtsumme: €{calculateTotal()}
                </div>

                <Input
                    label="Notizen (optional)"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Interne Anmerkungen..."
                />
            </form>
        </Modal>
    );
}
