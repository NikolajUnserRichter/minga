// Prüft die Rollengruppen und die Konditionsfelder der Oberfläche gegen das
// Backend (P4-D.3), ohne Browser und ohne Testframework.
// Lauf: node tests/unit/rollen.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  KAUFMAENNISCHE_ROLLEN, KUNDEN_KONDITIONSFELDER, ROLLEN_OHNE_HALLE, hatEineRolle, ohneKonditionen,
} from '../../src/services/rollen.ts';

// Gegenstück: backend/app/core/rollen.py (Konstanten, zwei Listen, KUNDENFELDER_KAUFMAENNISCH)
const py = readFileSync(new URL('../../../backend/app/core/rollen.py', import.meta.url), 'utf8');
const konstanten = new Map(
  [...py.matchAll(/^([A-Z]+) = "([a-z_]+)"$/gm)].map((m) => [m[1], m[2]] as [string, string]),
);
const liste = (name: string): string[] => {
  const m = py.match(new RegExp(`^${name} = \\[([A-Z, ]+)\\]$`, 'm'));
  assert.ok(m, `${name} nicht in rollen.py gefunden`);
  return m[1].split(',').map((s) => konstanten.get(s.trim()) ?? `?${s.trim()}`);
};
assert.deepEqual([...ROLLEN_OHNE_HALLE].sort(), liste('ROLLEN_OHNE_HALLE').sort());
assert.deepEqual([...KAUFMAENNISCHE_ROLLEN].sort(), liste('KAUFMAENNISCHE_ROLLEN').sort());
const block = py.match(/^KUNDENFELDER_KAUFMAENNISCH = \{\n([\s\S]*?)^\}$/m);
assert.ok(block, 'KUNDENFELDER_KAUFMAENNISCH nicht in rollen.py gefunden');
const konditionen = [...block[1].matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => m[1]);
assert.equal(konditionen.length, 11, `KUNDENFELDER_KAUFMAENNISCH: ${konditionen.join(', ')}`);
assert.deepEqual([...KUNDEN_KONDITIONSFELDER].sort(), konditionen.sort());

const faelle: Array<[string[] | undefined, readonly string[], boolean]> = [
  [undefined, ROLLEN_OHNE_HALLE, false],
  [[], ROLLEN_OHNE_HALLE, false],
  [['production_staff'], ROLLEN_OHNE_HALLE, false],
  [['production_staff', 'sales'], ROLLEN_OHNE_HALLE, true],
  [['production_planner'], ROLLEN_OHNE_HALLE, true],
  [['production_planner'], KAUFMAENNISCHE_ROLLEN, false],
  [['accounting'], KAUFMAENNISCHE_ROLLEN, true],
  [['offline_access', 'uma_authorization'], KAUFMAENNISCHE_ROLLEN, false],
];
for (const [rollen, gesucht, erwartet] of faelle) {
  assert.equal(hatEineRolle(rollen, gesucht), erwartet, `${JSON.stringify(rollen)} in ${gesucht.join('/')}`);
}

// Kundenformular der Halle (Customers.tsx): ohne Konditionen, alles andere bleibt.
const formular = {
  name: 'Großer Kern', telefon: '089 1', aktiv: true, show_prices_on_delivery_note: true,
  confirmation_emails: ['ab@grosser-kern.de'], payment_terms: 'NET_14', discount_percent: 0,
  skonto_percent: 0, skonto_days: 0, packaging_fee_amount: 0, packaging_fee_percent: 0,
  invoice_mode: 'EINZELN', pfand_abrechnung: 'JE_LIEFERUNG',
};
assert.deepEqual(ohneKonditionen(formular), {
  name: 'Großer Kern', telefon: '089 1', aktiv: true, show_prices_on_delivery_note: true,
  confirmation_emails: ['ab@grosser-kern.de'],
});
assert.equal(formular.payment_terms, 'NET_14', 'ohneKonditionen ändert die Vorlage nicht');
console.log(`rollen.check: 3 Listen wie im Backend, ${faelle.length} Fälle ok, Formular ohne Konditionen ok`);
