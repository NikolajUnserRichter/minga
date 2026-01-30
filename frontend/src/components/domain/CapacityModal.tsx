import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../ui/Modal';
import { Input, Select, SelectOption, Button } from '../ui';
import { capacityApi } from '../../services/api';
import { Capacity, ResourceType } from '../../types';

interface CapacityModalProps {
    open: boolean;
    onClose: () => void;
    capacity?: Capacity | null; // If null, create mode
}

const typeOptions: SelectOption[] = [
    { value: 'REGAL', label: 'Regal / Stellplatz' },
    { value: 'TRAY', label: 'Tray / Behälter' },
    { value: 'ARBEITSZEIT', label: 'Arbeitszeit / Personal' },
];

export function CapacityModal({ open, onClose, capacity }: CapacityModalProps) {
    const queryClient = useQueryClient();
    const isEdit = !!capacity;

    const [formData, setFormData] = useState({
        name: '',
        ressource_typ: 'REGAL' as ResourceType,
        max_kapazitaet: 0,
        aktuell_belegt: 0,
    });

    useEffect(() => {
        if (capacity) {
            setFormData({
                name: capacity.name || '',
                ressource_typ: capacity.ressource_typ,
                max_kapazitaet: capacity.max_kapazitaet,
                aktuell_belegt: capacity.aktuell_belegt,
            });
        } else {
            setFormData({
                name: '',
                ressource_typ: 'REGAL',
                max_kapazitaet: 100,
                aktuell_belegt: 0,
            });
        }
    }, [capacity, open]);

    const mutation = useMutation({
        mutationFn: (data: typeof formData) => {
            if (isEdit && capacity) {
                return capacityApi.update(capacity.id, data);
            }
            return capacityApi.create(data);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['capacities'] });
            onClose();
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        mutation.mutate(formData);
    };

    return (
        <Modal
            open={open}
            onClose={onClose}
            title={isEdit ? 'Ressource bearbeiten' : 'Neue Ressource hinzufügen'}
            size="md"
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
                        Abbrechen
                    </Button>
                    <Button onClick={handleSubmit} loading={mutation.isPending}>
                        Speichern
                    </Button>
                </>
            }
        >
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input
                    label="Name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="z.B. Regal A"
                    required
                />

                <Select
                    label="Typ"
                    options={typeOptions}
                    value={formData.ressource_typ}
                    onChange={(e) =>
                        setFormData({ ...formData, ressource_typ: e.target.value as ResourceType })
                    }
                    disabled={isEdit}
                />

                <div className="grid grid-cols-2 gap-4">
                    <Input
                        label="Maximale Kapazität"
                        type="number"
                        value={formData.max_kapazitaet}
                        onChange={(e) =>
                            setFormData({ ...formData, max_kapazitaet: parseInt(e.target.value) || 0 })
                        }
                        required
                    />

                    <Input
                        label="Aktuell belegt"
                        type="number"
                        value={formData.aktuell_belegt}
                        onChange={(e) =>
                            setFormData({ ...formData, aktuell_belegt: parseInt(e.target.value) || 0 })
                        }
                        required
                    />
                </div>
            </form>
        </Modal>
    );
}
