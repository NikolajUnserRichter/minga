import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Package, Trash } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Badge, Button, Input, Select, SelectOption, useToast } from '../ui';
import { leergutApi, LeergutArt, LeergutBewegung, LeergutVorschau } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { useUser } from '../common/Layout';

// Leergutkonto (Paket 3, Q6): Kunden mit Pfandabrechnung „monatlich“.
// Lieferungen buchen Ausgaben, Rückgaben werden als Stückzahl erfasst,
// abgerechnet wird einmal im Monat (Rechnungen → Leergutabrechnung).

const ART_LABEL: Record<LeergutArt, string> = {
  AUSGABE: 'Ausgabe (Lieferung)',
  RUECKNAHME: 'Rücknahme',
  KORREKTUR_PLUS: 'Korrektur +',
  KORREKTUR_MINUS: 'Korrektur −',
  ANFANGSBESTAND: 'Anfangsbestand',
};

const euro = (wert: number | string) => `${Number(wert).toFixed(2).replace('.', ',')} €`;
const datum = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString('de-DE');

/** Rückgabe je Kistenart erfassen — im Leergutkonto und im Tagesplan (Halle). */
function RuecknahmeFormular({ customerId, onGespeichert }: { customerId: string; onGespeichert: () => void }) {
  const toast = useToast();
  const { data: artikel = [], isLoading } = useQuery({ queryKey: ['leergut-artikel'], queryFn: leergutApi.artikel });
  const [mengen, setMengen] = useState<Record<string, string>>({});
  const [tag, setTag] = useState('');
  const [notiz, setNotiz] = useState('');
  const positionen = Object.entries(mengen)
    .map(([product_id, menge]) => ({ product_id, menge: Number(menge) }))
    .filter((p) => Number.isInteger(p.menge) && p.menge > 0);

  const speichern = useMutation({
    mutationFn: () => leergutApi.ruecknahme(customerId, {
      positionen,
      leistungsdatum: tag || undefined,
      notiz: notiz || undefined,
    }),
    onSuccess: () => {
      toast.success('Rücknahme erfasst');
      setMengen({});
      setNotiz('');
      onGespeichert();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Rücknahme nicht gespeichert')),
  });

  if (isLoading) return null;
  if (artikel.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
        Kein Pfandartikel angelegt — Produkt mit Kategorie „Pfand“ anlegen.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {artikel.map((a) => (
          <Input
            key={a.id}
            id={`leergut-menge-${a.id}`}
            label={`${a.name} — Stück zurück`}
            type="number"
            min={0}
            step={1}
            value={mengen[a.id] ?? ''}
            onChange={(e) => setMengen({ ...mengen, [a.id]: e.target.value })}
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input id="leergut-tag" label="Rückgabetag (leer = heute)" type="date" value={tag}
               onChange={(e) => setTag(e.target.value)} />
        <Input id="leergut-notiz" label="Notiz" value={notiz} onChange={(e) => setNotiz(e.target.value)} />
      </div>
      <div className="flex justify-end">
        <Button onClick={() => speichern.mutate()} loading={speichern.isPending} disabled={positionen.length === 0}>
          Rücknahme speichern
        </Button>
      </div>
    </div>
  );
}

const KORREKTUR_OPTIONEN: SelectOption[] = [
  { value: 'KORREKTUR_MINUS', label: 'Korrektur − (zugunsten des Kunden)' },
  { value: 'KORREKTUR_PLUS', label: 'Korrektur + (zugunsten Minga Greens)' },
  { value: 'ANFANGSBESTAND', label: 'Anfangsbestand (Kisten vor dem Stichtag)' },
];

/** Dialog „Leergutkonto“ an der Kundenkarte (Verwaltung, Vertrieb, Buchhaltung). */
export function LeergutKontoModal({ open, onClose, customerId, customerName }: {
  open: boolean;
  onClose: () => void;
  customerId: string | null;
  customerName: string;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { user } = useUser();
  const verwaltung = ['ADMIN', 'SALES', 'ACCOUNTING'].includes(user.role);

  const { data: konto } = useQuery({
    queryKey: ['leergut-konto', customerId],
    queryFn: () => leergutApi.konto(customerId!),
    enabled: open && !!customerId,
  });
  const { data: artikel = [] } = useQuery({
    queryKey: ['leergut-artikel'], queryFn: leergutApi.artikel, enabled: open,
  });

  const neuLaden = () => {
    queryClient.invalidateQueries({ queryKey: ['leergut-konto', customerId] });
    queryClient.invalidateQueries({ queryKey: ['leergut-kunden'] });
  };

  const loeschen = useMutation({
    mutationFn: (id: string) => leergutApi.loeschen(id),
    onSuccess: () => { toast.success('Bewegung gelöscht'); neuLaden(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Löschen fehlgeschlagen')),
  });

  // bereits_berechnet gilt nur für den Anfangsbestand (G-Q6-2: ja/nein)
  const leer = { art: 'KORREKTUR_MINUS', product_id: '', menge: '', tag: '', notiz: '', bereits_berechnet: true };
  const [korrektur, setKorrektur] = useState(leer);
  const anfangsbestand = korrektur.art === 'ANFANGSBESTAND';
  const korrigieren = useMutation({
    mutationFn: () => leergutApi.korrektur(customerId!, {
      art: korrektur.art as 'KORREKTUR_PLUS' | 'KORREKTUR_MINUS' | 'ANFANGSBESTAND',
      product_id: korrektur.product_id,
      menge: Number(korrektur.menge),
      leistungsdatum: korrektur.tag || undefined,
      notiz: korrektur.notiz,
      bereits_berechnet: anfangsbestand ? korrektur.bereits_berechnet : undefined,
    }),
    onSuccess: () => { toast.success('Buchung erfasst'); setKorrektur(leer); neuLaden(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Buchung nicht gespeichert')),
  });

  const loeschbar = (b: LeergutBewegung) =>
    !b.invoice_id && b.art !== 'AUSGABE' && (b.art === 'RUECKNAHME' || verwaltung);

  return (
    <Modal
      open={open && !!customerId}
      onClose={onClose}
      title={`Leergutkonto — ${customerName}`}
      size="xl"
      footer={<Button variant="secondary" onClick={onClose}>Schließen</Button>}
    >
      <div className="space-y-5">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          {konto?.pfand_monatlich_ab
            ? `Pfand läuft seit ${datum(konto.pfand_monatlich_ab)} über das Leergutkonto und wird monatlich abgerechnet.`
            : 'Der Kunde rechnet Pfand nicht (mehr) monatlich ab. Offene Bewegungen rechnet die nächste Leergutabrechnung noch ab.'}
        </p>

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 dark:text-gray-400">
              <th className="py-1">Kistenart</th><th>beim Kunden</th><th>Wert</th><th>noch abzurechnen</th>
            </tr>
          </thead>
          <tbody>
            {(konto?.salden ?? []).length === 0 ? (
              <tr><td colSpan={4} className="py-2 italic text-gray-500">Noch keine Bewegungen.</td></tr>
            ) : konto!.salden.map((s) => (
              <tr key={s.product_id} className="border-t border-gray-100 dark:border-gray-700">
                <td className="py-1">{s.artikel}</td>
                <td>{s.stueck} Stück</td>
                <td>{euro(s.wert)}</td>
                <td>{s.offen_stueck} Stück · {euro(s.offen_wert)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="border rounded p-3 dark:border-gray-700 space-y-2">
          <h4 className="font-medium text-sm">Rückgabe erfassen</h4>
          {customerId && <RuecknahmeFormular customerId={customerId} onGespeichert={neuLaden} />}
        </div>

        {verwaltung && (
          <div className="border rounded p-3 dark:border-gray-700 space-y-2">
            <h4 className="font-medium text-sm">Korrektur oder Anfangsbestand</h4>
            <div className="grid grid-cols-2 gap-3">
              <Select label="Art" options={KORREKTUR_OPTIONEN} value={korrektur.art}
                      onChange={(e) => setKorrektur({ ...korrektur, art: e.target.value })} />
              <Select label="Kistenart"
                      options={[{ value: '', label: 'wählen …' }, ...artikel.map((a) => ({ value: a.id, label: a.name }))]}
                      value={korrektur.product_id}
                      onChange={(e) => setKorrektur({ ...korrektur, product_id: e.target.value })} />
              <Input id="leergut-korrektur-menge" label="Stück" type="number" min={1} step={1} value={korrektur.menge}
                     onChange={(e) => setKorrektur({ ...korrektur, menge: e.target.value })} />
              <Input id="leergut-korrektur-tag" label="Datum (leer = heute)" type="date" value={korrektur.tag}
                     onChange={(e) => setKorrektur({ ...korrektur, tag: e.target.value })} />
            </div>
            <Input id="leergut-korrektur-notiz" label="Begründung (Pflicht)" value={korrektur.notiz}
                   onChange={(e) => setKorrektur({ ...korrektur, notiz: e.target.value })} />
            {anfangsbestand && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={korrektur.bereits_berechnet}
                  onChange={(e) => setKorrektur({ ...korrektur, bereits_berechnet: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Kisten wurden schon berechnet (Altsystem oder frühere Rechnung) — ohne Haken rechnet die
                  nächste Leergutabrechnung sie ab
                </span>
              </label>
            )}
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => korrigieren.mutate()} loading={korrigieren.isPending}
                      disabled={!korrektur.product_id || !(Number(korrektur.menge) > 0) || korrektur.notiz.trim().length < 3}>
                Buchen
              </Button>
            </div>
          </div>
        )}

        <div>
          <h4 className="font-medium text-sm mb-1">Bewegungen</h4>
          <ul className="divide-y divide-gray-100 dark:divide-gray-700 text-sm">
            {(konto?.bewegungen ?? []).map((b) => (
              <li key={b.id} className="py-1 flex items-center gap-2">
                <span className="w-24">{datum(b.leistungsdatum)}</span>
                <span className="w-40">{ART_LABEL[b.art]}</span>
                <span className="flex-1">
                  {b.menge} × {b.artikel}
                  <span className="text-gray-500"> · {b.erfasst_von ?? '—'}{b.notiz ? ` · ${b.notiz}` : ''}</span>
                </span>
                {b.invoice_id
                  ? <Badge variant="success" size="sm">abgerechnet</Badge>
                  : b.bereits_berechnet
                    ? <Badge variant="gray" size="sm">schon berechnet</Badge>
                    : <Badge variant="warning" size="sm">offen</Badge>}
                {loeschbar(b) && (
                  <button className="text-gray-400 hover:text-red-600" title="Löschen"
                          onClick={() => loeschen.mutate(b.id)}>
                    <Trash className="w-4 h-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Modal>
  );
}

/** Einstieg für die Halle im Tagesplan: Kunde wählen, Kisten zählen, speichern. */
export function LeergutRuecknahmeKnopf() {
  const queryClient = useQueryClient();
  const [offen, setOffen] = useState(false);
  const [kundeId, setKundeId] = useState('');
  const { data: kunden = [] } = useQuery({
    queryKey: ['leergut-kunden'], queryFn: leergutApi.kunden, enabled: offen,
  });
  const schliessen = () => { setOffen(false); setKundeId(''); };
  const optionen: SelectOption[] = [
    { value: '', label: 'Kunde wählen …' },
    ...kunden.map((k) => ({ value: k.customer_id, label: `${k.name} · beim Kunden: ${k.stueck_beim_kunden}` })),
  ];

  return (
    <>
      <Button variant="secondary" icon={<Package className="w-4 h-4" />} onClick={() => setOffen(true)}>
        Leergut zurück
      </Button>
      <Modal open={offen} onClose={schliessen} title="Leergut-Rücknahme" size="lg">
        <div className="space-y-4">
          {kunden.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Kein Kunde rechnet Pfand monatlich über das Leergutkonto ab.
            </p>
          ) : (
            <Select label="Kunde" options={optionen} value={kundeId} onChange={(e) => setKundeId(e.target.value)} />
          )}
          {kundeId && (
            <RuecknahmeFormular
              customerId={kundeId}
              onGespeichert={() => {
                queryClient.invalidateQueries({ queryKey: ['leergut-kunden'] });
                queryClient.invalidateQueries({ queryKey: ['leergut-konto', kundeId] });
                schliessen();
              }}
            />
          )}
        </div>
      </Modal>
    </>
  );
}

/** Rechnungen → „Leergutabrechnung“: Monat wählen, Vorschau, Entwürfe anlegen. */
export function LeergutLaufModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  // Leer = Vormonat; die Monatsgrenzen rechnet der Server (Europe/Berlin).
  const [monat, setMonat] = useState('');
  const [vorschau, setVorschau] = useState<LeergutVorschau | null>(null);
  const schliessen = () => { setVorschau(null); onClose(); };

  const vorschauMutation = useMutation({
    mutationFn: () => leergutApi.laufVorschau({ monat: monat || undefined }),
    onSuccess: (res) => setVorschau(res),
    onError: (e: any) => toast.error(getErrorMessage(e, 'Vorschau fehlgeschlagen')),
  });
  const anlegenMutation = useMutation({
    mutationFn: () => leergutApi.laufAnlegen({ monat: vorschau!.monat }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success(res.rechnungen.length
        ? `${res.rechnungen.length} Leergutbeleg(e) als Entwurf angelegt — prüfen und finalisieren; `
          + 'Korrekturen im Leergutkonto, danach den Entwurf verwerfen und neu anlegen'
        : 'Nichts abzurechnen');
      schliessen();
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Anlegen fehlgeschlagen')),
  });

  return (
    <Modal open={open} onClose={schliessen} title="Leergutabrechnung (monatlich)" size="lg">
      <div className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Je Kunde ein Beleg: ausgegebene minus zurückgenommene Kisten bis Monatsende. Die Belege entstehen
          als <b>Entwurf</b>; erst „Finalisieren“ gibt sie frei. Ihre Positionen kommen aus dem Leergutkonto
          und sind im Entwurf nicht änderbar. Lieferungen ohne gebuchte Ausgabe werden beim Anlegen nachgebucht.
        </p>
        <Input id="leergut-monat" label="Monat (leer = Vormonat)" type="month" value={monat}
               onChange={(e) => { setMonat(e.target.value); setVorschau(null); }} />

        {vorschau && (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 max-h-72 overflow-y-auto space-y-3">
            <p className="text-sm font-medium">Monat {vorschau.monat}</p>
            {vorschau.kunden.length === 0 && (
              <p className="text-sm text-gray-500 italic">Keine offenen Leergutbewegungen.</p>
            )}
            {vorschau.kunden.map((k) => (
              <div key={k.customer_id}>
                <p className="font-medium text-sm flex items-center gap-2">
                  {k.customer_name}
                  <span className="text-gray-500 font-normal">· {euro(k.summe_netto)} netto</span>
                  {k.minderung && <Badge variant="info" size="sm">Minderung</Badge>}
                  {k.pfand_abrechnung !== 'MONATLICH' && <Badge variant="warning" size="sm">Restabrechnung</Badge>}
                </p>
                <ul className="text-sm text-gray-600 dark:text-gray-300 ml-4 list-disc">
                  {k.positionen.map((p) => (
                    <li key={`${p.product_id}-${p.einzelwert}`}>
                      {p.artikel}: {p.ausgegeben} ausgegeben, {p.zurueckgenommen} zurück à {euro(p.einzelwert)}
                    </li>
                  ))}
                  {k.nachzug.map((n) => (
                    <li key={`${n.order_number}-${n.artikel}`} className="text-amber-700 dark:text-amber-300">
                      wird nachgebucht: {n.order_number} vom {datum(n.leistungsdatum)}, {n.menge} × {n.artikel}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {vorschau.uebersprungen.map((u) => (
              <p key={u.customer_id} className="text-sm text-amber-700 dark:text-amber-300">
                {u.customer_name}: {u.grund}
              </p>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={schliessen}>Abbrechen</Button>
          <Button variant="secondary" onClick={() => vorschauMutation.mutate()} loading={vorschauMutation.isPending}>
            Vorschau
          </Button>
          <Button onClick={() => anlegenMutation.mutate()} loading={anlegenMutation.isPending}
                  disabled={!vorschau || vorschau.kunden.length === 0}
                  title={!vorschau ? 'Erst die Vorschau prüfen' : ''}>
            Entwürfe anlegen
          </Button>
        </div>
      </div>
    </Modal>
  );
}
