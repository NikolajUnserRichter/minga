import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal, Button, Select, Badge, useToast, type SelectOption } from '../ui';
import { monatsrechnungApi, type MonatsrechnungHinweis, type Monatsrechnungen } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { useUser } from '../common/Layout';

// Monatsrechnungen (B5): Monat wählen → Stand prüfen → Entwürfe anlegen.
// Die Monatsgrenzen rechnet der Server aus JJJJ-MM; der Client rechnet
// kein Datum (früher: Von/Bis mit toISOString — in Europe/Berlin ergab das
// den Vormonatsletzten).

/** Die letzten zwölf abgeschlossenen Monate, neuester zuerst. Wert JJJJ-MM. */
export function abgeschlosseneMonate(heute = new Date()): SelectOption[] {
  const monate: SelectOption[] = [];
  for (let i = 1; i <= 12; i++) {
    const d = new Date(heute.getFullYear(), heute.getMonth() - i, 1);
    const wert = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    monate.push({ value: wert, label: d.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' }) });
  }
  return monate;
}

export function monatsName(monat: string): string {
  const [jahr, mon] = monat.split('-').map(Number);
  return new Date(jahr, mon - 1, 1).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
}

const HINWEIS_TITEL: Record<MonatsrechnungHinweis['art'], string> = {
  OHNE_LIEFERSCHEIN: 'Bestellungen ohne Lieferschein',
  NACHGEKOMMEN: 'Lieferscheine nach dem Entwurf',
  FRUEHERER_MONAT: 'Offene Lieferscheine aus früheren Monaten',
  INAKTIV: 'Inaktiver Kunde mit Lieferungen',
  NICHT_QUITTIERT: 'Lieferscheine ohne Quittung',
  KEINE_LIEFERUNGEN: 'Keine Lieferungen',
  EINZELABRECHNUNG: 'Nicht enthalten (Rechnung je Lieferung)',
};

// Laufstatus aus billing_runs — die Oberfläche zeigt keine Enum-Werte (Paket 2, P1;
// belegStatusLabel kennt diese Werte nicht).
const LAUF_STATUS_TITEL: Record<string, string> = {
  LAEUFT: 'läuft',
  FERTIG: 'fertig',
  FEHLER: 'mit Fehler',
};

/** Hinweise, die eine Handlung verlangen (die übrigen sind nur Information). */
export const WICHTIGE_HINWEISE: MonatsrechnungHinweis['art'][] = [
  'OHNE_LIEFERSCHEIN', 'NACHGEKOMMEN', 'FRUEHERER_MONAT', 'INAKTIV',
];

interface Props {
  open: boolean;
  onClose: () => void;
  /** Vorauswahl JJJJ-MM; ohne Angabe der Vormonat */
  monat?: string;
  /** Öffnet einen Monatsbeleg zur Prüfung (Rechnungsliste: Detailansicht) */
  onRechnungOeffnen?: (invoiceId: string) => void;
}

export function MonatsrechnungenDialog({ open, onClose, monat: vorauswahl, onRechnungOeffnen }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { user } = useUser();
  const istAdmin = user.role === 'ADMIN';
  const monate = abgeschlosseneMonate();
  const [monat, setMonat] = useState<string>(vorauswahl ?? String(monate[0].value));

  // Schlüssel unter ['invoices', …]: jede Rechnungsänderung (Finalisieren,
  // Verwerfen, Storno) invalidiert ['invoices'] und damit auch diesen Stand.
  const { data: stand, isLoading, isError, error } = useQuery({
    queryKey: ['invoices', 'monatsrechnungen', monat],
    queryFn: () => monatsrechnungApi.stand(monat),
    enabled: open,
  });

  const laufMutation = useMutation({
    mutationFn: () => monatsrechnungApi.lauf(monat),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success(res.angelegt.length
        ? `${res.angelegt.length} Entwurf/Entwürfe angelegt — bitte prüfen und freigeben`
        : 'Keine neuen Entwürfe — alles schon angelegt oder nichts abzurechnen');
      if (res.fehler.length) {
        toast.error(`Nicht angelegt: ${res.fehler.map((f) => f.customer_name).join(', ')}`);
      }
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Monatslauf fehlgeschlagen')),
  });

  const offeneEntwuerfe = stand?.entwuerfe.filter((e) => e.status === 'ENTWURF') ?? [];

  return (
    <Modal open={open} onClose={onClose} title="Monatsrechnungen" size="lg">
      <div className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Kunden mit „Monatlicher Sammelrechnung“ bekommen je Monat einen Rechnungsentwurf über
          alle noch nicht abgerechneten Lieferscheine. Die Rechnungsnummer entsteht erst beim
          Freigeben; versendet wird nichts automatisch.
        </p>
        <Select label="Leistungsmonat" options={monate} value={monat}
                onChange={(e) => setMonat(e.target.value)} />

        {isLoading && <p className="text-sm text-gray-500">Wird geladen …</p>}
        {isError && <p className="text-sm text-red-600">{getErrorMessage(error, 'Stand konnte nicht geladen werden')}</p>}

        {stand && (
          <>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Automatischer Vorschlag am 1. um 06:30: {stand.automatik_an ? 'an' : 'aus (Einstellungen)'}
              {stand.letzter_lauf && ` · letzter Lauf ${new Date(stand.letzter_lauf.gestartet_am + 'Z').toLocaleString('de-DE')}`
                + ` (${stand.letzter_lauf.art === 'MONAT_AUTO' ? 'automatisch' : 'von Hand'}, ${LAUF_STATUS_TITEL[stand.letzter_lauf.status] ?? stand.letzter_lauf.status})`}
            </p>

            <section>
              <h4 className="font-medium text-sm mb-1">Vorhandene Monatsbelege</h4>
              {stand.entwuerfe.length === 0 ? (
                <p className="text-sm text-gray-500 italic">Noch keine.</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {stand.entwuerfe.map((e) => (
                    <li key={e.invoice_id} className="flex items-center gap-2">
                      <Badge variant={e.status === 'ENTWURF' ? 'warning' : 'success'} size="sm">
                        {e.status === 'ENTWURF' ? 'Entwurf' : 'Freigegeben'}
                      </Badge>
                      {onRechnungOeffnen ? (
                        <button type="button" className="text-left text-minga-700 dark:text-minga-300 hover:underline"
                                onClick={() => onRechnungOeffnen(e.invoice_id)}>
                          {e.customer_name}{e.art === 'LEERGUT' ? ' · Leergut' : ''}
                        </button>
                      ) : (
                        <span>{e.customer_name}{e.art === 'LEERGUT' ? ' · Leergut' : ''}</span>
                      )}
                      <span className="text-gray-500">· {Number(e.subtotal).toFixed(2)} € netto</span>
                    </li>
                  ))}
                </ul>
              )}
              {offeneEntwuerfe.length > 0 && (
                <p className="mt-1 text-xs text-gray-500">
                  Entwurf anklicken, prüfen und finalisieren — erst dann bekommt er seine Rechnungsnummer.
                </p>
              )}
            </section>

            <section>
              <h4 className="font-medium text-sm mb-1">Würde jetzt angelegt</h4>
              {stand.vorgeschlagen.length === 0 ? (
                <p className="text-sm text-gray-500 italic">Nichts.</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {stand.vorgeschlagen.map((k) => (
                    <li key={`${k.art}-${k.customer_id}`}>
                      {k.customer_name}
                      <span className="text-gray-500">
                        {k.art === 'LEERGUT' ? ' · Leergut' : ` · ${k.anzahl_lieferscheine} Lieferscheine`}
                        {' · '}{Number(k.summe_netto).toFixed(2)} € netto
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {stand.hinweise.length > 0 && (
              <section>
                <h4 className="font-medium text-sm mb-1">Hinweise</h4>
                <ul className="text-sm space-y-2 max-h-56 overflow-y-auto">
                  {stand.hinweise.map((h, i) => (
                    <li key={i} className={WICHTIGE_HINWEISE.includes(h.art) ? 'text-amber-700 dark:text-amber-300' : 'text-gray-600 dark:text-gray-300'}>
                      <span className="font-medium">{HINWEIS_TITEL[h.art]}</span>
                      {h.customer_name && ` — ${h.customer_name}`}: {h.text}
                      {h.belege.length > 0 && <span className="block text-xs text-gray-500">{h.belege.join(', ')}</span>}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}

        <div className="flex justify-end gap-2">
          <button className="btn btn-secondary" onClick={onClose}>Schließen</button>
          {istAdmin && (
            // Immer anklickbar: der Lauf ist idempotent und legt auch Leergutbelege
            // an, die „Würde jetzt angelegt“ nicht vorausberechnet.
            <Button onClick={() => laufMutation.mutate()}
                    loading={laufMutation.isPending}
                    disabled={!stand}>
              Entwürfe anlegen
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}


/** Stand des Vormonats — für Banner (Rechnungsseite) und Karte (Dashboard). */
export function useMonatsrechnungenVormonat(enabled = true) {
  return useQuery({
    queryKey: ['invoices', 'monatsrechnungen', 'vormonat'],
    queryFn: () => monatsrechnungApi.stand(),
    enabled,
    retry: 0,
  });
}

/** Was im Vormonat noch zu tun ist; null, wenn nichts. */
export function offeneMonatsarbeit(stand?: Monatsrechnungen) {
  if (!stand) return null;
  const entwuerfe = stand.entwuerfe.filter((e) => e.status === 'ENTWURF');
  const hinweise = stand.hinweise.filter((h) => WICHTIGE_HINWEISE.includes(h.art));
  if (!entwuerfe.length && !stand.vorgeschlagen.length && !hinweise.length) return null;
  return {
    monat: monatsName(stand.monat),
    entwuerfe: entwuerfe.length,
    netto: entwuerfe.reduce((summe, e) => summe + Number(e.subtotal), 0),
    ohneEntwurf: stand.vorgeschlagen.length,
    hinweise: hinweise.length,
  };
}

export function MonatsrechnungenBanner({ onOeffnen }: { onOeffnen: () => void }) {
  const { data } = useMonatsrechnungenVormonat();
  const offen = offeneMonatsarbeit(data);
  if (!offen) return null;
  return (
    <div className="mb-6 flex items-center justify-between gap-4 p-4 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 text-sm text-amber-900 dark:text-amber-200">
      <p>
        <span className="font-medium">Monatsrechnungen {offen.monat}:</span>{' '}
        {offen.entwuerfe > 0 && `${offen.entwuerfe} Entwurf/Entwürfe zur Prüfung (${offen.netto.toFixed(2)} € netto)`}
        {offen.entwuerfe > 0 && (offen.ohneEntwurf > 0 || offen.hinweise > 0) && ' · '}
        {offen.ohneEntwurf > 0 && `${offen.ohneEntwurf} Kunde(n) noch ohne Entwurf`}
        {offen.ohneEntwurf > 0 && offen.hinweise > 0 && ' · '}
        {offen.hinweise > 0 && `${offen.hinweise} Hinweis(e)`}
      </p>
      <Button variant="secondary" onClick={onOeffnen}>Prüfen</Button>
    </div>
  );
}
