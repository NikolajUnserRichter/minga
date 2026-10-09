// Prüft rechnungPasstZurSuche ohne Browser und ohne Testframework (Paket 4, B; G05).
// Lauf: node tests/unit/rechnungssuche.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { rechnungPasstZurSuche } from '../../src/services/rechnungssuche.ts';

const oekoring = { invoice_number: 'RE-2026-00010', customer_name: 'Ökoring Handels GmbH', customer_number: 'KD-10006' };
const entwurf = { invoice_number: 'ENTWURF-75939B849826', customer_name: 'Großer Kern GmbH' };
const ohneKunde = { invoice_number: 'RE-2026-00001', customer_name: null };

const faelle: Array<[typeof oekoring | typeof entwurf | typeof ohneKunde, string, boolean]> = [
  [oekoring, '', true],                    // leere Suche zeigt alles
  [oekoring, '   ', true],
  [oekoring, 'RE-2026-00010', true],       // Nummer
  [oekoring, '00010', true],               // Teil der Nummer
  [oekoring, 'ökoring', true],             // Kundenname, Groß/klein egal
  [oekoring, 'ÖKORING', true],
  [oekoring, 'handels öko', true],         // jedes Wort, Reihenfolge egal
  [oekoring, 'kd-10006', true],            // Kundennummer
  [oekoring, 'ökoring 00011', false],      // ein Wort passt nicht
  [oekoring, 'Kern', false],
  [entwurf, 'entwurf', true],              // Entwurf ohne Nummer
  [entwurf, 'großer', true],
  [ohneKunde, '00001', true],              // ohne Kundenname kein Absturz
  [ohneKunde, 'gmbh', false],
];

for (const [rechnung, suche, erwartet] of faelle) {
  assert.equal(rechnungPasstZurSuche(rechnung, suche), erwartet, `${rechnung.invoice_number} / "${suche}"`);
}
console.log(`rechnungssuche.check: ${faelle.length} Fälle ok`);
