// Prüft die Aufbereitung des Bestellverlaufs ohne Browser und ohne Testframework
// (Paket 4.1, Abschnitt V). Lauf: node tests/unit/bestellverlauf.check.ts
// (Node >= 23.6: TypeScript ohne Build) oder npx --no-install tsx tests/unit/bestellverlauf.check.ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  AKTION_TEXT, AUSGEBLENDET_TEXT, aktionText, detailsText, statusText, verlaufAufbereiten,
  werText, wertText, zeitBerlin,
} from '../../src/services/bestellverlauf.ts';
import type { VerlaufEintrag } from '../../src/services/bestellverlauf.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

function eintrag(teil: Partial<VerlaufEintrag>): VerlaufEintrag {
  return {
    id: 'e1', order_id: 'o1', action: 'UPDATE', field_name: null, line_id: null,
    old_values: null, new_values: null, user_id: 'u1', user_name: 'testuser',
    created_at: '2026-10-09T21:07:12.123456', reason: null, ...teil,
  };
}

// Jede Aktion, die der Server schreibt, hat einen deutschen Text (Gegenstück:
// action="…" in den fünf Backend-Dateien, auch der Standardwert von setze_status)
const dateien = ['app/api/v1/sales.py', 'app/api/v1/imports.py', 'app/api/v1/documents.py',
  'app/services/steuersatz_korrektur.py', 'app/services/order_status_service.py'];
const imCode = new Set<string>();
for (const datei of dateien) {
  const py = readFileSync(new URL(`../../../backend/${datei}`, import.meta.url), 'utf8');
  for (const treffer of py.matchAll(/\baction(?::\s*str)?\s*=\s*"([A-Z_]+)"/g)) imCode.add(treffer[1]);
}
gleich([...imCode].sort(), ['ADD_LINE', 'BULK_STATUS_CHANGE', 'CONFIRM', 'DELETE_LINE', 'IMPORT',
  'LIEFERDATUM_NACHGETRAGEN', 'LIEFERSCHEIN_QUITTIERT', 'STATUS_CHANGE', 'STEUERSATZ_KORREKTUR',
  'UPDATE', 'UPDATE_LINE'], 'Aktionen im Backend');
gleich([...imCode].filter((a) => !(a in AKTION_TEXT)), [], 'jede Aktion übersetzt');
gleich(aktionText('LIEFERSCHEIN_QUITTIERT'), 'Lieferschein quittiert', 'Aktion');
gleich(aktionText('RECHNUNG_ZUGEORDNET'), 'Rechnung zugeordnet', 'Runbook-Aktion');
gleich(aktionText('STATUS_KORREKTUR'), 'Sonstige Änderung (STATUS_KORREKTUR)', 'unbekannte Aktion');

// Zeit: Server speichert UTC ohne Zone, angezeigt in Berlin (Sommer-/Winterzeit)
gleich(zeitBerlin('2026-10-09T21:07:12.123456'), '09.10.2026 23:07', 'Sommerzeit');
gleich(zeitBerlin('2026-10-31T23:30:00'), '01.11.2026 00:30', 'Winterzeit, Tageswechsel');
gleich(zeitBerlin('2026-10-09T21:07:12Z'), '09.10.2026 23:07', 'mit Zone');
gleich(zeitBerlin('kein Datum'), '', 'unlesbar');

// Wer
gleich(werText({ user_name: 'gernot', user_id: 'u1' }), 'gernot', 'Benutzer');
gleich(werText({ user_name: 'Systemkorrektur', user_id: null }), 'NovaERP (Datenkorrektur)', 'Runbook');
gleich(werText({ user_name: 'systemkorrektur', user_id: 'u1' }), 'NovaERP (Datenkorrektur)', 'Runbook 09.10. (Prod: klein, mit user_id)');
gleich(werText({ user_name: 'Datenkorrektur', user_id: null }), 'NovaERP (Datenkorrektur)', 'Steuersatz-Korrektur');
gleich(werText({ user_name: null, user_id: 'u1' }), 'Benutzer (Name nicht gespeichert)', 'Alteintrag vor V.1');
gleich(werText({ user_name: null, user_id: null }), 'System (automatisch)', 'ohne Login');

// Status mit den Wörtern der übrigen Oberfläche (statusLabels.ts)
gleich(statusText({ old_values: { status: 'ENTWURF' }, new_values: { status: 'BESTAETIGT' } }),
  'Entwurf → Bestätigt', 'Bestätigen');
gleich(statusText({ old_values: { status: 'BESTAETIGT' }, new_values: { status: 'IN_PRODUKTION' } }),
  'Bestätigt → Gepackt', 'IN_PRODUKTION heißt Gepackt');
gleich(statusText({ old_values: null, new_values: { status: 'BESTAETIGT' } }), 'Bestätigt', 'Import');
gleich(statusText({ old_values: { notes: null }, new_values: { notes: 'Tor 2' } }), null, 'kein Status');

// Werte als Kurztext
gleich(wertText('quantity', '4.000'), '4', 'Menge ganz');
gleich(wertText('quantity', '2.500'), '2,5', 'Menge mit Komma');
gleich(wertText('unit_price', '4.5000'), '4,50 €', 'Preis');
gleich(wertText('unit_price', '0.0833'), '0,0833 €', 'Preis mit 4 Stellen');
gleich(wertText('discount_percent', '10.00'), '10 %', 'Rabatt');
gleich(wertText('tax_rate', 'REDUZIERT'), '7 %', 'Steuersatz');
gleich(wertText('requested_delivery_date', '2026-10-12'), '12.10.2026', 'Tag');
gleich(wertText('notes', null), 'leer', 'leer');
gleich(wertText('notes', 'x'.repeat(80)), `${'x'.repeat(59)}…`, 'gekürzt');
gleich(wertText('customer_reference', '4711'), '4711', 'Nummer bleibt Text');

// Details je Aktion (Formen wie vom Server, gemessen auf 1e2238b + V.1/V.2)
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE',
  old_values: { quantity: '4.000', unit_price: '4.5000', tax_rate: 'REDUZIERT', discount_percent: '0' },
  new_values: { position: 1, product: 'Erbsen-Schale', quantity: '6', unit_price: '4.5000', tax_rate: 'REDUZIERT', discount_percent: '0' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6'], 'Menge geändert');
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE',
  old_values: { discount_percent: '0', quantity: '4.000', tax_rate: 'REDUZIERT', unit_price: '4.5000' },
  new_values: { discount_percent: '10', position: 1, product: 'Erbsen-Schale', quantity: '6', tax_rate: 'REDUZIERT', unit_price: '3.80' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6', 'Preis: 4,50 € → 3,80 €', 'Rabatt: 0 % → 10 %'], 'Preis und Rabatt, feste Reihenfolge');
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE', werte_ausgeblendet: true,
  old_values: { quantity: '4.000' }, new_values: { position: 1, product: 'Erbsen-Schale', quantity: '6' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6', AUSGEBLENDET_TEXT], 'Halle');
gleich(detailsText(eintrag({
  action: 'ADD_LINE', new_values: { position: 3, product: 'Senf-Schale', quantity: '1', unit_price: '2.80', discount_percent: '0' },
})), ['Pos. 3 · Senf-Schale', 'Menge: 1', 'Preis: 2,80 €'], 'neue Position ohne Rabatt-Rauschen');
gleich(detailsText(eintrag({
  action: 'DELETE_LINE', old_values: { position: 2, product: 'Radieschen-Schale', quantity: '2.000' },
})), ['Pos. 2 · Radieschen-Schale', 'Menge: 2'], 'Position entfernt');
gleich(detailsText(eintrag({ old_values: { notes: null }, new_values: { notes: 'Tor 2' } })),
  ['Notizen: leer → Tor 2'], 'Kopf geändert');
gleich(detailsText(eintrag({
  old_values: { delivery_address: "{'strasse': 'Hof'}" }, new_values: { delivery_address: "{'strasse': 'Tor 2'}" },
})), ['Lieferadresse geändert'], 'Adresse');
gleich(detailsText(eintrag({
  action: 'STATUS_CHANGE',
  old_values: { status: 'IN_PRODUKTION', actual_delivery_date: null },
  new_values: { status: 'GELIEFERT', actual_delivery_date: '2026-10-09' },
})), ['Geliefert am: leer → 09.10.2026'], 'Ausliefern');
gleich(detailsText(eintrag({
  action: 'IMPORT', new_values: { status: 'BESTAETIGT', bestell_nr_extern: '4711', datei: 'bestellungen.xlsx' },
})), ['Bestellnr. extern: 4711', 'Datei: bestellungen.xlsx'], 'Import');
gleich(detailsText(eintrag({
  action: 'STEUERSATZ_KORREKTUR', user_name: 'Datenkorrektur', user_id: null,
  old_values: { total_vat: '2.17', total_gross: '33.17', positionen: [{ position: 1, tax_rate: 'REDUZIERT', line_vat: '2.17', line_gross: '33.17' }] },
  new_values: { positionen: [{ position: 1, tax_rate: 'STANDARD', line_vat: '5.89', line_gross: '36.89' }], total_vat: '5.89', total_gross: '36.89' },
})), ['Pos. 1: Steuersatz: 7 % → 19 %, MwSt: 2,17 € → 5,89 €, Brutto: 33,17 € → 36,89 €',
  'MwSt gesamt: 2,17 € → 5,89 €', 'Brutto gesamt: 33,17 € → 36,89 €'], 'Steuersatz-Korrektur');
gleich(detailsText(eintrag({
  action: 'RECHNUNG_ZUGEORDNET', user_name: 'Systemkorrektur', old_values: null, new_values: { invoice: 'RE-2026-00005' },
})), ['Rechnung: RE-2026-00005'], 'Runbook-Form wie in Prod (Verwaltung)');
gleich(detailsText(eintrag({ action: 'RECHNUNG_ZUGEORDNET', old_values: {}, new_values: {}, werte_ausgeblendet: true })),
  [AUSGEBLENDET_TEXT], 'Runbook für die Halle');

// Ganze Zeilen: chronologisch (Server liefert neueste zuerst), Grund getrimmt
const roh = [
  eintrag({ id: 'e3', action: 'STATUS_CHANGE', created_at: '2026-10-09T05:10:00.000001',
    old_values: { status: 'BESTAETIGT' }, new_values: { status: 'IN_PRODUKTION' }, reason: 'Im Tagesplan als gepackt markiert' }),
  eintrag({ id: 'e2', action: 'CONFIRM', created_at: '2026-10-09T05:10:00.000001',
    old_values: { status: 'ENTWURF' }, new_values: { status: 'BESTAETIGT' }, reason: 'Beim Packen im Tagesplan bestätigt' }),
  eintrag({ id: 'e1', action: 'UPDATE', created_at: '2026-10-08T16:00:00',
    old_values: { notes: null }, new_values: { notes: 'Tor 2' }, reason: '  ' }),
];
const zeilen = verlaufAufbereiten(roh);
gleich(zeilen.map((z) => z.id), ['e1', 'e2', 'e3'], 'älteste zuerst, gleiche Zeit in Server-Reihenfolge umgekehrt');
gleich(zeilen[1], {
  id: 'e2', zeit: '09.10.2026 07:10', aktion: 'Bestätigt', status: 'Entwurf → Bestätigt', wer: 'testuser',
  details: [], grund: 'Beim Packen im Tagesplan bestätigt',
}, 'Zeile CONFIRM');
gleich(zeilen[0].grund, null, 'leerer Grund');
gleich(verlaufAufbereiten([]), [], 'leer');

console.log(`bestellverlauf.check: ${faelle} Fälle ok`);
