// Prüft rechnungenJeReiter und reiterZaehler ohne Browser und ohne
// Testframework (Paket 4.1, Z: Reiterzähler der Rechnungsliste).
// Lauf: node tests/unit/rechnungsreiter.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { rechnungenJeReiter, reiterZaehler } from '../../src/services/rechnungssuche.ts';

const r = (nr: number, status: string, kunde: string | null) => ({
  invoice_number: `RE-2026-${String(nr).padStart(5, '0')}`,
  status,
  customer_name: kunde,
  customer_number: `KD-${10000 + nr}`,
});
const oekoringOffen = r(1, 'OFFEN', 'Ökoring Handels GmbH');
const oekoringBezahlt = r(2, 'BEZAHLT', 'Ökoring Handels GmbH');
const kernEntwurf = r(3, 'ENTWURF', 'Großer Kern GmbH');
const kernTeilbezahlt = r(4, 'TEILBEZAHLT', 'Großer Kern GmbH');
const ohneKunde = r(5, 'STORNIERT', null);
const kernUeberfaellig = r(6, 'UEBERFAELLIG', 'Großer Kern GmbH');
const liste = [oekoringOffen, oekoringBezahlt, kernEntwurf, kernTeilbezahlt, ohneKunde, kernUeberfaellig];
// GET /invoices/overdue liefert UEBERFAELLIG und überfällige TEILBEZAHLT
const ueberfaellig = [kernUeberfaellig, kernTeilbezahlt];

let faelle = 0;
// Erwartet je Reiter die letzte Ziffer der Rechnungsnummern, in Listenreihenfolge
const pruefe = (suche: string, erwartet: Record<'all' | 'open' | 'overdue' | 'paid', string[]>) => {
  const reiter = rechnungenJeReiter(liste, ueberfaellig, suche);
  for (const id of ['all', 'open', 'overdue', 'paid'] as const) {
    assert.deepEqual(reiter[id].map((x) => x.invoice_number.slice(-1)), erwartet[id], `${id} / "${suche}"`);
    faelle += 1;
  }
};
pruefe('', { all: ['1', '2', '3', '4', '5', '6'], open: ['1'], overdue: ['6', '4'], paid: ['2'] });
pruefe('kern', { all: ['3', '4', '6'], open: [], overdue: ['6', '4'], paid: [] });
pruefe('ÖKORING', { all: ['1', '2'], open: ['1'], overdue: [], paid: ['2'] });
pruefe('kd-10004', { all: ['4'], open: [], overdue: ['4'], paid: [] });
pruefe('00005', { all: ['5'], open: [], overdue: [], paid: [] });
pruefe('kern 00001', { all: [], open: [], overdue: [], paid: [] });

// Die Tabelle zeigt dieselben Objekte, die der Zähler zählt
const ohneSuche = rechnungenJeReiter(liste, ueberfaellig, '');
assert.equal(ohneSuche.open[0], oekoringOffen);
faelle += 1;
assert.equal(ohneSuche.overdue[1], kernTeilbezahlt);
faelle += 1;

// Zähler: an der Listengrenze ist die Zahl eine Untergrenze
const zaehler: Array<[number, boolean, number | string]> = [
  [0, false, 0],
  [7, false, 7],
  [100, true, '100+'],
  [12, true, '12+'],
  [0, true, 0],
];
for (const [anzahl, gekuerzt, erwartet] of zaehler) {
  assert.equal(reiterZaehler(anzahl, gekuerzt), erwartet, `${anzahl} / ${gekuerzt}`);
  faelle += 1;
}
console.log(`rechnungsreiter.check: ${faelle} Fälle ok`);
