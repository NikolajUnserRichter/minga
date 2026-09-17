import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button, Combobox, Input, Select, Textarea, useToast } from '../ui';
import { customerPricesApi, productsApi, salesApi } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Order } from '../../types';

interface EditableLine {
    id: string;
    product_name: string;
    quantity: number | string;
    unit: string;
    unit_price: number | string;
    line_net: number | string;
}

interface EditableOrder extends Order {
    requested_delivery_date: string;
    notes: string | null;
    lines: EditableLine[];
}

const emptyLine = () => ({
    product_id: '',
    product_name: '',
    quantity: '1',
    unit: 'STK',
    unit_price: '0',
    is_customer_specific: false,
    price_manually_edited: false,
});

const formatAmount = (value: number | string | undefined) =>
    Number(value ?? 0).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });

function EditableOrderLine({ line, disabled, canRemove, onSave, onRemove }: {
    line: EditableLine;
    disabled: boolean;
    canRemove: boolean;
    onSave: (lineId: string, quantity: number, unitPrice: number) => Promise<void>;
    onRemove: (lineId: string, name: string) => Promise<void>;
}) {
    const [quantity, setQuantity] = useState(String(line.quantity));
    const [unitPrice, setUnitPrice] = useState(String(line.unit_price));

    useEffect(() => {
        setQuantity(String(line.quantity));
        setUnitPrice(String(line.unit_price));
    }, [line.quantity, line.unit_price]);

    const quantityValid = quantity.trim() !== '' && Number.isFinite(Number(quantity)) && Number(quantity) > 0;
    const priceValid = unitPrice.trim() !== '' && Number.isFinite(Number(unitPrice)) && Number(unitPrice) >= 0;
    const save = async () => {
        if (disabled || !quantityValid || !priceValid) return;
        if (Number(quantity) === Number(line.quantity) && Number(unitPrice) === Number(line.unit_price)) return;
        await onSave(line.id, Number(quantity), Number(unitPrice));
    };

    return (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{line.product_name}</span>
                <span className="text-sm whitespace-nowrap">{formatAmount(line.line_net)} netto</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
                <Input
                    id={`edit-quantity-${line.id}`}
                    label={`Menge (${line.unit})`}
                    type="number" min="0" step="any" value={quantity}
                    onChange={(event) => setQuantity(event.target.value)} onBlur={save}
                    disabled={disabled} error={quantityValid ? undefined : 'Menge muss größer als 0 sein'}
                />
                <Input
                    id={`edit-price-${line.id}`}
                    label="Preis pro Einheit (€ netto)"
                    type="number" min="0" step="0.01" value={unitPrice}
                    onChange={(event) => setUnitPrice(event.target.value)} onBlur={save}
                    disabled={disabled} error={priceValid ? undefined : 'Gültigen Preis ab 0 eingeben'}
                />
                <Button
                    variant="danger" size="sm" icon={<Trash className="w-4 h-4" />}
                    disabled={disabled || !canRemove}
                    title={!canRemove ? 'Mindestens eine Position muss erhalten bleiben' : undefined}
                    onClick={() => onRemove(line.id, line.product_name)}
                >
                    Entfernen
                </Button>
            </div>
        </div>
    );
}

export function EditOrderModal({ open, order, onClose }: {
    open: boolean;
    order: Order | null;
    onClose: () => void;
}) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const orderId = order?.id;
    const [currentOrder, setCurrentOrder] = useState<EditableOrder | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState('');
    const [loadAttempt, setLoadAttempt] = useState(0);
    const [busy, setBusy] = useState(false);
    const saving = useRef(false);
    const [deliveryDate, setDeliveryDate] = useState('');
    const [customerReference, setCustomerReference] = useState('');
    const [notes, setNotes] = useState('');
    const [changeReason, setChangeReason] = useState('');
    const [cancelReason, setCancelReason] = useState('');
    const [newLine, setNewLine] = useState(emptyLine);
    const [priceLoading, setPriceLoading] = useState(false);
    const [priceError, setPriceError] = useState('');
    const priceRequest = useRef(0);

    useEffect(() => {
        let active = true;
        setCurrentOrder(null);
        setLoadError('');
        setChangeReason('');
        setCancelReason('');
        setNewLine(emptyLine());
        setPriceLoading(false);
        setPriceError('');
        priceRequest.current += 1;
        if (open && orderId) {
            setLoading(true);
            salesApi.getOrder(orderId).then((response) => {
                if (!active) return;
                const detail = response as EditableOrder;
                setCurrentOrder(detail);
                setDeliveryDate(detail.requested_delivery_date);
                setCustomerReference(detail.customer_reference ?? '');
                setNotes(detail.notes ?? '');
            }).catch((error: unknown) => {
                if (active) setLoadError(getErrorMessage(error, 'Bestellung konnte nicht geladen werden'));
            }).finally(() => {
                if (active) setLoading(false);
            });
        }
        return () => {
            active = false;
            priceRequest.current += 1;
        };
    }, [open, orderId, loadAttempt]);

    const istStorniert = currentOrder?.status === 'STORNIERT';
    const stornierbar = currentOrder?.status === 'ENTWURF' || currentOrder?.status === 'BESTAETIGT';
    const disabled = busy || istStorniert;
    const products = useQuery({
        queryKey: ['products', { is_active: true }],
        queryFn: () => productsApi.list({ is_active: true }),
        enabled: open && stornierbar,
    });

    const refreshOrder = async () => {
        if (!orderId) return;
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
        const response = await salesApi.getOrder(orderId);
        setCurrentOrder(response as EditableOrder);
    };

    const runChange = async (change: () => Promise<void>) => {
        if (!currentOrder || istStorniert || saving.current) return;
        saving.current = true;
        setBusy(true);
        try {
            await change();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, 'Bestellung konnte nicht geändert werden'));
        } finally {
            saving.current = false;
            setBusy(false);
        }
    };

    const saveHeader = async () => {
        if (!currentOrder) return;
        if (!deliveryDate) return toast.error('Bitte ein Lieferdatum angeben');
        const changes: Parameters<typeof salesApi.updateOrder>[1] = {};
        if (deliveryDate !== currentOrder.requested_delivery_date) changes.requested_delivery_date = deliveryDate;
        if (customerReference !== (currentOrder.customer_reference ?? '')) changes.customer_reference = customerReference;
        if (notes !== (currentOrder.notes ?? '')) changes.notes = notes;
        if (Object.keys(changes).length === 0) return;
        if (changeReason.trim()) changes.change_reason = changeReason.trim();
        await runChange(async () => {
            await salesApi.updateOrder(currentOrder.id, changes);
            await refreshOrder();
            setChangeReason('');
            toast.success('Bestellung aktualisiert');
        });
    };

    const saveLine = async (lineId: string, quantity: number, unitPrice: number) => {
        if (!currentOrder) return;
        await runChange(async () => {
            await salesApi.updateOrderLine(currentOrder.id, lineId, { quantity, unit_price: unitPrice });
            await refreshOrder();
        });
    };

    const removeLine = async (lineId: string, name: string) => {
        if (!currentOrder || disabled) return;
        if (!window.confirm(`Position "${name}" aus der Bestellung entfernen?`)) return;
        await runChange(async () => {
            await salesApi.deleteOrderLine(currentOrder.id, lineId);
            await refreshOrder();
            toast.success('Position entfernt');
        });
    };

    const selectProduct = async (productId: string) => {
        const product = products.data?.find((item) => item.id === productId);
        if (!product || !currentOrder || disabled) return;
        const request = ++priceRequest.current;
        setNewLine({ ...emptyLine(), product_id: product.id, product_name: product.name, unit_price: String(product.base_price ?? 0) });
        setPriceLoading(true);
        setPriceError('');
        try {
            const customerId = currentOrder.customer_id || currentOrder.kunde_id;
            const effective = await customerPricesApi.getEffective(customerId, product.id);
            if (request !== priceRequest.current) return;
            setNewLine((current) => current.price_manually_edited ? current : {
                ...current,
                unit_price: String(effective.unit_price),
                is_customer_specific: effective.is_customer_specific,
            });
        } catch (error: unknown) {
            if (request === priceRequest.current) {
                setPriceError(getErrorMessage(error, 'Sonderpreis konnte nicht geladen werden. Produkt erneut auswählen.'));
            }
        } finally {
            if (request === priceRequest.current) setPriceLoading(false);
        }
    };

    const addLine = async () => {
        if (!currentOrder || !stornierbar || priceLoading || priceError) return;
        if (!newLine.product_id) return toast.error('Bitte ein Produkt auswählen');
        const quantity = Number(newLine.quantity);
        const unitPrice = Number(newLine.unit_price);
        if (!newLine.quantity.trim() || !Number.isFinite(quantity) || quantity <= 0) return toast.error('Menge muss größer als 0 sein');
        if (!newLine.unit_price.trim() || !Number.isFinite(unitPrice) || unitPrice < 0) return toast.error('Gültigen Preis ab 0 eingeben');
        await runChange(async () => {
            await salesApi.addOrderLine(currentOrder.id, {
                product_id: newLine.product_id,
                product_name: newLine.product_name,
                quantity,
                unit: newLine.unit,
                unit_price: unitPrice,
            });
            setNewLine(emptyLine());
            await refreshOrder();
            toast.success('Position hinzugefügt');
        });
    };

    const cancelOrder = async () => {
        if (!currentOrder || !stornierbar || busy) return;
        if (!cancelReason.trim()) return toast.error('Bitte einen Stornogrund angeben');
        if (!window.confirm('Bestellung wirklich stornieren? Das lässt sich nicht rückgängig machen.')) return;
        await runChange(async () => {
            await salesApi.updateOrderStatus(currentOrder.id, 'STORNIERT', cancelReason.trim());
            await queryClient.invalidateQueries({ queryKey: ['orders'] });
            toast.success('Bestellung storniert');
            onClose();
        });
    };

    const close = () => {
        if (!saving.current) onClose();
    };

    return (
        <Modal open={open} onClose={close} title={`Bestellung bearbeiten${order?.order_number ? ` – ${order.order_number}` : ''}`} size="lg"
            footer={<Button variant="secondary" onClick={close} disabled={busy}>Schließen</Button>}>
            {loading && <p role="status">Bestellung wird geladen…</p>}
            {loadError && <div role="alert" className="space-y-3">
                <p className="text-red-600">{loadError}</p>
                <Button variant="secondary" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>Erneut versuchen</Button>
            </div>}
            {currentOrder && <div className="space-y-6">
                {istStorniert && <p role="status" className="rounded-lg bg-gray-100 dark:bg-gray-800 p-3">
                    Diese Bestellung ist storniert und kann nicht bearbeitet werden.
                </p>}
                <section className="space-y-3">
                    <h3 className="font-semibold">Kopfdaten</h3>
                    <p className="text-sm text-gray-500">{currentOrder.customer_name || currentOrder.kunde_name}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Input label="Lieferdatum" type="date" required value={deliveryDate}
                            disabled={disabled} onChange={(event) => setDeliveryDate(event.target.value)} />
                        <Input label="Kundenbestellnummer" value={customerReference}
                            disabled={disabled} onChange={(event) => setCustomerReference(event.target.value)} />
                    </div>
                    <Textarea label="Notizen" value={notes} disabled={disabled} onChange={(event) => setNotes(event.target.value)} />
                    <Input label="Änderungsgrund (optional)" value={changeReason}
                        disabled={disabled} onChange={(event) => setChangeReason(event.target.value)} />
                    <Button onClick={saveHeader} disabled={disabled} loading={busy}>Kopfdaten speichern</Button>
                </section>
                <section className="space-y-3 border-t border-gray-200 dark:border-gray-700 pt-4">
                    <h3 className="font-semibold">Positionen</h3>
                    <p className="text-sm text-gray-500">Menge und Preis werden beim Verlassen des Feldes gespeichert.</p>
                    {busy && <p role="status" className="text-sm">Änderung wird gespeichert…</p>}
                    {currentOrder.lines.map((line) => <EditableOrderLine key={line.id} line={line} disabled={disabled}
                        canRemove={currentOrder.status === 'ENTWURF' || currentOrder.lines.length > 1}
                        onSave={saveLine} onRemove={removeLine} />)}
                    {currentOrder.lines.length === 0 && <p className="text-sm text-gray-500">Keine Positionen vorhanden.</p>}
                    <div className="flex flex-wrap justify-end gap-4 font-medium">
                        <span>Netto: {formatAmount(currentOrder.total_net)}</span>
                        <span>Brutto: {formatAmount(currentOrder.total_gross)}</span>
                    </div>
                    {stornierbar ? <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3 space-y-3">
                        <h4 className="font-medium">Position hinzufügen</h4>
                        {products.isError && <p role="alert" className="text-red-600 text-sm">
                            {getErrorMessage(products.error, 'Produkte konnten nicht geladen werden')}
                            <Button variant="ghost" size="sm" onClick={() => products.refetch()}>Erneut laden</Button>
                        </p>}
                        <Combobox label="Produkt" value={newLine.product_id} onChange={selectProduct}
                            disabled={disabled || products.isLoading} placeholder="Produkt suchen…"
                            options={(products.data || []).map((product) => ({ value: product.id, label: (product.is_bundle || product.is_variable_bundle) ? `📦 ${product.name}` : product.name }))} />
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <Input label="Menge" type="number" min="0" step="any" value={newLine.quantity} disabled={disabled}
                                onChange={(event) => setNewLine((current) => ({ ...current, quantity: event.target.value }))} />
                            <Select label="Einheit" value={newLine.unit} disabled={disabled}
                                onChange={(event) => setNewLine((current) => ({ ...current, unit: event.target.value }))}
                                options={[
                                    { value: 'g', label: 'g' }, { value: 'kg', label: 'kg' }, { value: 'STK', label: 'Stk' },
                                    { value: 'SCHALE', label: 'Schale' }, { value: 'TRAY', label: 'Tray (8 Schalen)' },
                                    { value: 'KISTE_12', label: 'Mehrwegkiste (12 Schalen)' }, { value: 'KISTE_6', label: 'Mehrwegkiste (6 Schalen)' },
                                    { value: 'KARTON_6', label: 'Karton (6 Schalen)' },
                                ]} />
                            <div>
                                <Input label="Preis (€ netto)" type="number" min="0" step="0.01" value={newLine.unit_price} disabled={disabled}
                                    onChange={(event) => {
                                        setPriceError('');
                                        setNewLine((current) => ({ ...current, unit_price: event.target.value, price_manually_edited: true, is_customer_specific: false }));
                                    }} />
                                {newLine.is_customer_specific && <span className="text-xs font-medium text-green-700 dark:text-green-400">Sonderpreis</span>}
                            </div>
                        </div>
                        {priceLoading && <p role="status" className="text-sm">Kundenpreis wird geladen…</p>}
                        {priceError && <p role="alert" className="text-red-600 text-sm">{priceError}</p>}
                        <Button variant="secondary" icon={<Plus className="w-4 h-4" />} onClick={addLine}
                            disabled={disabled || priceLoading || !!priceError || !newLine.product_id}>Position hinzufügen</Button>
                    </div> : !istStorniert && <p className="text-sm text-gray-500">
                        Positionen können nur bei Entwürfen und bestätigten Bestellungen hinzugefügt werden.
                    </p>}
                </section>
                <section className="space-y-3 border-t border-gray-200 dark:border-gray-700 pt-4">
                    <h3 className="font-semibold">Stornieren</h3>
                    {stornierbar ? <>
                        <Textarea label="Stornogrund" required value={cancelReason} disabled={busy}
                            onChange={(event) => setCancelReason(event.target.value)} />
                        <Button variant="danger" onClick={cancelOrder} disabled={busy}>Bestellung stornieren</Button>
                    </> : <p className="text-sm text-gray-500">
                        {istStorniert ? 'Diese Bestellung ist bereits storniert.'
                            : currentOrder.status === 'IN_PRODUKTION' ? 'Eine Bestellung in Produktion kann nicht mehr storniert werden.'
                                : 'Eine gelieferte oder fakturierte Bestellung kann nicht mehr storniert werden.'}
                    </p>}
                </section>
            </div>}
        </Modal>
    );
}
