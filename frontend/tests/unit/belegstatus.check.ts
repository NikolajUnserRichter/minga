// Prüft die Anzeige des Belegstatus ohne Browser und ohne Testframework (Paket 4, Abschnitt C).
// Lauf: node tests/unit/belegstatus.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import {
  LUECKEN_TEXT, datumKurz, heuteBerlin, lieferscheinZelle, rechnungZelle, versandZelle, vorgabeVon, zahlungZelle,
} from '../../src/services/belegstatus.ts';
import type { BelegstatusZeile } from '../../src/services/belegstatus.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

function zeile(teil: Partial<BelegstatusZeile>): BelegstatusZeile {
  return {
    order_id: 'o1', order_number: 'BE-20261008-0006', order_status: 'GELIEFERT',
    customer_id: 'k1', customer_name: 'Ferdinand Bierbichler GmbH & Co. KG', abrechnung: 'EINZELN',
    liefertag: '2026-10-09', geliefert: true, lieferscheine: [], rechnung: null,
    extern_abgerechnet: false, rechnung_faellig_ab: '2026-10-09', luecken: [], unvollstaendig: false,
    ...teil,
  };
}
const ls = { id: 'l1', nummer: 'LS-20261009-0001', status: 'GELIEFERT' };
const re = (teil: Record<string, unknown> = {}) => ({
  id: 'r1', nummer: 'RE-2026-00008', status: 'OFFEN', sammelrechnung: false,
  versendet_am: null as string | null, bezahlt: false, ...teil,
});

// Datum: Tag wie geschrieben, Zeitstempel ohne Zone = UTC, angezeigt in Berlin
gleich(datumKurz('2026-10-08'), '08.10.2026', 'Tag');
gleich(datumKurz('2026-10-08T06:19:56.168045'), '08.10.2026', 'Zeitstempel vom Server');
gleich(datumKurz('2026-10-31T23:30:00'), '01.11.2026', 'UTC 23:30 = Berlin 00:30 am 1.11.');
gleich(datumKurz(null), '', 'ohne Datum');
gleich(datumKurz('kein Datum'), '', 'unlesbar');

// Stichtag und Vorgabe „von“ (1. des Vormonats)
gleich(heuteBerlin(new Date('2026-10-08T22:30:00Z')), '2026-10-09', 'heute in Berlin');
gleich(vorgabeVon('2026-10-09'), '2026-09-01', 'Vormonat');
gleich(vorgabeVon('2027-01-15'), '2026-12-01', 'Jahreswechsel');

// Lieferschein
gleich(lieferscheinZelle(zeile({ lieferscheine: [ls] })), { zeichen: '✔', text: 'LS-20261009-0001', ton: 'ok' }, 'LS da');
gleich(lieferscheinZelle(zeile({ lieferscheine: [ls, { ...ls, nummer: 'LS-20261009-0002' }] })).text,
  'LS-20261009-0001, LS-20261009-0002', 'zwei LS');
gleich(lieferscheinZelle(zeile({})), { zeichen: '✘', text: 'fehlt', ton: 'neutral' }, 'LS fehlt (keine Lücke)');
gleich(lieferscheinZelle(zeile({ extern_abgerechnet: true })), { zeichen: '—', text: 'extern', ton: 'neutral' }, 'extern');

// Rechnung
gleich(rechnungZelle(zeile({ luecken: ['OHNE_RECHNUNG'] })), { zeichen: '✘', text: 'fehlt', ton: 'luecke' }, 'RE fehlt');
gleich(rechnungZelle(zeile({ rechnung: re({ status: 'ENTWURF', nummer: 'ENTWURF-AB12' }), luecken: ['RECHNUNG_ENTWURF'] })),
  { zeichen: '◐', text: 'Entwurf', ton: 'luecke' }, 'Entwurf');
gleich(rechnungZelle(zeile({ rechnung: re() })), { zeichen: '✔', text: 'RE-2026-00008', ton: 'ok' }, 'RE da');
gleich(rechnungZelle(zeile({ rechnung: re({ sammelrechnung: true }) })).text, 'RE-2026-00008 (Sammelrechnung)', 'Sammel');
gleich(rechnungZelle(zeile({ extern_abgerechnet: true })), { zeichen: '✔', text: 'extern (DATEV)', ton: 'neutral' }, 'extern');
gleich(rechnungZelle(zeile({ abrechnung: 'MONATLICH', rechnung_faellig_ab: '2026-11-01' })),
  { zeichen: '—', text: 'Monatsrechnung ab 01.11.2026', ton: 'neutral' }, 'Monatskunde');
gleich(rechnungZelle(zeile({ geliefert: false, liefertag: '2026-10-12', rechnung_faellig_ab: '2026-10-12' })),
  { zeichen: '—', text: 'nicht geliefert', ton: 'neutral' }, 'noch nicht geliefert');
gleich(rechnungZelle(zeile({ rechnung_faellig_ab: '2026-10-12', liefertag: '2026-10-12' })),
  { zeichen: '—', text: 'fällig ab 12.10.2026', ton: 'neutral' }, 'geliefert, noch nicht fällig');

// Versand
gleich(versandZelle(zeile({ rechnung: re(), luecken: ['NICHT_VERSENDET'] })),
  { zeichen: '✘', text: 'nicht versendet', ton: 'luecke' }, 'nicht versendet');
gleich(versandZelle(zeile({ rechnung: re({ versendet_am: '2026-10-08T06:19:56.168045' }) })),
  { zeichen: '✔', text: '08.10.2026', ton: 'ok' }, 'versendet');
gleich(versandZelle(zeile({ rechnung: re({ status: 'ENTWURF' }) })), { zeichen: '—', text: '', ton: 'neutral' }, 'Entwurf');
gleich(versandZelle(zeile({})), { zeichen: '—', text: '', ton: 'neutral' }, 'ohne RE');

// Zahlung (nur Anzeige, keine Lücke)
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'BEZAHLT', bezahlt: true }) })), { zeichen: '✔', text: 'bezahlt', ton: 'ok' }, 'bezahlt');
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'UEBERFAELLIG' }) })), { zeichen: '✘', text: 'überfällig', ton: 'neutral' }, 'überfällig');
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'TEILBEZAHLT' }) })).text, 'teilbezahlt', 'teilbezahlt');
gleich(zahlungZelle(zeile({})), { zeichen: '—', text: '', ton: 'neutral' }, 'ohne RE');

// Texte der Lücken
gleich(Object.keys(LUECKEN_TEXT), ['OHNE_RECHNUNG', 'RECHNUNG_ENTWURF', 'NICHT_VERSENDET'], 'Lückenarten wie der Server');

console.log(`belegstatus.check: ${faelle} Fälle ok`);
