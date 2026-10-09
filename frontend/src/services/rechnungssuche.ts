/**
 * Suche der Rechnungsliste „nach Nummer oder Kunde“ (Paket 4, B; G05).
 *
 * Gilt in jedem Reiter (Alle, Offen, Überfällig, Bezahlt) — bis Paket 4
 * wirkte sie nur unter „Alle“. Jedes Wort der Eingabe muss in der
 * Rechnungsnummer, im Kundennamen oder in der Kundennummer vorkommen;
 * Groß- und Kleinschreibung zählen nicht. Gesucht wird in der geladenen
 * Liste (die neuesten 100 Rechnungen, LISTENGRENZE in Invoices.tsx).
 *
 * Bewusst ohne Importe: tests/unit/rechnungssuche.check.ts lädt die Datei
 * direkt mit Node.
 */

export interface Suchbar {
  invoice_number: string
  customer_name?: string | null
  customer_number?: string | null
}

export function rechnungPasstZurSuche(rechnung: Suchbar, suche: string): boolean {
  const woerter = suche.toLocaleLowerCase('de-DE').split(/\s+/).filter(Boolean);
  if (woerter.length === 0) return true;
  const text = [rechnung.invoice_number, rechnung.customer_name, rechnung.customer_number]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('de-DE');
  return woerter.every((wort) => text.includes(wort));
}
