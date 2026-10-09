import assert from 'node:assert/strict';
import { eingabeAusZahl, positionsaenderung } from '../../src/services/positionsaenderung.ts';

const alt = { quantity: 4, unit_price: 18.68 };
for (const eingabe of ['4.000', '1.000,5', '1.000.000', ' 12.345,67 ']) {
  assert.deepEqual(positionsaenderung(alt, eingabe, '18,68'), {
    fehler: 'Menge: bitte ohne Tausenderpunkt eingeben, z. B. 1000,5',
  });
  assert.deepEqual(positionsaenderung(alt, '4', eingabe), {
    fehler: 'Einzelpreis: bitte ohne Tausenderpunkt eingeben, z. B. 1000,5',
  });
}
for (const [wert, erwartet] of [['4.000', '4'], ['2.500', '2,5'], [0.125, '0,125'], [1000.5, '1000,5']] as const) {
  assert.equal(eingabeAusZahl(wert), erwartet);
}
const { euro } = await import('../../src/services/zahlenformat.ts');
for (const [wert, erwartet] of [[18.68, '18,68 €'], ['18.6800', '18,68 €'], [0, '0,00 €'], [-18.68, '-18,68 €']] as const) {
  assert.equal(euro(wert), erwartet);
}
assert.deepEqual(positionsaenderung(alt, '0.125', '18.68'), { daten: { quantity: 0.125 } });
assert.deepEqual(positionsaenderung(alt, '4,000', '18,68'), { daten: {} });
console.log('p4fix7-zahlen.check: 18 Fälle ok');
