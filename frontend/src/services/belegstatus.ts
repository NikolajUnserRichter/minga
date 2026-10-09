/**
 * Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2):
 * Typen der Antwort von GET /belegstatus und die Anzeige der Spalten
 * Lieferschein, Rechnung, Versand und Zahlung. Die Regeln (geliefert, fällig,
 * unvollständig) stehen im Server: backend/app/services/belegstatus.py.
 *
 * Bewusst ohne Importe: tests/unit/belegstatus.check.ts lädt die Datei direkt
 * mit Node (wie dateiname.ts).
 */

export type Luecke = 'OHNE_RECHNUNG' | 'RECHNUNG_ENTWURF' | 'NICHT_VERSENDET';

export interface BelegstatusLieferschein {
  id: string;
  nummer: string;
  status: string;
}

export interface BelegstatusRechnung {
  id: string;
  /** Entwurf: Platzhalter ENTWURF-… (keine Nummer) */
  nummer: string;
  status: string;
  sammelrechnung: boolean;
  versendet_am: string | null;
  bezahlt: boolean;
}

export interface BelegstatusZeile {
  order_id: string;
  order_number: string;
  order_status: string;
  customer_id: string;
  customer_name: string;
  abrechnung: 'EINZELN' | 'MONATLICH';
  liefertag: string;
  geliefert: boolean;
  lieferscheine: BelegstatusLieferschein[];
  rechnung: BelegstatusRechnung | null;
  extern_abgerechnet: boolean;
  rechnung_faellig_ab: string;
  luecken: Luecke[];
  unvollstaendig: boolean;
}

export interface BelegstatusListe {
  items: BelegstatusZeile[];
  total: number;
  /** unvollständige Zeilen in Zeitraum und Kunde (Zahl am Filter) */
  unvollstaendig: number;
  heute: string;
}

export interface BelegstatusFilter {
  von?: string;
  bis?: string;
  kunde_id?: string;
  nur_unvollstaendig?: boolean;
  page?: number;
  page_size?: number;
}

export const LUECKEN_TEXT: Record<Luecke, string> = {
  OHNE_RECHNUNG: 'Rechnung fehlt',
  RECHNUNG_ENTWURF: 'Rechnung nur als Entwurf',
  NICHT_VERSENDET: 'Rechnung nicht versendet',
};

/** Eine Zelle der Übersicht. ton 'luecke' nur, wenn die Zelle eine Lücke der Zeile erklärt. */
export interface Zelle {
  zeichen: '✔' | '✘' | '◐' | '—';
  text: string;
  ton: 'ok' | 'luecke' | 'neutral';
}

const NUR_TAG = /^(\d{4})-(\d{2})-(\d{2})$/;
const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * TT.MM.JJJJ. Ein Tag „2026-10-08“ gilt wie geschrieben; ein Zeitstempel ohne
 * Zone ist UTC (der Server speichert sent_at in UTC) und wird in Berliner
 * Zeit angezeigt. Leer ohne oder bei unlesbarem Wert.
 */
export function datumKurz(wert: string | null | undefined): string {
  if (!wert) return '';
  const tag = NUR_TAG.exec(wert);
  if (tag) return `${tag[3]}.${tag[2]}.${tag[1]}`;
  const zeit = new Date(MIT_ZONE.test(wert) ? wert : `${wert}Z`);
  if (Number.isNaN(zeit.getTime())) return '';
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(zeit);
}

/** Heute in Berlin als JJJJ-MM-TT. */
export function heuteBerlin(jetzt: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(jetzt);
}

/** Vorgabe für „von“: der 1. des Vormonats. */
export function vorgabeVon(heute: string): string {
  const [jahr, monat] = heute.split('-').map(Number);
  return monat === 1 ? `${jahr - 1}-12-01` : `${jahr}-${String(monat - 1).padStart(2, '0')}-01`;
}

export function lieferscheinZelle(z: BelegstatusZeile): Zelle {
  if (z.lieferscheine.length) {
    return { zeichen: '✔', text: z.lieferscheine.map((l) => l.nummer).join(', '), ton: 'ok' };
  }
  if (z.extern_abgerechnet) return { zeichen: '—', text: 'extern', ton: 'neutral' };
  return { zeichen: '✘', text: 'fehlt', ton: 'neutral' };
}

export function rechnungZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (r && r.status === 'ENTWURF') {
    return { zeichen: '◐', text: 'Entwurf', ton: z.luecken.includes('RECHNUNG_ENTWURF') ? 'luecke' : 'neutral' };
  }
  if (r) return { zeichen: '✔', text: r.sammelrechnung ? `${r.nummer} (Sammelrechnung)` : r.nummer, ton: 'ok' };
  if (z.extern_abgerechnet) return { zeichen: '✔', text: 'extern (DATEV)', ton: 'neutral' };
  if (z.luecken.includes('OHNE_RECHNUNG')) return { zeichen: '✘', text: 'fehlt', ton: 'luecke' };
  if (!z.geliefert) return { zeichen: '—', text: 'nicht geliefert', ton: 'neutral' };
  if (z.abrechnung === 'MONATLICH') {
    return { zeichen: '—', text: `Monatsrechnung ab ${datumKurz(z.rechnung_faellig_ab)}`, ton: 'neutral' };
  }
  return { zeichen: '—', text: `fällig ab ${datumKurz(z.rechnung_faellig_ab)}`, ton: 'neutral' };
}

export function versandZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (!r || r.status === 'ENTWURF') return { zeichen: '—', text: '', ton: 'neutral' };
  if (r.versendet_am) return { zeichen: '✔', text: datumKurz(r.versendet_am), ton: 'ok' };
  return { zeichen: '✘', text: 'nicht versendet', ton: z.luecken.includes('NICHT_VERSENDET') ? 'luecke' : 'neutral' };
}

const ZAHLSTATUS: Record<string, string> = {
  OFFEN: 'offen',
  TEILBEZAHLT: 'teilbezahlt',
  UEBERFAELLIG: 'überfällig',
  MAHNVERFAHREN: 'Mahnverfahren',
};

/** Zahlung: nur Anzeige (Gernot: „optional: bezahlt“), nie eine Lücke. */
export function zahlungZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (!r || r.status === 'ENTWURF') return { zeichen: '—', text: '', ton: 'neutral' };
  if (r.bezahlt) return { zeichen: '✔', text: 'bezahlt', ton: 'ok' };
  return { zeichen: '✘', text: ZAHLSTATUS[r.status] ?? r.status, ton: 'neutral' };
}
