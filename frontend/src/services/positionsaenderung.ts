/**
 * Menge und Einzelpreis einer Position im Rechnungsentwurf ändern (Paket 4, B;
 * G21: „Entwurf prüfen – Positionen editierbar (Menge, Preis, Position
 * löschen)“). Aus den Eingabefeldern wird die Änderung für
 * PATCH /invoices/{id}/lines/{line_id}: nur geänderte Felder. Der Server
 * rechnet Zeile und Summen neu und lehnt festgeschriebene Rechnungen ab.
 *
 * Bewusst ohne Importe: tests/unit/positionsaenderung.check.ts lädt die Datei
 * direkt mit Node.
 */

export interface PositionsWerte {
  quantity: number | string
  unit_price: number | string
}

export type Positionsaenderung =
  | { fehler: string }
  | { daten: { quantity?: number; unit_price?: number } }

/** Eingabe "2,5" oder "2.5" → 2.5. Keine Zahl, negativ, Tausenderpunkte oder
 *  mehr Nachkommastellen als die Spalte speichert → NaN. "1.000" ist
 *  mehrdeutig (deutscher Tausenderpunkt: 1000; Dezimalpunkt: 1) und wird
 *  abgelehnt statt geraten; "0.125", "3.10" und "1,000" bleiben eindeutig. */
export function zahlAusEingabe(eingabe: string, nachkommastellen: number): number {
  const roh = eingabe.trim();
  if (/^[1-9]\d{0,2}\.\d{3}$/.test(roh)) return NaN;
  const text = roh.replace(',', '.');
  const muster = new RegExp(`^\\d+(\\.\\d{1,${nachkommastellen}})?$`);
  return muster.test(text) ? Number(text) : NaN;
}

/** Wert für das Eingabefeld: 2.5 → "2,5", "10.000" → "10". */
export function eingabeAusZahl(wert: number | string): string {
  const zahl = Number(wert);
  return Number.isFinite(zahl) ? String(zahl).replace('.', ',') : '';
}

/** Menge: Spalte Numeric(10, 3); Einzelpreis: Numeric(10, 4). */
export function positionsaenderung(alt: PositionsWerte, menge: string, preis: string): Positionsaenderung {
  const neueMenge = zahlAusEingabe(menge, 3);
  if (!(neueMenge > 0)) return { fehler: 'Menge: eine Zahl größer als 0 mit höchstens 3 Nachkommastellen' };
  const neuerPreis = zahlAusEingabe(preis, 4);
  if (!(neuerPreis >= 0)) return { fehler: 'Einzelpreis: eine Zahl ab 0 mit höchstens 4 Nachkommastellen' };
  const daten: { quantity?: number; unit_price?: number } = {};
  if (neueMenge !== Number(alt.quantity)) daten.quantity = neueMenge;
  if (neuerPreis !== Number(alt.unit_price)) daten.unit_price = neuerPreis;
  return { daten };
}
