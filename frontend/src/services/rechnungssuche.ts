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

/** Reiter der Rechnungsliste (Invoices.tsx). */
export type RechnungsReiter = 'all' | 'open' | 'overdue' | 'paid'

export interface ReiterRechnung extends Suchbar {
  status: string
}

/**
 * Was jeder Reiter bei der aktuellen Suche zeigt (Paket 4.1, Z).
 *
 * Eine Regel für Tabelle und Zähler: die Tabelle zeigt `reiter[aktiv]`,
 * der Zähler eines Reiters ist `reiter[id].length` — eine zweite
 * Zähllogik gibt es nicht. „Offen“ und „Bezahlt“ filtern die geladene
 * Liste nach Status, „Überfällig“ ist die Liste von GET /invoices/overdue
 * (UEBERFAELLIG und überfällige TEILBEZAHLT); in jedem Reiter wirkt die
 * Suche (Paket 4, B; G05).
 */
export function rechnungenJeReiter<T extends ReiterRechnung>(
  rechnungen: T[],
  ueberfaellige: T[],
  suche: string,
): Record<RechnungsReiter, T[]> {
  const passt = (rechnung: T) => rechnungPasstZurSuche(rechnung, suche);
  return {
    all: rechnungen.filter(passt),
    open: rechnungen.filter((r) => r.status === 'OFFEN' && passt(r)),
    overdue: ueberfaellige.filter(passt),
    paid: rechnungen.filter((r) => r.status === 'BEZAHLT' && passt(r)),
  };
}

/**
 * Zähler eines Reiters für die Reiterleiste (`badge` in Tabs.tsx).
 *
 * `gekuerzt`: Die geladene Liste hat die Listengrenze erreicht — ältere
 * Rechnungen fehlen womöglich, die Zahl ist eine Untergrenze („12+“), wie
 * „100+ Rechnungen“ im Seitenkopf. 0 bleibt 0; die Reiterleiste blendet
 * sie aus (wie bei den Bestellungen).
 */
export function reiterZaehler(anzahl: number, gekuerzt: boolean): number | string {
  return gekuerzt && anzahl > 0 ? `${anzahl}+` : anzahl;
}
