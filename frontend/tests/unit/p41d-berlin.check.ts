// Paket 4.1, Abschnitt D: Anzeige- und Vorgabetag im Browser = Berliner Tag,
// zu denselben Zeitpunkten wie backend/tests/test_paket4_1.py (TestP41D…).
// Lauf: node tests/unit/p41d-berlin.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { datumKurz, heuteBerlin } from '../../src/services/belegstatus.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

// „Erstellt am“ (Sales.tsx): bestell_datum kommt naiv in UTC vom Server
gleich(datumKurz('2026-10-09T22:30:00'), '10.10.2026', '00:30 Sommerzeit');
gleich(datumKurz('2026-10-09T21:30:00'), '09.10.2026', '23:30 Sommerzeit');
gleich(datumKurz('2026-12-31T23:30:00'), '01.01.2027', '00:30 am Neujahrstag, Winterzeit');
gleich(datumKurz('2025-03-01T00:00:00'), '01.03.2025', 'Altdaten-Import setzt 00:00');

// Stichtag-Vorgabe (Inventur.tsx)
gleich(heuteBerlin(new Date('2026-12-31T23:30:00Z')), '2027-01-01', '00:30 am Neujahrstag');
gleich(heuteBerlin(new Date('2026-12-31T22:30:00Z')), '2026-12-31', '23:30 an Silvester');
gleich(heuteBerlin(new Date('2026-10-09T22:30:00Z')), '2026-10-10', '00:30 Sommerzeit');

console.log(`p41d-berlin.check: ${faelle} Fälle ok`);
