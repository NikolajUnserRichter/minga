import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../ui/Modal';
import { Button, Input, useToast } from '../ui';
import { productionApi, seedsApi, GrowthEvent, GrowthEventTypeKey } from '../../services/api';
import { Calendar, User, Plus, Droplet, Sprout, Move, Snowflake, Package, ListChecks } from 'lucide-react';
import { getErrorMessage } from '../../services/errors';

interface Props {
  open: boolean;
  onClose: () => void;
  growBatchId: string | null;
  batchLabel?: string;
  /** Saatgut-Charge der Aussaat — bei einer Mischung stehen dort die Ausgangschargen. */
  seedBatchId?: string | null;
}

const ICONS: Partial<Record<GrowthEventTypeKey, JSX.Element>> = {
  SOAKING_STARTED:          <Droplet className="w-4 h-4" />,
  SOAKING_COMPLETED:        <Droplet className="w-4 h-4" />,
  SOWING_STARTED:           <Sprout className="w-4 h-4" />,
  SOWING_COMPLETED:         <Sprout className="w-4 h-4" />,
  MOVED_TO_GERMINATION:     <Move className="w-4 h-4" />,
  REMOVED_FROM_GERMINATION: <Move className="w-4 h-4" />,
  MOVED_TO_GROW_ROOM:       <Move className="w-4 h-4" />,
  MOVED_TO_COOLING:         <Snowflake className="w-4 h-4" />,
  PACKAGING_STARTED:        <Package className="w-4 h-4" />,
  PACKAGING_COMPLETED:      <Package className="w-4 h-4" />,
  NOTE:                     <ListChecks className="w-4 h-4" />,
};

const formatTs = (ts: string) =>
  new Date(ts).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

export function GrowthTimelineModal({ open, onClose, growBatchId, batchLabel, seedBatchId }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [employeeName, setEmployeeName] = useState('');
  const [notes, setNotes] = useState('');

  const { data: events = [] } = useQuery({
    queryKey: ['growth-events', growBatchId],
    queryFn: () => productionApi.listEvents(growBatchId!),
    enabled: open && !!growBatchId,
  });

  const { data: eventTypes = [] } = useQuery({
    queryKey: ['growth-event-types'],
    queryFn: () => productionApi.listEventTypes(),
  });

  // Bei einer normalen Charge kommt eine leere Liste zurück — dann bleibt der
  // Block aus und die Timeline sieht aus wie bisher.
  const { data: mischung = [] } = useQuery({
    queryKey: ['seed-batch-components', seedBatchId],
    queryFn: () => seedsApi.listBatchComponents(seedBatchId!),
    enabled: open && !!seedBatchId,
  });

  const createMutation = useMutation({
    mutationFn: (event_type: GrowthEventTypeKey) =>
      productionApi.createEvent(growBatchId!, {
        event_type,
        employee_name: employeeName || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['growth-events', growBatchId] });
      setNotes('');
      toast.success('Event erfasst');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Erfassen')),
  });

  return (
    <Modal
      open={open && !!growBatchId}
      onClose={onClose}
      title={`Timeline — ${batchLabel || 'Charge'}`}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>Schließen</Button>}
    >
      <div className="space-y-5">
        {/* Mischcharge: woraus wurde gemischt (Rückverfolgbarkeit) */}
        {mischung.length > 0 && (
          <div className="border rounded-lg p-3 dark:border-gray-700 bg-minga-50 dark:bg-minga-900/30">
            <h4 className="font-medium text-sm text-minga-800 dark:text-minga-200 mb-2">
              Mischung aus
            </h4>
            <ul className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
              {mischung.map((k) => (
                <li key={`${k.component_seed_id}-${k.charge_nummer}`} className="flex justify-between">
                  <span>{k.seed_name || 'Unbekannte Sorte'} · Charge #{k.charge_nummer}</span>
                  <span className="font-medium">{Number(k.menge_gramm)} g</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Quick-Add Section */}
        <div className="border rounded-lg p-3 dark:border-gray-700 bg-gray-50/40 dark:bg-gray-800/40 space-y-3">
          <h4 className="font-medium text-sm text-gray-800 dark:text-gray-200 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Neues Event erfassen
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input
              placeholder="Mitarbeiter:in (optional)"
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
            />
            <Input
              placeholder="Notiz (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
            {eventTypes.map((t) => (
              <Button
                key={t.value}
                size="sm"
                variant="secondary"
                loading={createMutation.isPending}
                icon={ICONS[t.value]}
                onClick={() => createMutation.mutate(t.value)}
              >
                {t.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div>
          <h4 className="font-medium text-sm text-gray-800 dark:text-gray-200 mb-2">
            Verlauf ({events.length})
          </h4>
          {events.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Noch keine Events erfasst. Klick oben einen Schritt an um zu starten.
            </p>
          ) : (
            <ol className="relative border-l-2 border-gray-200 dark:border-gray-700 ml-2 space-y-3">
              {events.map((ev: GrowthEvent) => {
                const label = eventTypes.find((t) => t.value === ev.event_type)?.label ?? ev.event_type;
                return (
                  <li key={ev.id} className="ml-4">
                    <div className="absolute -left-[7px] w-3 h-3 rounded-full bg-minga-500 mt-1.5" />
                    <div className="flex items-center gap-2 text-sm font-medium text-gray-800 dark:text-gray-200">
                      {ICONS[ev.event_type]} {label}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatTs(ev.occurred_at)}</span>
                      {ev.employee_name && (
                        <span className="flex items-center gap-1"><User className="w-3 h-3" />{ev.employee_name}</span>
                      )}
                    </div>
                    {ev.notes && (
                      <p className="text-xs text-gray-600 dark:text-gray-300 italic mt-1">„{ev.notes}"</p>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </Modal>
  );
}
