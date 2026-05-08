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
    product_name: string;
    quantity: number;
    unit: string;
    unit_price: number;
}

export function CreateOrderModal({ open, onClose, preselectedCustomer }: CreateOrderModalProps) {
    const queryClient = useQueryClient();
    const toast = useToast();

    const [customerId, setCustomerId] = useState('');
    const [deliveryDate, setDeliveryDate] = useState('');
    const [lines, setLines] = useState<OrderLineRow[]>([{ product_id: '', product_name: '', quantity: 1, unit: 'g', unit_price: 0 }]);
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
        ? productsData.map(p => ({ id: p.id, name: p.name, price: p.base_price || 0, unit: 'g' }))
        : (seedsData?.items || []).map(s => ({ id: s.id, name: s.name, price: 10, unit: 'g' })); // Default price for seeds

    useEffect(() => {
        if (open) {
            // Reset form
            setCustomerId(preselectedCustomer?.id || '');
            setDeliveryDate(new Date().toISOString().split('T')[0]); // Today (same-day allowed)
            setLines([{ product_id: '', product_name: '', quantity: 1, unit: 'g', unit_price: 0 }]);
            setNotes('');
            setCustomerReference('');
        }
    }, [open, preselectedCustomer]);

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

        const orderLines = lines.map(l => ({
            product_id: l.product_id || undefined,
            product_name: l.product_name,
            quantity: l.quantity,
            unit: l.unit,
            unit_price: l.unit_price,
            tax_rate: 'REDUZIERT' as const, // Food products use reduced tax rate (7%)
        }));

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

        // If product_id changes, update product_name and unit_price from the selected product
        if (field === 'product_id') {
            const selectedItem = availableItems.find(p => p.id === value);
            if (selectedItem) {
                newLines[index].product_name = selectedItem.name;
                newLines[index].unit_price = selectedItem.price;
                newLines[index].unit = selectedItem.unit || 'g';
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
        setLines([...lines, { product_id: '', product_name: '', quantity: 1, unit: 'g', unit_price: 0 }]);
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
                    {lines.map((line, index) => (
                        <div key={index} className="flex gap-2 items-end">
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
                                        { value: 'SCHALE', label: 'Schale' }
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
                    ))}
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
