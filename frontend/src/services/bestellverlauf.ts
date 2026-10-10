/**
 * Bestellverlauf (Paket 4.1, Abschnitt V): die Einträge von
 * GET /sales/orders/{id}/audit-log für den Belege-Dialog aufbereiten —
 * wann (Berliner Zeit), wer, was (Aktion auf Deutsch), Status alt → neu,
 * geänderte Werte als Kurztext, Grund. Geschrieben werden die Einträge im
 * Server (sales._create_audit_log, order_status_service.setze_status,
 * imports, Datenkorrekturen). Logins ohne Konditionssicht bekommen Preise und
 * Beträge nicht (werte_ausgeblendet, sales.VERLAUF_WERTE_FUER_ALLE).
 *
 * Einziger Import sind die Statuswörter der übrigen Oberfläche; beide Dateien
 * lädt tests/unit/bestellverlauf.check.ts direkt mit Node (Endung .ts nötig).
 */
import { orderStatusLabel } from '../components/ui/statusLabels.ts';

/** Ein Eintrag, wie der Server ihn liefert (schemas/order.py, OrderAuditLogResponse). */
export interface VerlaufEintrag {
  id: string;
  order_id: string;
  action: string;
  field_name: string | null;
  line_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  user_id: string | null;
  user_name: string | null;
  created_at: string;
  reason: string | null;
  werte_ausgeblendet?: boolean;
}

/** Eine Zeile der Anzeige. */
export interface VerlaufZeile {
  id: string;
  /** TT.MM.JJJJ HH:MM in Berlin */
  zeit: string;
  aktion: string;
  /** „Bestätigt → Gepackt“, bei einem Import nur der neue Status; sonst null */
  status: string | null;
  wer: string;
  details: string[];
  grund: string | null;
}

/** Alle Aktionen, die Code oder Korrektur-Runbooks schreiben (Stand 1e2238b). */
export const AKTION_TEXT: Record<string, string> = {
  CREATE: 'Angelegt',
  IMPORT: 'Importiert',
  CONFIRM: 'Bestätigt',
  STATUS_CHANGE: 'Status geändert',
  BULK_STATUS_CHANGE: 'Status geändert (Sammelaktion)',
  LIEFERSCHEIN_QUITTIERT: 'Lieferschein quittiert',
  LIEFERDATUM_NACHGETRAGEN: 'Lieferdatum nachgetragen',
  UPDATE: 'Bestellung geändert',
  ADD_LINE: 'Position hinzugefügt',
  UPDATE_LINE: 'Position geändert',
  DELETE_LINE: 'Position entfernt',
  STEUERSATZ_KORREKTUR: 'Steuersatz korrigiert',
  RECHNUNG_ZUGEORDNET: 'Rechnung zugeordnet',
};

export const FELD_TEXT: Record<string, string> = {
  actual_delivery_date: 'Geliefert am',
  requested_delivery_date: 'Liefertag',
  confirmed_delivery_date: 'Bestätigter Liefertag',
  packing_date: 'Packtag',
  customer_reference: 'Kundenbestellnummer',
  notes: 'Notizen',
  internal_notes: 'Interne Notizen',
  billing_address: 'Rechnungsadresse',
  delivery_address: 'Lieferadresse',
  quantity: 'Menge',
  unit_price: 'Preis',
  discount_percent: 'Rabatt',
  tax_rate: 'Steuersatz',
  line_vat: 'MwSt',
  line_gross: 'Brutto',
  positionen: 'Positionen',
  total_vat: 'MwSt gesamt',
  total_gross: 'Brutto gesamt',
  bestell_nr_extern: 'Bestellnr. extern',
  datei: 'Datei',
  // Runbook RECHNUNG_ZUGEORDNET (Prod: neu {"invoice": "RE-…"}); für die Halle ausgeblendet (Server)
  invoice: 'Rechnung',
};

/** Namen, unter denen Korrekturen der NovaERP-Betreuung laufen — klein geschrieben, verglichen
 * ohne Rücksicht auf Groß-/Kleinschreibung (Prod: „systemkorrektur“ und „Systemkorrektur“). */
const KORREKTUR_NAMEN = new Set(['systemkorrektur', 'datenkorrektur']);
export const AUSGEBLENDET_TEXT = 'Preise und Beträge nur für Verwaltung, Vertrieb, Buchhaltung und Planung';

const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;
const NUR_TAG = /^(\d{4})-(\d{2})-(\d{2})$/;
const STEUERSATZ: Record<string, string> = { STANDARD: '19 %', REDUZIERT: '7 %', STEUERFREI: '0 %' };
const BETRAG = new Set(['unit_price', 'line_vat', 'line_gross', 'total_vat', 'total_gross']);
const MAX_TEXT = 60;

/** Zeitstempel des Servers (UTC ohne Zone, bis zu 6 Nachkommastellen) als Millisekunden. */
function zeitwert(wert: string): number {
  const kurz = wert.replace(/(\.\d{3})\d+/, '$1');
  return new Date(MIT_ZONE.test(kurz) ? kurz : `${kurz}Z`).getTime();
}

/** TT.MM.JJJJ HH:MM in Berliner Zeit; leer bei unlesbarem Wert. */
export function zeitBerlin(wert: string): string {
  const ms = zeitwert(wert);
  if (Number.isNaN(ms)) return '';
  const teile = Object.fromEntries(new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(ms)).map((t) => [t.type, t.value]));
  return `${teile.day}.${teile.month}.${teile.year} ${teile.hour}:${teile.minute}`;
}

export function aktionText(action: string): string {
  return AKTION_TEXT[action] ?? `Sonstige Änderung (${action})`;
}

export function werText(e: Pick<VerlaufEintrag, 'user_name' | 'user_id'>): string {
  const name = e.user_name?.trim();
  if (name) return KORREKTUR_NAMEN.has(name.toLowerCase()) ? 'NovaERP (Datenkorrektur)' : name;
  return e.user_id ? 'Benutzer (Name nicht gespeichert)' : 'System (automatisch)';
}

/** Dezimalzahl ohne Tausenderpunkt, Komma, ohne Nullen am Ende („4.000“ → „4“). */
function zahlKurz(n: number, min = 0, max = 3): string {
  let text = n.toFixed(max);
  if (max > min) text = text.replace(new RegExp(`0{1,${max - min}}$`), '');
  return text.replace(/\.$/, '').replace('.', ',');
}

function kuerzen(text: string): string {
  return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT - 1)}…` : text;
}

/** Ein Wert als Kurztext, je nach Feld. */
export function wertText(feld: string, wert: unknown): string {
  if (wert === null || wert === undefined || wert === '') return 'leer';
  if (Array.isArray(wert)) return `${wert.length} ${wert.length === 1 ? 'Position' : 'Positionen'}`;
  if (typeof wert === 'object') return 'geändert';
  const text = String(wert);
  // Adressen speichert update_order als Python-Text eines dict
  if (text.startsWith('{')) return 'geändert';
  if (feld === 'status') return orderStatusLabel(text);
  if (feld === 'tax_rate') return STEUERSATZ[text] ?? text;
  const tag = NUR_TAG.exec(text);
  if (tag) return `${tag[3]}.${tag[2]}.${tag[1]}`;
  const zahl = typeof wert === 'number' ? wert : Number(text);
  if (text.trim() !== '' && Number.isFinite(zahl)) {
    if (BETRAG.has(feld)) return `${zahlKurz(zahl, 2, 4)} €`;
    if (feld === 'discount_percent') return `${zahlKurz(zahl, 0, 2)} %`;
    if (feld === 'quantity') return zahlKurz(zahl);
  }
  return kuerzen(text);
}

function feldText(feld: string): string {
  return FELD_TEXT[feld] ?? feld;
}

/** Feste Reihenfolge wie FELD_TEXT, unbekannte Felder zuletzt — unabhängig davon, in welcher
 * Reihenfolge ein Schreibpfad die Schlüssel ablegt. */
const FELD_REIHE = Object.keys(FELD_TEXT);
function rang(feld: string): number {
  const i = FELD_REIHE.indexOf(feld);
  return i < 0 ? FELD_REIHE.length : i;
}

/** Positionsangabe „Pos. 1 · Erbsen-Schale“ aus position/product. */
function positionText(werte: Record<string, unknown>): string | null {
  const teile: string[] = [];
  if (werte.position !== undefined && werte.position !== null) teile.push(`Pos. ${werte.position}`);
  if (werte.product) teile.push(String(werte.product));
  return teile.length ? teile.join(' · ') : null;
}

/** Unterschiede zweier Wertegruppen; gleich formatierte Werte zählen als unverändert. */
function unterschiede(alt: Record<string, unknown>, neu: Record<string, unknown>): string[] {
  const zeilen: string[] = [];
  const felder = [...new Set([...Object.keys(alt), ...Object.keys(neu)])]
    .filter((f) => f !== 'status' && f !== 'position' && f !== 'product')
    .sort((x, y) => rang(x) - rang(y));
  for (const feld of felder) {
    const a = alt[feld];
    const n = neu[feld];
    if (feld in alt && feld in neu) {
      if (Array.isArray(a) && Array.isArray(n)) {
        n.forEach((pos, i) => {
          const altPos = (a[i] ?? {}) as Record<string, unknown>;
          const neuPos = (pos ?? {}) as Record<string, unknown>;
          const was = unterschiede(altPos, neuPos);
          if (was.length) zeilen.push(`${positionText(neuPos) ?? `Pos. ${i + 1}`}: ${was.join(', ')}`);
        });
        continue;
      }
      const vorher = wertText(feld, a);
      const nachher = wertText(feld, n);
      if (vorher !== nachher) zeilen.push(`${feldText(feld)}: ${vorher} → ${nachher}`);
      else if (vorher === 'geändert' && String(a) !== String(n)) zeilen.push(`${feldText(feld)} geändert`);
    } else {
      const wert = feld in neu ? n : a;
      // Neue Position ohne Rabatt: „Rabatt: 0 %“ wäre nur Rauschen
      if (feld === 'discount_percent' && Number(wert) === 0) continue;
      zeilen.push(`${feldText(feld)}: ${wertText(feld, wert)}`);
    }
  }
  return zeilen;
}

/** Status alt → neu; bei einem Eintrag nur mit neuem Status (Import) nur dieser. */
export function statusText(e: Pick<VerlaufEintrag, 'old_values' | 'new_values'>): string | null {
  const alt = e.old_values?.status;
  const neu = e.new_values?.status;
  if (!neu) return null;
  return alt ? `${orderStatusLabel(String(alt))} → ${orderStatusLabel(String(neu))}` : orderStatusLabel(String(neu));
}

export function detailsText(e: VerlaufEintrag): string[] {
  const alt = e.old_values ?? {};
  const neu = e.new_values ?? {};
  const zeilen: string[] = [];
  const position = positionText({ ...alt, ...neu });
  if (position) zeilen.push(position);
  zeilen.push(...unterschiede(alt, neu));
  if (e.werte_ausgeblendet) zeilen.push(AUSGEBLENDET_TEXT);
  return zeilen;
}

/** Chronologisch, älteste zuerst. Der Server liefert die neuesten zuerst; bei
 * gleichem Zeitstempel bleibt dessen Reihenfolge umgekehrt erhalten. */
export function verlaufAufbereiten(eintraege: VerlaufEintrag[]): VerlaufZeile[] {
  return eintraege
    .map((e, i) => ({ e, i, t: zeitwert(e.created_at) }))
    .sort((x, y) => (x.t - y.t) || (y.i - x.i))
    .map(({ e }) => ({
      id: e.id,
      zeit: zeitBerlin(e.created_at),
      aktion: aktionText(e.action),
      status: statusText(e),
      wer: werText(e),
      details: detailsText(e),
      grund: e.reason?.trim() || null,
    }));
}
