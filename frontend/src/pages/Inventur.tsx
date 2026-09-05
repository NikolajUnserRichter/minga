import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ClipboardList, FileDown, FileText, Lock, Plus, Printer } from 'lucide-react';
import { inventurApi, Inventur as InventurTyp, InventurPosition } from '../services/api';
import { getErrorMessage } from '../services/errors';
import { PageHeader } from '../components/common/Layout';
import { Badge, Button, EmptyState, Input, Modal, PageLoader, Select, useToast } from '../components/ui';

/**
 * Inventur: Stichtagszählung für Jahresabschluss und Zertifizierung.
 * Soll wird beim Anlegen eingefroren; die Erfassung ist bewusst großflächig
 * gehalten, damit sie auf dem Tablet in der Halle bedienbar ist.
 */

const TYPEN = [
  { value: 'JAHRESINVENTUR', label: 'Jahresinventur' },
  { value: 'STICHPROBE', label: 'Stichprobe' },
  { value: 'ANLASSINVENTUR', label: 'Anlassinventur' },
];

const ITEM_LABEL: Record<string, string> = {
  SAATGUT: 'Saatgut', SUBSTRAT: 'Substrat', VERPACKUNG: 'Verpackung',
  FERTIGWARE: 'Fertigware', PFANDKISTE: 'Pfandkiste',
};

export default function Inventur() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [neuOffen, setNeuOffen] = useState(false);
  const [typ, setTyp] = useState('JAHRESINVENTUR');
  const [stichtag, setStichtag] = useState(new Date().toISOString().split('T')[0]);
  const [aktiveId, setAktiveId] = useState<string | null>(null);

  const { data: inventuren, isLoading } = useQuery({
    queryKey: ['inventuren'],
    queryFn: inventurApi.list,
  });

  const { data: aktive } = useQuery({
    queryKey: ['inventur', aktiveId],
    queryFn: () => inventurApi.get(aktiveId!),
    enabled: !!aktiveId,
  });

  const neu = useMutation({
    mutationFn: () => inventurApi.create({ typ, count_date: stichtag }),
    onSuccess: (inv) => {
      queryClient.invalidateQueries({ queryKey: ['inventuren'] });
      setNeuOffen(false);
      setAktiveId(inv.id);
      toast.success(`Inventur ${inv.count_number} angelegt — Sollbestand ist eingefroren`);
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Inventur konnte nicht angelegt werden')),
  });

  const zaehlen = useMutation({
    mutationFn: ({ itemId, menge, notes }: { itemId: string; menge?: number; notes?: string }) =>
      inventurApi.updateItem(aktiveId!, itemId, {
        ...(menge !== undefined ? { counted_quantity: menge } : {}),
        ...(notes !== undefined ? { notes } : {}),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventur', aktiveId] }),
    onError: (e) => toast.error(getErrorMessage(e, 'Zählung konnte nicht gespeichert werden')),
  });

  const abschliessen = useMutation({
    mutationFn: () => inventurApi.finalize(aktiveId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventuren'] });
      queryClient.invalidateQueries({ queryKey: ['inventur', aktiveId] });
      toast.success('Inventur abgeschlossen — Differenzen sind zum Stichtag gebucht');
    },
    // Der 400er trägt die Liste der unerklärten Differenzen — genau die zeigen
    onError: (e) => toast.error(getErrorMessage(e, 'Abschluss nicht möglich')),
  });

  const abgeschlossen = aktive?.status === 'ABGESCHLOSSEN';

  const differenzKlasse = (p: InventurPosition) => {
    if (p.difference === null || p.counted_quantity === null) return '';
    const d = Number(p.difference);
    if (d === 0) return 'text-green-700 dark:text-green-400';
    const basis = Math.abs(Number(p.system_quantity)) || 1;
    return Math.abs(d) / basis > 0.05
      ? 'text-red-600 dark:text-red-400 font-semibold'
      : 'text-amber-700 dark:text-amber-400';
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventur"
        subtitle="Stichtagszählung — Soll eingefroren, Differenzen werden zum Stichtag gebucht"
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setNeuOffen(true)}>
            Neue Inventur
          </Button>
        }
      />

      {isLoading ? <PageLoader /> : (
        <div className="card overflow-x-auto">
          {(inventuren ?? []).length === 0 ? (
            <EmptyState title="Noch keine Inventur"
              description="Eine neue Inventur friert den Sollbestand ein und erzeugt die Zählliste." />
          ) : (
            <table className="table">
              <thead>
                <tr><th>Nummer</th><th>Typ</th><th>Stichtag</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {(inventuren ?? []).map((inv: InventurTyp) => (
                  <tr key={inv.id} className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      onClick={() => setAktiveId(inv.id)}>
                    <td className="font-medium">{inv.count_number}</td>
                    <td>{TYPEN.find(t => t.value === inv.typ)?.label || inv.typ}</td>
                    <td>{new Date(inv.count_date).toLocaleDateString('de-DE')}</td>
                    <td>
                      <Badge variant={inv.status === 'ABGESCHLOSSEN' ? 'success' : 'warning'}>
                        {inv.status === 'ABGESCHLOSSEN' ? 'Abgeschlossen' : 'In Erfassung'}
                      </Badge>
                    </td>
                    <td className="text-right"><ClipboardList className="w-4 h-4 text-gray-400 inline" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Anlegen */}
      <Modal open={neuOffen} onClose={() => setNeuOffen(false)} title="Neue Inventur">
        <div className="space-y-4">
          <Select label="Typ" value={typ} onChange={(e) => setTyp(e.target.value)} options={TYPEN} />
          <Input label="Stichtag" type="date" value={stichtag}
                 onChange={(e) => setStichtag(e.target.value)}
                 hint="Korrekturen werden auf diesen Tag gebucht" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Gezählt wird alles: Saatgut, Substrate, Verpackungen und fertige Erzeugnisse.
            Der Sollbestand wird beim Anlegen eingefroren.
          </p>
          <div className="flex justify-end gap-2">
            <button className="btn btn-secondary" onClick={() => setNeuOffen(false)}>Abbrechen</button>
            <Button onClick={() => neu.mutate()} loading={neu.isPending}>Anlegen</Button>
          </div>
        </div>
      </Modal>

      {/* Erfassung */}
      <Modal open={!!aktiveId} onClose={() => setAktiveId(null)}
             title={aktive ? `${aktive.count_number} · Stichtag ${new Date(aktive.count_date).toLocaleDateString('de-DE')}` : 'Inventur'}>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-secondary btn-sm"
              onClick={() => inventurApi.zaehlliste(aktiveId!, true).catch(() => toast.error('PDF fehlgeschlagen'))}>
              <Printer className="w-4 h-4" /> Zählliste (blind)
            </button>
            <button className="btn btn-secondary btn-sm"
              onClick={() => inventurApi.export(aktiveId!, 'pdf').catch(() => toast.error('PDF fehlgeschlagen'))}>
              <FileText className="w-4 h-4" /> Abschluss-PDF
            </button>
            <button className="btn btn-secondary btn-sm"
              onClick={() => inventurApi.export(aktiveId!, 'xlsx').catch(() => toast.error('Export fehlgeschlagen'))}>
              <FileDown className="w-4 h-4" /> XLSX
            </button>
          </div>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {(aktive?.items ?? []).map((p) => (
              <div key={p.id} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/40 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <Badge variant="gray" size="sm">{ITEM_LABEL[p.item_type] || p.item_type}</Badge>
                    <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
                      Soll: {Number(p.system_quantity).toLocaleString('de-DE')} {p.unit}
                    </span>
                  </div>
                  {p.difference !== null && p.counted_quantity !== null && (
                    <span className={`text-sm ${differenzKlasse(p)}`}>
                      Differenz: {Number(p.difference).toLocaleString('de-DE')} {p.unit}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    type="number" step="any" inputMode="decimal"
                    className="input flex-1 text-lg"
                    placeholder={`Gezählt (${p.unit})`}
                    defaultValue={p.counted_quantity ?? ''}
                    disabled={abgeschlossen}
                    onBlur={(e) => {
                      const v = e.target.value;
                      if (v !== '' && Number(v) !== Number(p.counted_quantity)) {
                        zaehlen.mutate({ itemId: p.id, menge: Number(v) });
                      }
                    }}
                  />
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="Bemerkung (Pflicht ab 5 % Abweichung)"
                    defaultValue={p.notes ?? ''}
                    disabled={abgeschlossen}
                    onBlur={(e) => {
                      if (e.target.value !== (p.notes ?? '')) {
                        zaehlen.mutate({ itemId: p.id, notes: e.target.value });
                      }
                    }}
                  />
                </div>
                {p.wert !== null && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Wert (letzter EK): {Number(p.wert).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
            <p className="text-sm font-medium">
              Gesamtwert:{' '}
              {Number(aktive?.gesamtwert ?? 0).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
            </p>
            {abgeschlossen ? (
              <Badge variant="success"><Lock className="w-3 h-3 inline mr-1" />Abgeschlossen</Badge>
            ) : (
              <Button onClick={() => abschliessen.mutate()} loading={abschliessen.isPending}>
                Abschließen &amp; Differenzen buchen
              </Button>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
