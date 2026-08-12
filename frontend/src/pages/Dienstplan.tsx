import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Plus, Trash } from 'lucide-react';
import { staffApi, StaffShift } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { Button, Input, Modal, useToast, PageLoader } from '../components/ui';

/** Montag der Woche, die `d` enthält. */
function mondayOf(d: Date): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7));
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function isoDate(d: Date): string {
  return d.toISOString().split('T')[0];
}

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

/**
 * Dienstplan: Wochenansicht mit Schichten pro Tag.
 * Leichtgewichtig — Mitarbeiter sind Namen (mit Autovervollständigung),
 * eine Schicht ist Name + Zeitfenster + Aufgabe.
 */
export default function Dienstplan() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [addingFor, setAddingFor] = useState<string | null>(null); // ISO-Datum
  const [deletingShift, setDeletingShift] = useState<StaffShift | null>(null);

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      return d;
    }),
    [weekStart],
  );
  const von = isoDate(days[0]);
  const bis = isoDate(days[6]);

  const { data: shifts = [], isLoading } = useQuery({
    queryKey: ['staff-shifts', von, bis],
    queryFn: () => staffApi.listShifts({ von_datum: von, bis_datum: bis }),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ['staff-employees'],
    queryFn: () => staffApi.listEmployees(),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-shifts'] });
    queryClient.invalidateQueries({ queryKey: ['staff-employees'] });
    queryClient.invalidateQueries({ queryKey: ['day-plan'] });
  };

  const deleteMutation = useMutation({
    mutationFn: (id: string) => staffApi.deleteShift(id),
    onSuccess: () => {
      invalidate();
      setDeletingShift(null);
      toast.success('Schicht gelöscht');
    },
    onError: () => toast.error('Löschen fehlgeschlagen'),
  });

  const shiftWeek = (offset: number) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + offset * 7);
    setWeekStart(d);
  };

  if (isLoading) return <PageLoader />;

  const kw = (() => {
    // ISO-Kalenderwoche des Wochen-Donnerstags
    const thursday = new Date(weekStart);
    thursday.setDate(thursday.getDate() + 3);
    const jan1 = new Date(thursday.getFullYear(), 0, 1);
    return Math.ceil(((thursday.getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7);
  })();

  const today = isoDate(new Date());

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dienstplan"
        subtitle={`KW ${kw} · ${days[0].toLocaleDateString('de-DE')} – ${days[6].toLocaleDateString('de-DE')}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => shiftWeek(-1)} icon={<ChevronLeft className="w-4 h-4" />} />
            <Button variant="secondary" size="sm" onClick={() => setWeekStart(mondayOf(new Date()))}>Heute</Button>
            <Button variant="secondary" size="sm" onClick={() => shiftWeek(1)} icon={<ChevronRight className="w-4 h-4" />} />
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
        {days.map((day, i) => {
          const iso = isoDate(day);
          const dayShifts = shifts.filter((s) => s.datum === iso);
          const isToday = iso === today;
          return (
            <div key={iso} className={`card ${isToday ? 'ring-2 ring-minga-500' : ''}`}>
              <div className="card-header px-3 py-2">
                <div className="flex items-center justify-between w-full">
                  <span className={`text-sm font-semibold ${isToday ? 'text-minga-600 dark:text-minga-400' : 'text-gray-700 dark:text-gray-300'}`}>
                    {WEEKDAYS[i]} {day.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}
                  </span>
                  <button
                    className="text-gray-400 hover:text-minga-600"
                    title="Schicht hinzufügen"
                    onClick={() => setAddingFor(iso)}
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="card-body px-3 py-2 space-y-2 min-h-[80px]">
                {dayShifts.length === 0 && (
                  <p className="text-xs text-gray-400 italic">frei</p>
                )}
                {dayShifts.map((s) => (
                  <div key={s.id} className="p-2 rounded bg-minga-50 dark:bg-minga-900/20 border border-minga-100 dark:border-minga-800 group">
                    <div className="flex items-start justify-between gap-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">{s.employee_name}</p>
                      <button
                        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 transition-opacity"
                        title="Schicht löschen"
                        onClick={() => setDeletingShift(s)}
                      >
                        <Trash className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {s.start_time && s.end_time ? `${s.start_time}–${s.end_time}` : s.start_time ? `ab ${s.start_time}` : 'ganztags'}
                      {s.aufgabe && ` · ${s.aufgabe}`}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {addingFor && (
        <AddShiftModal
          datum={addingFor}
          employees={employees}
          onClose={() => setAddingFor(null)}
          onSaved={() => {
            setAddingFor(null);
            invalidate();
          }}
        />
      )}

      <Modal
        open={!!deletingShift}
        onClose={() => setDeletingShift(null)}
        title="Schicht löschen"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeletingShift(null)}>Abbrechen</Button>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => deletingShift && deleteMutation.mutate(deletingShift.id)}
            >
              Löschen
            </Button>
          </>
        }
      >
        <p className="text-gray-600 dark:text-gray-400">
          Schicht von <strong>{deletingShift?.employee_name}</strong> am{' '}
          {deletingShift ? new Date(deletingShift.datum).toLocaleDateString('de-DE') : ''} wirklich löschen?
        </p>
      </Modal>
    </div>
  );
}

function AddShiftModal({ datum, employees, onClose, onSaved }: {
  datum: string;
  employees: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    employee_name: '',
    start_time: '08:00',
    end_time: '16:00',
    aufgabe: '',
  });

  const createMutation = useMutation({
    mutationFn: () => staffApi.createShift({
      employee_name: form.employee_name.trim(),
      datum,
      start_time: form.start_time || null,
      end_time: form.end_time || null,
      aufgabe: form.aufgabe.trim() || null,
    }),
    onSuccess: () => {
      toast.success('Schicht angelegt');
      onSaved();
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || 'Anlegen fehlgeschlagen'),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.employee_name.trim()) {
      toast.error('Bitte einen Namen angeben');
      return;
    }
    createMutation.mutate();
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Schicht am ${new Date(datum).toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit' })}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSubmit} loading={createMutation.isPending}>Anlegen</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Input
            label="Mitarbeiter"
            required
            value={form.employee_name}
            onChange={(e) => setForm({ ...form, employee_name: e.target.value })}
            placeholder="Name eingeben…"
            list="dienstplan-employees"
          />
          <datalist id="dienstplan-employees">
            {employees.map((name) => <option key={name} value={name} />)}
          </datalist>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Von"
            type="time"
            value={form.start_time}
            onChange={(e) => setForm({ ...form, start_time: e.target.value })}
          />
          <Input
            label="Bis"
            type="time"
            value={form.end_time}
            onChange={(e) => setForm({ ...form, end_time: e.target.value })}
          />
        </div>
        <Input
          label="Aufgabe (optional)"
          value={form.aufgabe}
          onChange={(e) => setForm({ ...form, aufgabe: e.target.value })}
          placeholder="z.B. Aussaat, Ernte + Verpacken, Auslieferung"
        />
      </form>
    </Modal>
  );
}
