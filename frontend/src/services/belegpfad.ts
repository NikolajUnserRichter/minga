/**
 * Ablage im Belegordner (Abschnitt O, Gernot 09.10.2026):
 * <Belegordner>/<Belegart>/<JJJJ-MM>/<Dateiname>, z. B.
 * Belege/Rechnungen/2026-10/RE-2026-00006.pdf.
 *
 * Die Belegart kommt vom Aufrufer, nicht aus dem Dateinamen: Rechnung,
 * Stornorechnung, Leergutbeleg und Monatsrechnung heißen alle RE-….pdf
 * (ein Nummernkreis). Der Monat kommt aus dem Belegdatum in Berliner Zeit,
 * ohne Datum aus dem heutigen Tag in Berlin.
 *
 * Bewusst ohne Importe: tests/unit/belegpfad.check.ts lädt die Datei direkt
 * mit Node (wie dateiname.ts).
 */

export type Belegart =
  | 'Rechnungen'
  | 'Stornorechnungen'
  | 'Gutschriften'
  | 'Leergut'
  | 'Proformarechnungen'
  | 'Entwürfe'
  | 'Auftragsbestätigungen'
  | 'Lieferscheine'
  | 'Packlisten'
  | 'Mahnungen'
  | 'DATEV-Exporte'
  | 'Lastschriften';

/**
 * Exporte heißen nach einem Datum, nicht nach einer Belegnummer: derselbe Name
 * hat einen anderen Inhalt (zweite SEPA-Einreichung am selben Tag, DATEV nur
 * mit den neuen Buchungen). Sie werden nie ersetzt, sondern bekommen (1), (2) ….
 */
export function istExport(art: Belegart): boolean {
  return art === 'DATEV-Exporte' || art === 'Lastschriften';
}

export interface RechnungFuerAblage {
  invoice_type: string;
  status: string;
  original_invoice_id?: string | null;
  beleg_art?: string | null;
}

/**
 * Belegart einer Rechnung. Entwürfe getrennt, sonst genau die Typ-Spalte der
 * Rechnungsliste (Invoices.tsx): Stornorechnung, Leergutabrechnung, dann der
 * Typ — Gutschrift, Proforma, Rechnung (auch Monatsrechnung). Proforma ist
 * keine Steuerrechnung und bekommt deshalb einen eigenen Ordner.
 */
export function belegartDerRechnung(r: RechnungFuerAblage): Belegart {
  if (r.status === 'ENTWURF') return 'Entwürfe';
  if (r.invoice_type === 'GUTSCHRIFT' && r.original_invoice_id) return 'Stornorechnungen';
  if (r.beleg_art === 'LEERGUT') return 'Leergut';
  if (r.invoice_type === 'GUTSCHRIFT') return 'Gutschriften';
  if (r.invoice_type === 'PROFORMA') return 'Proformarechnungen';
  return 'Rechnungen';
}

const NUR_DATUM = /^(\d{4})-(\d{2})-\d{2}$/;
const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * JJJJ-MM des Belegdatums in Berliner Zeit. "2026-10-31" gilt wie geschrieben;
 * ein Zeitstempel ohne Zone ist UTC (der Server speichert
 * datetime.now(timezone.utc), SQLite gibt ihn ohne Zone zurück). Ohne oder mit
 * unlesbarem Datum: der heutige Monat in Berlin.
 */
export function belegmonat(datum: string | null | undefined, jetzt: Date = new Date()): string {
  if (datum) {
    const tag = NUR_DATUM.exec(datum);
    if (tag) return `${tag[1]}-${tag[2]}`;
    const zeit = new Date(MIT_ZONE.test(datum) ? datum : `${datum}Z`);
    if (!Number.isNaN(zeit.getTime())) return monatInBerlin(zeit);
  }
  return monatInBerlin(jetzt);
}

function monatInBerlin(zeit: Date): string {
  const teile = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit',
  }).formatToParts(zeit);
  const jahr = teile.find((t) => t.type === 'year')?.value;
  const monat = teile.find((t) => t.type === 'month')?.value;
  return `${jahr}-${monat}`;
}

/** Datei- bzw. Ordnername ohne Zeichen, die Windows oder der Browser ablehnen. */
export function sichererName(name: string): string {
  // eslint-disable-next-line no-control-regex
  const sauber = name.replace(/[\x00-\x1f<>:"/\\|?*]/g, '_').replace(/[. ]+$/, '').trim();
  return sauber || 'Beleg';
}

/** Name für eine schon vorhandene Datei: ("RE-1.pdf", 1) → "RE-1 (1).pdf". */
export function nameMitZaehler(dateiname: string, n: number): string {
  const punkt = dateiname.lastIndexOf('.');
  if (punkt <= 0) return `${dateiname} (${n})`;
  return `${dateiname.slice(0, punkt)} (${n})${dateiname.slice(punkt)}`;
}

export interface Ablage {
  /** Unterordner unter dem Belegordner: [Belegart, JJJJ-MM] */
  ordner: [Belegart, string];
  datei: string;
}

export function belegablage(
  art: Belegart, datum: string | null | undefined, dateiname: string, jetzt: Date = new Date(),
): Ablage {
  return { ordner: [art, belegmonat(datum, jetzt)], datei: sichererName(dateiname) };
}

/** Anzeige im Toast: "Belege/Rechnungen/2026-10/RE-2026-00006.pdf". */
export function ablageAnzeige(wurzel: string, ablage: Ablage, datei: string = ablage.datei): string {
  return [wurzel, ...ablage.ordner, datei].join('/');
}
