import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, ListTodo, Plus, Printer, Trash } from 'lucide-react';
import { staffApi, StaffShift, StaffTask } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { Button, Input, Modal, Select, useToast, PageLoader } from '../components/ui';
import { getErrorMessage } from '../services/errors';

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
  const [addingTaskFor, setAddingTaskFor] = useState<string | null>(null); // ISO-Datum
  const [deletingShift, setDeletingShift] = useState<StaffShift | null>(null);
  const [deletingTask, setDeletingTask] = useState<StaffTask | null>(null);
  const [printing, setPrinting] = useState(false);

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

  const { data: tasks = [] } = useQuery({
    queryKey: ['staff-tasks', von, bis],
    queryFn: () => staffApi.listTasks({ von_datum: von, bis_datum: bis }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-shifts'] });
    queryClient.invalidateQueries({ queryKey: ['staff-tasks'] });
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

  const toggleTaskMutation = useMutation({
    mutationFn: (task: StaffTask) => staffApi.updateTask(task.id, { erledigt: !task.erledigt }),
    onSuccess: () => invalidate(),
    onError: () => toast.error('Konnte Aufgabe nicht aktualisieren'),
  });

  const deleteTaskMutation = useMutation({
    mutationFn: ({ id, serie }: { id: string; serie: boolean }) => staffApi.deleteTask(id, serie),
    onSuccess: () => {
      invalidate();
      setDeletingTask(null);
      toast.success('Aufgabe gelöscht');
    },
    onError: () => toast.error('Löschen fehlgeschlagen'),
  });

  /** Aushang als PDF öffnen — der Druckdialog kommt aus dem PDF-Viewer. */
  const handlePrint = async () => {
    setPrinting(true);
    try {
      const blob = await staffApi.printShifts({ von_datum: von, bis_datum: bis });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Blob-URL erst freigeben, wenn der Viewer sie geladen hat
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      toast.error('Dienstplan konnte nicht erzeugt werden');
    } finally {
      setPrinting(false);
    }
  };

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
            <Button
              size="sm"
              loading={printing}
              onClick={handlePrint}
              icon={<Printer className="w-4 h-4" />}
            >
              Aushang drucken
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
        {days.map((day, i) => {
          const iso = isoDate(day);
          const dayShifts = shifts.filter((s) => s.datum === iso);
          const dayTasks = tasks.filter((t) => t.datum === iso);
          const isToday = iso === today;
          return (
            <div key={iso} className={`card ${isToday ? 'ring-2 ring-minga-500' : ''}`}>
              <div className="card-header px-3 py-2">
                <div className="flex items-center justify-between w-full">
                  <span className={`text-sm font-semibold ${isToday ? 'text-minga-600 dark:text-minga-400' : 'text-gray-700 dark:text-gray-300'}`}>
                    {WEEKDAYS[i]} {day.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      className="text-gray-400 hover:text-minga-600"
                      title="Aufgabe hinzufügen"
                      onClick={() => setAddingTaskFor(iso)}
                    >
                      <ListTodo className="w-4 h-4" />
                    </button>
                    <button
                      className="text-gray-400 hover:text-minga-600"
                      title="Schicht hinzufügen"
                      onClick={() => setAddingFor(iso)}
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <div className="card-body px-3 py-2 space-y-2 min-h-[80px]">
                {dayShifts.length === 0 && dayTasks.length === 0 && (
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

                {dayTasks.length > 0 && (
                  <div className="pt-2 mt-1 border-t border-gray-100 dark:border-gray-700 space-y-1">
                    {dayTasks.map((t) => (
                      <div key={t.id} className="flex items-start gap-1.5 group">
                        <input
                          type="checkbox"
                          className="mt-0.5 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
                          checked={t.erledigt}
                          onChange={() => toggleTaskMutation.mutate(t)}
                          title="Als erledigt markieren"
                        />
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs ${t.erledigt ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'}`}>
                            {t.titel}
                          </p>
                          {t.employee_name && (
                            <p className="text-[11px] text-gray-400">{t.employee_name}</p>
                          )}
                        </div>
                        <button
                          className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 transition-opacity"
                          title="Aufgabe löschen"
                          onClick={() => setDeletingTask(t)}
                        >
                          <Trash className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
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

      {addingTaskFor && (
        <AddTaskModal
          datum={addingTaskFor}
          employees={employees}
          onClose={() => setAddingTaskFor(null)}
          onSaved={() => {
            setAddingTaskFor(null);
            invalidate();
          }}
        />
      )}

      <Modal
        open={!!deletingTask}
        onClose={() => setDeletingTask(null)}
        title="Aufgabe löschen"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeletingTask(null)}>Abbrechen</Button>
            {deletingTask?.serie_id && (
              <Button
                variant="danger"
                loading={deleteTaskMutation.isPending}
                onClick={() => deletingTask && deleteTaskMutation.mutate({ id: deletingTask.id, serie: true })}
              >
                Serie ab hier löschen
              </Button>
            )}
            <Button
              variant="danger"
              loading={deleteTaskMutation.isPending}
              onClick={() => deletingTask && deleteTaskMutation.mutate({ id: deletingTask.id, serie: false })}
            >
              Nur diesen Termin
            </Button>
          </>
        }
      >
        <p className="text-gray-600 dark:text-gray-400">
          <strong>{deletingTask?.titel}</strong> am{' '}
          {deletingTask ? new Date(deletingTask.datum).toLocaleDateString('de-DE') : ''} löschen?
          {deletingTask?.serie_id && ' Diese Aufgabe gehört zu einer Serie — frühere Termine bleiben in jedem Fall erhalten.'}
        </p>
      </Modal>

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
    onError: (e: any) => toast.error(getErrorMessage(e, 'Anlegen fehlgeschlagen')),
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

/** Zusatzaufgabe anlegen — optional als wiederkehrende Serie (z.B. Müllabholung). */
function AddTaskModal({ datum, employees, onClose, onSaved }: {
  datum: string;
  employees: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    titel: '',
    employee_name: '',
    wiederholung: '' as '' | 'TAEGLICH' | 'WOECHENTLICH',
    wiederholung_bis: '',
  });

  const createMutation = useMutation({
    mutationFn: () => staffApi.createTask({
      titel: form.titel.trim(),
      datum,
      employee_name: form.employee_name.trim() || null,
      wiederholung: form.wiederholung || null,
      wiederholung_bis: form.wiederholung ? (form.wiederholung_bis || null) : null,
    }),
    onSuccess: (created) => {
      toast.success(created.length > 1 ? `${created.length} Termine angelegt` : 'Aufgabe angelegt');
      onSaved();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Anlegen fehlgeschlagen')),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.titel.trim()) {
      toast.error('Bitte eine Aufgabe angeben');
      return;
    }
    createMutation.mutate();
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Aufgabe am ${new Date(datum).toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit' })}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button onClick={handleSubmit} loading={createMutation.isPending}>Anlegen</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Aufgabe"
          required
          value={form.titel}
          onChange={(e) => setForm({ ...form, titel: e.target.value })}
          placeholder="z.B. Kisten spülen, Hanfmatten auffüllen, Müll rausstellen"
        />
        <div>
          <Input
            label="Mitarbeiter (optional)"
            value={form.employee_name}
            onChange={(e) => setForm({ ...form, employee_name: e.target.value })}
            placeholder="leer = gilt für den ganzen Tag"
            list="dienstplan-employees"
          />
          <datalist id="dienstplan-employees">
            {employees.map((name) => <option key={name} value={name} />)}
          </datalist>
        </div>
        <Select
          label="Wiederholung"
          value={form.wiederholung}
          onChange={(e) => setForm({ ...form, wiederholung: e.target.value as typeof form.wiederholung })}
          options={[
            { value: '', label: 'Einmalig' },
            { value: 'TAEGLICH', label: 'Täglich' },
            { value: 'WOECHENTLICH', label: 'Wöchentlich' },
          ]}
          hint="Wiederkehrende Aufgaben werden als einzelne Termine angelegt und können einzeln abgehakt werden."
        />
        {form.wiederholung && (
          <Input
            label="Wiederholen bis"
            type="date"
            value={form.wiederholung_bis}
            onChange={(e) => setForm({ ...form, wiederholung_bis: e.target.value })}
            hint="Leer = 8 Wochen"
          />
        )}
      </form>
    </Modal>
  );
}
