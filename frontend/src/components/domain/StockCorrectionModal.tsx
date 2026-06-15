import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, AlertTriangle } from 'lucide-react';
import { inventoryApi } from '../../services/api';
import { Button, Input, Modal, useToast } from '../ui';
import { InventoryType } from '../../types';

interface StockCorrectionModalProps {
    open: boolean;
    onClose: () => void;
    inventoryId: string;
    currentQuantity: number;
    unit: string;
    itemType: InventoryType; // 'SEED' | 'PRODUCT' | 'PACKAGING'
    itemName: string;
}

export function StockCorrectionModal({
    open,
    onClose,
    inventoryId,
    currentQuantity,
    unit,
    itemType,
    itemName
}: StockCorrectionModalProps) {
    const toast = useToast();
    const queryClient = useQueryClient();
    const safeCurrent = Number(currentQuantity ?? 0);
    const [actualQuantity, setActualQuantity] = useState<string>(String(safeCurrent));
    const [reason, setReason] = useState('');

    useEffect(() => {
        if (open) {
            setActualQuantity(String(Number(currentQuantity ?? 0)));
            setReason('');
        }
    }, [open, currentQuantity]);

    const difference = Number(actualQuantity) - safeCurrent;
    const isGain = difference > 0;
    const isLoss = difference < 0;

    const correctionMutation = useMutation({
        mutationFn: () => inventoryApi.correctInventory({
            inventory_id: inventoryId,
            inventory_type: itemType,
            actual_quantity: Number(actualQuantity),
            reason: reason || 'Manuelle Bestandskorrektur'
        }),
        onSuccess: () => {
            queryClient.invalidateQueries();
            toast.success('Bestand korrigiert');
            onClose();
        },
        onError: () => {
            toast.error('Fehler bei der Korrektur');
        }
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        correctionMutation.mutate();
    };

    return (
        <Modal open={open} onClose={onClose} title={`Bestandskorrektur: ${itemName}`}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg flex justify-between items-center mb-4">
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Aktueller Bestand (System)</p>
                        <p className="text-xl font-bold">{safeCurrent} {unit ?? ''}</p>
                    </div>
                    {difference !== 0 && (
                        <div className={`text-right ${isGain ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                            <p className="text-sm">Differenz</p>
                            <p className="text-xl font-bold">
                                {isGain ? '+' : ''}{difference.toFixed(2)} {unit}
                            </p>
                        </div>
                    )}
                </div>

                <Input
                    label="Tatsächlicher Bestand (Gezählt)"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={actualQuantity}
                    onChange={(e) => setActualQuantity(e.target.value)}
                    endIcon={unit}
                    autoFocus
                />

                <Input
                    label="Grund für Abweichung"
                    placeholder="z.B. Zählfehler, Bruch, Schwund..."
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    required={difference !== 0}
                />

                {isLoss && (
                    <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-900/20 p-2 rounded">
                        <AlertTriangle className="w-4 h-4" />
                        <span>Achtung: Dies bucht einen Verlust von {Math.abs(difference)} {unit}.</span>
                    </div>
                )}

                <div className="flex justify-end gap-2 pt-4">
                    <Button variant="secondary" type="button" onClick={onClose}>
                        Abbrechen
                    </Button>
                    <Button
                        type="submit"
                        loading={correctionMutation.isPending}
                        disabled={Number(actualQuantity) === safeCurrent}
                    >
                        <Check className="w-4 h-4 mr-2" />
                        Korrektur buchen
                    </Button>
                </div>
            </form>
        </Modal>
    );
}

// Helper to map backend enum
export const getInventoryTypeLabel = (type: InventoryType) => {
    switch (type) {
        case 'SAATGUT': return 'Saatgut';
        case 'FERTIGWARE': return 'Fertigware';
        case 'VERPACKUNG': return 'Verpackung';
        default: return type;
    }
};
