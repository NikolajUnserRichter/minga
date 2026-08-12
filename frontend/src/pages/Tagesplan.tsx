import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Sprout, Scissors, Package, Truck, Users } from 'lucide-react';
import { productionApi } from '../services/api';
import { PageHeader } from '../components/common/Layout';
import { Input, EmptyState, Badge, PageLoader } from '../components/ui';

/**
 * Tagesplan für Mitarbeiter: was ist heute zu tun?
 * Aussaat · Ernte · Verpacken · Ausliefern — auf einer Seite.
 */
export default function Tagesplan() {
  const today = new Date().toISOString().split('T')[0];
  const [date, setDate] = useState(today);

  const { data: plan, isLoading } = useQuery({
    queryKey: ['day-plan', date],
    queryFn: () => productionApi.getDayPlan(date),
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
        <div key={i} className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{a.seed_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {a.trays} Kisten
              {a.saatgut_gramm > 0 && ` · ${a.saatgut_gramm.toFixed(0)} g Saatgut`}
              {a.substrat && (
                <> · Substrat: <span className="font-semibold text-green-700 dark:text-green-300">{a.substrat}</span></>
              )}
            </p>
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
      empty: 'Nichts zu verpacken (Lieferungen von morgen + Same-Day erscheinen hier).',
      rows: (plan?.verpacken ?? []).map((o, i) => (
        <div key={i} className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{o.customer_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {o.order_number} · {o.positionen} Positionen · Lieferung {new Date(o.delivery_date).toLocaleDateString('de-DE')}
            </p>
          </div>
          <Badge variant={o.status === 'Entwurf' ? 'warning' : 'info'}>{o.status}</Badge>
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
