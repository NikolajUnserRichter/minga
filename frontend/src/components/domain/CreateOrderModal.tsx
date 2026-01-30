import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../ui/Modal';
import { Input, Select, Button, useToast } from '../ui';
import { salesApi, seedsApi } from '../../services/api';
import { Customer, Seed } from '../../types';
import { Plus, Trash } from 'lucide-react';

interface CreateOrderModalProps {
    open: boolean;
    onClose: () => void;
    preselectedCustomer?: Customer | null;
}

interface OrderItemRow {
    seed_id: string;
    menge: number;
    einheit: string;
}

export function CreateOrderModal({ open, onClose, preselectedCustomer }: CreateOrderModalProps) {
    const queryClient = useQueryClient();
    const toast = useToast();

    const [customerId, setCustomerId] = useState('');
    const [deliveryDate, setDeliveryDate] = useState('');
    const [items, setItems] = useState<OrderItemRow[]>([{ seed_id: '', menge: 1, einheit: 'g' }]);
    const [notes, setNotes] = useState('');

    // Fetch Customers if not preselected
    const { data: customersData } = useQuery({
        queryKey: ['customers'],
        queryFn: () => salesApi.listCustomers(),
        enabled: open,
    });

    // Fetch Seeds for product selection
    const { data: seedsData } = useQuery({
        queryKey: ['seeds'],
        queryFn: () => seedsApi.list({ aktiv: true }),
        enabled: open,
    });

    useEffect(() => {
        if (open) {
            // Reset form
            setCustomerId(preselectedCustomer?.id || '');
            setDeliveryDate(new Date(Date.now() + 86400000).toISOString().split('T')[0]); // Tomorrow
            setItems([{ seed_id: '', menge: 1, einheit: 'g' }]);
            setNotes('');
        }
    }, [open, preselectedCustomer]);

    const createOrderMutation = useMutation({
        mutationFn: (data: any) => salesApi.createOrder(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['orders'] });
            toast.success('Bestellung erfolgreich erstellt');
            onClose();
        },
        onError: () => {
            toast.error('Fehler beim Erstellen der Bestellung');
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!customerId) return toast.error('Bitte einen Kunden wählen');
        if (items.some(i => !i.seed_id)) return toast.error('Bitte Produkte auswählen');

        createOrderMutation.mutate({
            kunde_id: customerId,
            liefer_datum: deliveryDate,
            positionen: items,
            notizen: notes
        });
    };

    const updateItem = (index: number, field: keyof OrderItemRow, value: any) => {
        const newItems = [...items];
        newItems[index] = { ...newItems[index], [field]: value };
        setItems(newItems);
    };

    const removeItem = (index: number) => {
        if (items.length > 1) {
            setItems(items.filter((_, i) => i !== index));
        }
    };

    const addItem = () => {
        setItems([...items, { seed_id: '', menge: 1, einheit: 'g' }]);
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

                <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Positionen</label>
                    {items.map((item, index) => (
                        <div key={index} className="flex gap-2 items-end">
                            <div className="flex-1">
                                <Select
                                    value={item.seed_id}
                                    onChange={(e) => updateItem(index, 'seed_id', e.target.value)}
                                    options={[
                                        { value: '', label: 'Produkt wählen...' },
                                        ...(seedsData?.items || []).map(s => ({ value: s.id, label: s.name }))
                                    ]}
                                />
                            </div>
                            <div className="w-24">
                                <Input
                                    type="number"
                                    value={item.menge}
                                    onChange={(e) => updateItem(index, 'menge', parseFloat(e.target.value))}
                                    min={0.1}
                                    step={0.1}
                                />
                            </div>
                            <div className="w-24">
                                <Select
                                    value={item.einheit}
                                    onChange={(e) => updateItem(index, 'einheit', e.target.value)}
                                    options={[
                                        { value: 'g', label: 'Gramm' },
                                        { value: 'kg', label: 'Kg' },
                                        { value: 'stk', label: 'Stk' },
                                        { value: 'tray', label: 'Tray' }
                                    ]}
                                />
                            </div>
                            <Button
                                type="button"
                                variant="danger"
                                onClick={() => removeItem(index)}
                                disabled={items.length === 1}
                                icon={<Trash className="w-4 h-4" />}
                            />
                        </div>
                    ))}
                    <Button type="button" variant="secondary" size="sm" onClick={addItem} icon={<Plus className="w-3 h-3" />}>
                        Position hinzufügen
                    </Button>
                </div>

                <Input
                    label="Notizen"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Interne Anmerkungen..."
                />
            </form>
        </Modal>
    );
}
