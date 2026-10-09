// Prüft positionsaenderung ohne Browser und ohne Testframework (Paket 4, B; G21).
// Lauf: node tests/unit/positionsaenderung.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { eingabeAusZahl, positionsaenderung } from '../../src/services/positionsaenderung.ts';

const MENGE_FALSCH = { fehler: 'Menge: eine Zahl größer als 0 mit höchstens 3 Nachkommastellen' };
const PREIS_FALSCH = { fehler: 'Einzelpreis: eine Zahl ab 0 mit höchstens 4 Nachkommastellen' };
const MENGE_TAUSENDER = { fehler: 'Menge: bitte ohne Tausenderpunkt eingeben, z. B. 1000,5' };
const PREIS_TAUSENDER = { fehler: 'Einzelpreis: bitte ohne Tausenderpunkt eingeben, z. B. 1000,5' };
// Die API liefert Dezimalzahlen je nach Weg als Zahl oder als Text ("10.000")
const alt = { quantity: '10.000', unit_price: 2.5 };

const faelle: Array<[string, string, unknown]> = [
  ['10', '2,50', { daten: {} }],                              // nichts geändert
  ['8', '2,5', { daten: { quantity: 8 } }],                   // nur Menge
  ['10', '2,75', { daten: { unit_price: 2.75 } }],            // nur Preis, Komma
  ['12,5', '3.10', { daten: { quantity: 12.5, unit_price: 3.1 } }], // beides, Punkt
  [' 10 ', ' 0 ', { daten: { unit_price: 0 } }],              // Preis 0 erlaubt, Leerzeichen egal
  ['0,125', '0,0833', { daten: { quantity: 0.125, unit_price: 0.0833 } }],
  ['0', '2,5', MENGE_FALSCH],
  ['', '2,5', MENGE_FALSCH],
  ['-1', '2,5', MENGE_FALSCH],
  ['1,2345', '2,5', MENGE_FALSCH],                            // 4 Nachkommastellen
  ['zehn', '2,5', MENGE_FALSCH],
  ['10', '', PREIS_FALSCH],
  ['10', '-2', PREIS_FALSCH],
  ['10', '2,12345', PREIS_FALSCH],                            // 5 Nachkommastellen
  ['10', '1.000,00', PREIS_TAUSENDER],                        // Tausenderpunkt
  ['1.000', '2,5', MENGE_TAUSENDER],                          // mehrdeutig: 1000 oder 1?
  ['10', '1.000', PREIS_TAUSENDER],                           // mehrdeutig, nicht raten
];

for (const [menge, preis, erwartet] of faelle) {
  assert.deepEqual(positionsaenderung(alt, menge, preis), erwartet, `${menge} / ${preis}`);
}
assert.equal(eingabeAusZahl('10.000'), '10');
assert.equal(eingabeAusZahl(2.5), '2,5');
assert.equal(eingabeAusZahl('0.0833'), '0,0833');
console.log(`positionsaenderung.check: ${faelle.length + 3} Fälle ok`);
