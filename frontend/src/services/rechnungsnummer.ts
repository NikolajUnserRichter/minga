// Rechnungsnummer erst beim Finalisieren (Spec 08.10.2026, Entscheidung 2).
// Ein Entwurf trägt bis dahin einen Platzhalter ENTWURF-… (Backend:
// app.models.invoice.ENTWURF_PRAEFIX), den die Oberfläche nicht als Nummer zeigt.

export const ENTWURF_PRAEFIX = 'ENTWURF-';

export function istEntwurfsnummer(nummer?: string | null): boolean {
  return !!nummer && nummer.startsWith(ENTWURF_PRAEFIX);
}

/** Rechnungsnummer für die Anzeige — ein Entwurf hat noch keine. */
export function rechnungsnummerAnzeige(nummer?: string | null): string {
  return istEntwurfsnummer(nummer) ? 'Entwurf (ohne Nummer)' : (nummer ?? '');
}

/** Rückfrage vor jedem Finalisieren: danach ist die Rechnung unveränderlich. */
export const FINALISIEREN_RUECKFRAGE =
  'Rechnung finalisieren? Sie erhält die nächste freie Rechnungsnummer und das heutige ' +
  'Rechnungsdatum und lässt sich danach nur noch stornieren.';
