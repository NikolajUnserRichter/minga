import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Sprout, Scissors, Package, Truck, Users, Boxes, ListTodo, Plus, FileText, ChevronDown, ChevronRight } from 'lucide-react';
import { productionApi, staffApi, documentsApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { Input, EmptyState, Badge, PageLoader, Button, useToast } from '../components/ui';

/**
 * Tagesplan für Mitarbeiter: was ist heute zu tun?
 * Aussaat · Ernte · Verpacken · Ausliefern — auf einer Seite.
 */
export default function Tagesplan() {
  const today = new Date().toISOString().split('T')[0];
  const [date, setDate] = useState(today);
  const [neueAufgabe, setNeueAufgabe] = useState('');
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: plan, isLoading } = useQuery({
    queryKey: ['day-plan', date],
    queryFn: () => productionApi.getDayPlan(date),
  });

  const invalidateAufgaben = () => {
    queryClient.invalidateQueries({ queryKey: ['day-plan'] });
    queryClient.invalidateQueries({ queryKey: ['staff-tasks'] });
  };

  const addTaskMutation = useMutation({
    mutationFn: (titel: string) => staffApi.createTask({ titel, datum: date }),
    onSuccess: () => {
      setNeueAufgabe('');
      invalidateAufgaben();
    },
    onError: () => toast.error('Aufgabe konnte nicht angelegt werden'),
  });

  const toggleTaskMutation = useMutation({
    mutationFn: ({ id, erledigt }: { id: string; erledigt: boolean }) =>
      staffApi.updateTask(id, { erledigt }),
    onSuccess: () => invalidateAufgaben(),
    onError: () => toast.error('Konnte Aufgabe nicht aktualisieren'),
  });

  // Sortenbedarf des Packtags: Bundles sind bereits in Komponenten aufgelöst
  const { data: packaging } = useQuery({
    queryKey: ['packaging-plan', date],
    queryFn: () => productionApi.getPackagingPlan(date),
  });

  // Welche Verpacken-Bestellung ist aufgeklappt (Positionen sichtbar)
  const [offeneBestellung, setOffeneBestellung] = useState<string | null>(null);

  // Packliste aus dem Tagesplan heraus: existiert schon ein Lieferschein,
  // nimm dessen Packliste — sonst wird er angelegt (Positionen 1:1 aus der
  // Bestellung) und das PDF öffnet sich direkt.
  const packlisteMutation = useMutation({
    mutationFn: async (orderId: string) => {
      const notes = await documentsApi.listDeliveryNotes(orderId);
      const note = notes[0] ?? (await documentsApi.createDeliveryNote(orderId, {}));
      await documentsApi.downloadPackingListPdf(note);
    },
    onError: () => toast.error('Packliste konnte nicht geöffnet werden'),
  });

  if (isLoading) return <PageLoader />;

  const sections = [
    {
      key: 'aussaat',
      title: 'Aussaat',
      icon: <Sprout className="w-5 h-5 text-green-600 dark:text-green-400" />,
      count: plan?.aussaat.length ?? 0,
      empty: 'Keine Aussaaten geplant (genehmigte Produktionsvorschläge erscheinen hier).',
      rows: (plan?.aussaat ?? []).map((a, i) => (
        <div key={i} className="flex items-start justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{a.seed_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {a.trays} Kisten
              {a.saatgut_gramm > 0 && ` · ${a.saatgut_gramm.toFixed(0)} g Saatgut`}
              {a.substrat && (
                <> · Substrat: <span className="font-semibold text-green-700 dark:text-green-300">{a.substrat}</span></>
              )}
            </p>
            {/* Mischsorte: die Einzelsorten mit Mengen — wer mischt, braucht
                sie hier und nicht in den Stammdaten. */}
            {(a.mix_components ?? []).length > 0 && (
              <div className="mt-2 pl-3 border-l-2 border-green-200 dark:border-green-800 space-y-0.5">
                {a.mix_components.map((k, j) => (
                  <p key={j} className="text-sm text-gray-600 dark:text-gray-300">
                    {k.seed_name || 'Unbekannt'}:{' '}
                    <span className="font-semibold">{k.gramm_gesamt.toFixed(0)} g</span>
                    <span className="text-gray-400"> ({k.gramm_pro_tray.toFixed(0)} g/Kiste)</span>
                    {k.charge_nummer && <span className="text-gray-400"> · Charge {k.charge_nummer}</span>}
                  </p>
                ))}
              </div>
            )}
          </div>
          <Badge variant={a.status === 'GENEHMIGT' ? 'success' : 'warning'}>{a.status}</Badge>
        </div>
      )),
    },
    {
      key: 'ernte',
      title: 'Ernte',
      icon: <Scissors className="w-5 h-5 text-amber-600 dark:text-amber-400" />,
      count: plan?.ernte.length ?? 0,
      empty: 'Keine Chargen im Erntefenster.',
      rows: (plan?.ernte ?? []).map((e) => (
        <div key={e.batch_id} className="flex items-center justify-between p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{e.seed_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {e.trays} Kisten · Regal {e.regal_position || '—'} · optimal {new Date(e.optimal).toLocaleDateString('de-DE')}
            </p>
          </div>
          {e.ist_optimal_heute && <Badge variant="success">Heute optimal</Badge>}
        </div>
      )),
    },
    {
      key: 'verpacken',
      title: 'Verpacken',
      icon: <Package className="w-5 h-5 text-blue-600 dark:text-blue-400" />,
      count: plan?.verpacken.length ?? 0,
      empty: 'Nichts zu verpacken (Bestellungen werden am Tag vor der Lieferung gepackt).',
      rows: (plan?.verpacken ?? []).map((o) => (
        <div key={o.order_id} className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setOffeneBestellung(offeneBestellung === o.order_id ? null : o.order_id)}
          >
            <div className="flex items-center gap-2">
              {offeneBestellung === o.order_id
                ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
              <div>
                <p className="font-medium text-gray-900 dark:text-white">{o.customer_name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {o.order_number} · {o.positionen} Positionen · Lieferung {new Date(o.delivery_date).toLocaleDateString('de-DE')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {o.packing_date_explizit && <Badge variant="warning">Packtag fix</Badge>}
              <Badge variant={o.status === 'Entwurf' ? 'warning' : 'info'}>{o.status}</Badge>
              <button
                className="btn btn-ghost btn-sm"
                title="Packliste öffnen"
                disabled={packlisteMutation.isPending}
                onClick={(e) => {
                  e.stopPropagation();
                  packlisteMutation.mutate(o.order_id);
                }}
              >
                <FileText className="w-4 h-4" />
                Packliste
              </button>
            </div>
          </div>
          {/* Aufgeklappt: was in die Kiste gehört, ohne Seitenwechsel */}
          {offeneBestellung === o.order_id && (
            <div className="mt-2 ml-6 pl-3 border-l-2 border-blue-200 dark:border-blue-800 space-y-0.5">
              {o.lines.map((l, j) => (
                <p key={j} className="text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-semibold">{Number(l.quantity).toLocaleString('de-DE')} {l.unit}</span>{' '}
                  {l.product_name}
                </p>
              ))}
            </div>
          )}
        </div>
      )),
    },
    {
      key: 'ausliefern',
      title: 'Ausliefern',
      icon: <Truck className="w-5 h-5 text-purple-600 dark:text-purple-400" />,
      count: plan?.ausliefern.length ?? 0,
      empty: 'Keine Auslieferungen an diesem Tag.',
      rows: (plan?.ausliefern ?? []).map((o, i) => (
        <div key={i} className="flex items-center justify-between p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{o.customer_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{o.order_number} · {o.positionen} Positionen</p>
          </div>
          <Badge variant={o.status === 'Entwurf' ? 'warning' : 'info'}>{o.status}</Badge>
        </div>
      )),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tagesplan"
        subtitle={new Date(date).toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}
        actions={
          <div className="w-44">
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        }
      />

      {/* Dienst: wer arbeitet an dem Tag */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h3 className="card-title flex items-center gap-2">
            <Users className="w-5 h-5 text-minga-600 dark:text-minga-400" />
            Im Dienst
          </h3>
          <Link to="/staff-schedule" className="text-sm text-minga-600 dark:text-minga-400 hover:underline">
            Dienstplan bearbeiten
          </Link>
        </div>
        <div className="card-body">
          {(plan?.dienst ?? []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Niemand eingeteilt — Schichten im Dienstplan anlegen.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(plan?.dienst ?? []).map((d, i) => (
                <div key={i} className="px-3 py-2 rounded-lg bg-minga-50 dark:bg-minga-900/20 border border-minga-100 dark:border-minga-800">
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{d.employee_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {d.start_time && d.end_time ? `${d.start_time}–${d.end_time}` : 'ganztags'}
                    {d.aufgabe && ` · ${d.aufgabe}`}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Zusatzaufgaben ohne Produktionsbezug: Kisten spülen, Reinigen,
          Hanfmatten auffüllen, Müllabholung — hier abhakbar. */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h3 className="card-title flex items-center gap-2">
            <ListTodo className="w-5 h-5 text-minga-600 dark:text-minga-400" />
            Zusätzliche Aufgaben
          </h3>
          <Link to="/staff-schedule" className="text-sm text-minga-600 dark:text-minga-400 hover:underline">
            Serien & Zuordnung im Dienstplan
          </Link>
        </div>
        <div className="card-body space-y-3">
          {(plan?.aufgaben ?? []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Keine Zusatzaufgaben für diesen Tag.
            </p>
          ) : (
            <div className="space-y-2">
              {(plan?.aufgaben ?? []).map((a) => (
                <label
                  key={a.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-700/40 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
                    checked={a.erledigt}
                    onChange={() => toggleTaskMutation.mutate({ id: a.id, erledigt: !a.erledigt })}
                  />
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium ${a.erledigt ? 'line-through text-gray-400' : 'text-gray-900 dark:text-white'}`}>
                      {a.titel}
                    </p>
                    {a.beschreibung && (
                      <p className="text-sm text-gray-500 dark:text-gray-400">{a.beschreibung}</p>
                    )}
                  </div>
                  {a.employee_name && <Badge variant="gray">{a.employee_name}</Badge>}
                </label>
              ))}
            </div>
          )}

          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const titel = neueAufgabe.trim();
              if (titel) addTaskMutation.mutate(titel);
            }}
          >
            <div className="flex-1">
              <Input
                value={neueAufgabe}
                onChange={(e) => setNeueAufgabe(e.target.value)}
                placeholder="Aufgabe für diesen Tag, z.B. Kisten spülen"
              />
            </div>
            <Button
              type="submit"
              variant="secondary"
              loading={addTaskMutation.isPending}
              disabled={!neueAufgabe.trim()}
              icon={<Plus className="w-4 h-4" />}
            >
              Hinzufügen
            </Button>
          </form>
        </div>
      </div>

      {/* Sortenbedarf: was muss für die heute zu packenden Bestellungen
          bereitstehen — Bundles (Genussmix & Co.) sind aufgelöst. */}
      {(packaging?.komponenten ?? []).length > 0 && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h3 className="card-title flex items-center gap-2">
              <Boxes className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              Sortenbedarf zum Packen
            </h3>
            <Badge variant="info">{packaging?.komponenten.length}</Badge>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {(packaging?.komponenten ?? []).map((k, i) => (
                <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <p className="font-medium text-gray-900 dark:text-white">{k.product_name}</p>
                  <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
                    {Number(k.total_quantity).toLocaleString('de-DE')}
                  </p>
                  {k.aus_bundles.length > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">inkl. {k.aus_bundles.join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {sections.map((s) => (
          <div key={s.key} className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title flex items-center gap-2">{s.icon}{s.title}</h3>
              <Badge variant={s.count > 0 ? 'info' : 'gray'}>{s.count}</Badge>
            </div>
            <div className="card-body">
              {s.count === 0 ? (
                <EmptyState title={`Keine Aufgaben`} description={s.empty} />
              ) : (
                <div className="space-y-2">{s.rows}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
