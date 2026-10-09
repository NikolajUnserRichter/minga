import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Mail, Send } from 'lucide-react';
import { Button, Textarea, useToast } from '../ui';
import { salesApi, BelegVersandAuftrag } from '../../services/api';
import { DocumentDispatch } from '../../types';

/**
 * Belegversand per E-Mail (Paket 3, Q2) — ersetzt die frühere Eingabe der
 * Adresse im Browser-Dialog. Gernot (08.10.2026): EINE Mail, alle Adressen im An-Feld.
 */
export type Belegart = 'AB' | 'LS' | 'RE';

type ListenFeld = 'confirmation_emails' | 'delivery_note_emails' | 'invoice_emails';

const LISTE: Record<Belegart, ListenFeld> = {
  AB: 'confirmation_emails',
  LS: 'delivery_note_emails',
  RE: 'invoice_emails',
};

const TITEL: Record<Belegart, string> = {
  AB: 'Auftragsbestätigung',
  LS: 'Lieferschein',
  RE: 'Rechnung',
};

// Grobe Formatprüfung beim Tippen; verbindlich prüft der Server.
const FORMAT = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const HOECHSTENS = 10;

/** Trennt an Zeilenumbruch, Komma, Semikolon und Leerzeichen; klein, ohne Dubletten. */
export function adressListe(text: string): string[] {
  const ergebnis: string[] = [];
  for (const roh of text.split(/[\s,;]+/)) {
    const adresse = roh.trim().toLowerCase();
    if (adresse && !ergebnis.includes(adresse)) ergebnis.push(adresse);
  }
  return ergebnis;
}

/** „(1) a@kunde.de, (2) b@kunde.de" — so, wie Gernot es lesen möchte. */
export function nummeriert(adressen: string[]): string {
  return adressen.map((a, i) => `(${i + 1}) ${a}`).join(', ');
}

/** Eine Zeile des Versandprotokolls als Text. */
export function versandZeile(d: DocumentDispatch): string {
  const wann = new Date(d.sent_at).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
  const wer = d.sent_by_name ? ` · ${d.sent_by_name}` : '';
  if (d.status === 'NUR_MARKIERT') return `${wann}${wer} · ohne Mail als versendet markiert`;
  const cc = d.cc_addrs.length ? ` · Cc ${d.cc_addrs.join(', ')}` : '';
  return `${wann}${wer} · versendet an ${nummeriert(d.to_addrs)}${cc}`;
}

/** Erfolgsmeldung nach einem Versand; bei Teilablehnung als Warnung. */
export function versandMeldung(
  toast: ReturnType<typeof useToast>,
  beleg: string,
  eintraege: DocumentDispatch[] | undefined,
) {
  const d = eintraege && eintraege.length ? eintraege[eintraege.length - 1] : undefined;
  if (!d) {
    toast.success(`${beleg} gespeichert`);
  } else if (d.status === 'NUR_MARKIERT') {
    toast.success(`${beleg} ohne Mail als versendet markiert`);
  } else if (d.status === 'TEILWEISE') {
    toast.warning(
      `${beleg} versendet an ${nummeriert(d.to_addrs)} — abgelehnt: ${Object.keys(d.refused ?? {}).join(', ')}`,
      10000,
    );
  } else {
    toast.success(`${beleg} versendet an ${nummeriert(d.to_addrs)}`);
  }
}

/** Versandprotokoll unter einem Beleg: wann, wer, an wen. */
export function VersandProtokoll({ eintraege }: { eintraege?: DocumentDispatch[] }) {
  if (!eintraege || eintraege.length === 0) return null;
  return (
    <ul className="mt-1 space-y-0.5 text-xs text-gray-500 dark:text-gray-400">
      {eintraege.map((d) => (
        <li key={d.id} className="flex items-start gap-1">
          <Mail className="w-3 h-3 mt-0.5 shrink-0" />
          <span>
            {versandZeile(d)}
            {d.status === 'TEILWEISE' && d.refused && (
              <span className="text-amber-700 dark:text-amber-300">
                {' '}· abgelehnt: {Object.keys(d.refused).join(', ')}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

interface VersandFormularProps {
  belegart: Belegart;
  belegNummer: string;
  customerId?: string | null;
  /** AB und Lieferschein im Entwurf: „ohne Mail markieren" anbieten */
  nurMarkierenMoeglich?: boolean;
  pending?: boolean;
  onSenden: (auftrag: BelegVersandAuftrag) => void;
  onAbbrechen: () => void;
}

/**
 * Empfänger wählen und senden. Inline (kein zweites Modal): Zwei gestapelte
 * Modals schließen beide auf Escape (siehe Paket 1, Task 29).
 * Vorbelegt mit der Liste der Belegart aus dem Kundenstamm, sonst mit der
 * Haupt-E-Mail; Vorschläge aus den Ansprechpartnern. Vorbelegt wird erst mit
 * dem beim Öffnen frisch geladenen Kundenstamm (isFetchedAfterMount): Eine
 * zwischengespeicherte ältere Liste käme sonst ins Formular, und das Formular
 * schickt die angezeigten Adressen immer ausdrücklich als `to`.
 */
export function VersandFormular({
  belegart,
  belegNummer,
  customerId,
  nurMarkierenMoeglich = false,
  pending = false,
  onSenden,
  onAbbrechen,
}: VersandFormularProps) {
  const kundeQuery = useQuery({
    queryKey: ['customer', customerId],
    queryFn: () => salesApi.getCustomer(customerId!),
    enabled: !!customerId,
    staleTime: 0,
  });
  const kontakteQuery = useQuery({
    queryKey: ['customer-contacts', customerId],
    queryFn: () => salesApi.listContacts(customerId!),
    enabled: !!customerId,
  });

  const [an, setAn] = useState('');
  const [cc, setCc] = useState('');
  const [ccOffen, setCcOffen] = useState(false);
  const [vorbelegt, setVorbelegt] = useState(false);

  useEffect(() => {
    if (vorbelegt) return;
    // Erst nach dem Laden beim Öffnen (auch nach einem Ladefehler: dann leer)
    if (customerId && !kundeQuery.isFetchedAfterMount) return;
    const kunde = kundeQuery.data;
    if (kunde) {
      const liste = kunde[LISTE[belegart]] ?? [];
      setAn((liste.length ? liste : kunde.email ? [kunde.email] : []).join('\n'));
    }
    setVorbelegt(true);
  }, [customerId, kundeQuery.data, kundeQuery.isFetchedAfterMount, vorbelegt, belegart]);

  const anListe = adressListe(an);
  const ccListe = adressListe(cc).filter((a) => !anListe.includes(a));
  const ungueltig = [...anListe, ...ccListe].filter((a) => !FORMAT.test(a));
  const zuViele = anListe.length + ccListe.length > HOECHSTENS;
  const vorschlaege = [kundeQuery.data?.email, ...(kontakteQuery.data ?? []).map((k) => k.email)]
    .filter((a): a is string => !!a)
    .map((a) => a.toLowerCase())
    .filter((a, i, alle) => alle.indexOf(a) === i && !anListe.includes(a));

  return (
    <div className="space-y-2 rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 p-3">
      <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
        {TITEL[belegart]} {belegNummer} per E-Mail
      </p>
      <Textarea
        label="An (eine Adresse je Zeile)"
        rows={3}
        value={an}
        disabled={!vorbelegt}
        onChange={(e) => setAn(e.target.value)}
        hint={!vorbelegt
          ? 'Empfänger werden geladen …'
          : anListe.length ? `Eine Mail an ${nummeriert(anListe)}` : 'Keine Adresse: keine Mail'}
      />
      {vorschlaege.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-xs">
          <span className="text-gray-500 dark:text-gray-400">Vorschläge:</span>
          {vorschlaege.map((a) => (
            <button
              key={a}
              type="button"
              disabled={!vorbelegt}
              className="rounded bg-gray-200 dark:bg-gray-700 px-2 py-0.5"
              onClick={() => setAn((t) => (t.trim() ? `${t.trim()}\n${a}` : a))}
            >
              + {a}
            </button>
          ))}
        </div>
      )}
      {ccOffen ? (
        <Textarea label="Cc (optional)" rows={2} value={cc} onChange={(e) => setCc(e.target.value)} />
      ) : (
        <button type="button" className="text-xs underline text-gray-600 dark:text-gray-300" onClick={() => setCcOffen(true)}>
          Cc hinzufügen
        </button>
      )}
      {ungueltig.length > 0 && (
        <p className="text-xs text-red-700 dark:text-red-300">Keine gültige Adresse: {ungueltig.join(', ')}</p>
      )}
      {zuViele && (
        <p className="text-xs text-red-700 dark:text-red-300">Höchstens {HOECHSTENS} Adressen je Mail.</p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button size="sm" variant="secondary" onClick={onAbbrechen}>
          Abbrechen
        </Button>
        {nurMarkierenMoeglich && (
          <Button size="sm" variant="secondary" disabled={pending} onClick={() => onSenden({})}>
            Ohne Mail als {belegart === 'LS' ? 'ausgestellt' : 'versendet'} markieren
          </Button>
        )}
        <Button
          size="sm"
          icon={<Send className="w-3 h-3" />}
          loading={pending}
          disabled={!vorbelegt || anListe.length === 0 || ungueltig.length > 0 || zuViele}
          onClick={() => onSenden({ to: anListe, cc: ccListe })}
        >
          Senden
        </Button>
      </div>
    </div>
  );
}
