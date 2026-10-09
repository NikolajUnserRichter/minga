import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { sepaApi } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Button, Input, useToast } from '../ui';
import { belegHerunterladen } from '../../services/belegordner';

/**
 * Arbeitsliste „Lastschrift-Einzüge" (B10): festgeschriebene
 * Lastschriftrechnungen mit ausstehendem Einzug. „Bei der Bank einreichen"
 * erzeugt die CSV fürs Online-Banking mit genau den angehakten Rechnungen und
 * vermerkt sie als eingereicht — keine Rechnung landet zweimal in einer Datei.
 * Nach dem Kontoauszug „Als eingezogen buchen". Kein SEPA-XML.
 */
const ANKUENDIGUNG: Record<string, string> = {
  RECHTZEITIG: 'per Mail',
  ZU_SPAET: 'zu spät gemailt',
  NICHT_PER_MAIL: 'nicht per Mail versendet',
};

// Bei responseType 'blob' kommt auch die Fehlerantwort als Blob.
async function fehlertext(e: unknown, standard: string): Promise<string> {
  const daten = (e as { response?: { data?: unknown } })?.response?.data;
  if (daten instanceof Blob) {
    try {
      return JSON.parse(await daten.text()).detail || standard;
    } catch {
      return standard;
    }
  }
  return getErrorMessage(e, standard);
}

export function SepaEinzugsliste() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const heute = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Berlin' });
  const [bis, setBis] = useState('');
  const [auswahl, setAuswahl] = useState<string[]>([]);
  const [datum, setDatum] = useState(heute);
  const [reicheEin, setReicheEin] = useState(false);

  const { data: zeilen = [], isLoading } = useQuery({
    queryKey: ['sepa-einzugsliste', bis],
    queryFn: () => sepaApi.einzugsliste(bis || undefined),
  });
  const neuLaden = () => {
    setAuswahl([]);
    queryClient.invalidateQueries({ queryKey: ['sepa-einzugsliste'] });
    queryClient.invalidateQueries({ queryKey: ['invoices'] });
  };

  const buchen = useMutation({
    mutationFn: () => sepaApi.einzugBuchen(auswahl, datum),
    onSuccess: (r) => {
      toast.success(`${r.gebucht.length} Einzug/Einzüge gebucht`);
      r.hinweise.forEach((h) => toast.warning(h));
      neuLaden();
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Buchen fehlgeschlagen')),
  });

  const einreichbar = zeilen.filter((z) => auswahl.includes(z.invoice_id) && !z.eingereicht_am);

  const einreichen = async () => {
    const ohneMail = einreichbar.filter((z) => z.ankuendigung !== 'RECHTZEITIG');
    try {
      // Abschnitt O: erst die Ordner-Freigabe (braucht den frischen Klick), dann
      // die Rückfrage, dann einreichen. Die CSV gibt es nur einmal (zweites
      // Mal 409): Kann der Ordner nicht schreiben, kommt sie als Download.
      const ergebnis = await belegHerunterladen(
        { art: 'Lastschriften', ersatzname: `Lastschrift-Einreichung_${heute}.csv`, mime: 'text/csv' },
        async () => {
          let bestaetigt = false;
          if (ohneMail.length > 0) {
            bestaetigt = confirm(
              `Für ${ohneMail.map((z) => z.invoice_number).join(', ')} ist keine rechtzeitige Vorabankündigung per Mail belegt. `
              + 'Wurde sie auf anderem Weg rechtzeitig zugestellt? (Wird an der Rechnung vermerkt.)',
            );
            if (!bestaetigt) return null;
          }
          setReicheEin(true);
          return sepaApi.einreichen(einreichbar.map((z) => z.invoice_id), bestaetigt);
        },
        toast,
      );
      if (!ergebnis) return;
      toast.success(`${einreichbar.length} Lastschrift(en) als eingereicht vermerkt`);
      neuLaden();
    } catch (e) {
      toast.error(await fehlertext(e, 'Einreichung fehlgeschlagen'));
    } finally {
      setReicheEin(false);
    }
  };

  const umschalten = (id: string) =>
    setAuswahl((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2">
        <Input label="Einzugsdatum bis" type="date" value={bis} onChange={(e) => setBis(e.target.value)} />
        <Button variant="secondary" onClick={einreichen} loading={reicheEin} disabled={einreichbar.length === 0}>
          Bei der Bank einreichen (CSV) ({einreichbar.length})
        </Button>
      </div>
      {isLoading ? (
        <div className="text-sm text-gray-500">Lädt …</div>
      ) : zeilen.length === 0 ? (
        <div className="text-sm text-gray-500">Keine ausstehenden Lastschrift-Einzüge.</div>
      ) : (
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase">
              <th></th><th>Rechnung</th><th>Kunde</th><th>Einzug am</th><th>Betrag</th><th>Mandat</th><th>IBAN</th><th>Vorabankündigung</th><th>Eingereicht</th>
            </tr>
          </thead>
          <tbody>
            {zeilen.map((z) => (
              <tr key={z.invoice_id} className={z.mandat_aktiv ? '' : 'text-red-600'}>
                <td>
                  <input type="checkbox" disabled={!z.mandat_aktiv}
                    checked={auswahl.includes(z.invoice_id)} onChange={() => umschalten(z.invoice_id)} />
                </td>
                <td>{z.invoice_number}</td>
                <td>{z.customer_name}</td>
                <td>
                  {new Date(z.einzugsdatum).toLocaleDateString('de-DE')}
                  {z.ueberfaellig_seit_tagen > 0 && <span className="text-xs text-amber-600"> (seit {z.ueberfaellig_seit_tagen} T.)</span>}
                </td>
                <td>{Number(z.betrag).toFixed(2)} {z.waehrung}</td>
                <td>{z.mandatsreferenz}{z.mandat_aktiv ? '' : ' — widerrufen, nicht einziehen'}</td>
                <td className="font-mono">{z.iban}</td>
                <td className={z.ankuendigung === 'RECHTZEITIG' ? '' : 'text-amber-600'}>
                  {ANKUENDIGUNG[z.ankuendigung] || z.ankuendigung}
                  {z.versendet_am ? ` (${new Date(z.versendet_am).toLocaleDateString('de-DE')})` : ''}
                </td>
                <td>{z.eingereicht_am ? new Date(z.eingereicht_am).toLocaleDateString('de-DE') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-end gap-2 border-t pt-3">
        <Input label="Eingezogen am (laut Kontoauszug)" type="date" max={heute} value={datum}
          onChange={(e) => setDatum(e.target.value)} />
        <Button disabled={auswahl.length === 0} loading={buchen.isPending} onClick={() => buchen.mutate()}>
          Als eingezogen buchen ({auswahl.length})
        </Button>
      </div>
    </div>
  );
}
