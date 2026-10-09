// Prüft die Ablage im Belegordner ohne Browser und ohne Testframework (Abschnitt O).
// Lauf: node tests/unit/belegpfad.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import {
  ablageAnzeige, belegablage, belegartDerRechnung, belegmonat, istExport, nameMitZaehler, sichererName,
} from '../../src/services/belegpfad.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

// Belegart aus der Rechnung, Vorrang wie die Typ-Spalte der Rechnungsliste
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'OFFEN' }), 'Rechnungen', 'Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'BEZAHLT', beleg_art: null }), 'Rechnungen', 'Monatsrechnung ist eine Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'STORNIERT' }), 'Rechnungen', 'stornierte Rechnung bleibt Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: 'a1' }), 'Stornorechnungen', 'Stornorechnung');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: 'a1', beleg_art: 'LEERGUT' }), 'Stornorechnungen', 'Storno eines Leergutbelegs');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: null }), 'Gutschriften', 'Gutschrift ohne Original');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'OFFEN', beleg_art: 'LEERGUT' }), 'Leergut', 'Leergutbeleg');
gleich(belegartDerRechnung({ invoice_type: 'PROFORMA', status: 'OFFEN' }), 'Proformarechnungen', 'Proforma ist keine Steuerrechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'ENTWURF' }), 'Entwürfe', 'Entwurf');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'ENTWURF', beleg_art: 'LEERGUT' }), 'Entwürfe', 'Leergut-Entwurf');

// Monat nach Belegdatum (Berlin); ohne Datum der heutige Monat in Berlin
const jetzt = new Date('2026-12-31T23:30:00Z'); // in Berlin schon 01.01.2027
gleich(belegmonat('2026-10-31', jetzt), '2026-10', 'Datum ohne Uhrzeit');
gleich(belegmonat('2026-10-31T21:59:00', jetzt), '2026-10', 'Zeitstempel ohne Zone = UTC');
gleich(belegmonat('2026-10-31T23:30:00', jetzt), '2026-11', 'UTC 23:30 = Berlin 00:30 am 1.11.');
gleich(belegmonat('2026-10-31T23:30:00.123456', jetzt), '2026-11', 'Mikrosekunden wie vom Server');
gleich(belegmonat('2026-09-30T22:30:00Z', jetzt), '2026-10', 'Sommerzeit: UTC+2');
gleich(belegmonat('2026-10-31T23:30:00+01:00', jetzt), '2026-10', 'Zeitstempel mit Zone');
gleich(belegmonat(null, jetzt), '2027-01', 'ohne Datum: heute in Berlin');
gleich(belegmonat(undefined, jetzt), '2027-01', 'ohne Datum (undefined)');
gleich(belegmonat('', jetzt), '2027-01', 'leeres Datum');
gleich(belegmonat('kein Datum', jetzt), '2027-01', 'unlesbares Datum');

// Ablage und Anzeige im Toast
const ablage = belegablage('Rechnungen', '2026-10-09', 'RE-2026-00006.pdf', jetzt);
gleich(ablage, { ordner: ['Rechnungen', '2026-10'], datei: 'RE-2026-00006.pdf' }, 'Ablage einer Rechnung');
gleich(ablageAnzeige('Belege', ablage), 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf', 'Anzeige');
gleich(ablageAnzeige('Belege', ablage, 'RE-2026-00006 (1).pdf'), 'Belege/Rechnungen/2026-10/RE-2026-00006 (1).pdf', 'Anzeige mit Zusatz');
gleich(belegablage('Mahnungen', null, 'Zahlungserinnerung_RE-2026-00006_Stufe1.pdf', jetzt).ordner, ['Mahnungen', '2027-01'], 'Mahnung: heute');

// Zusatz (n) für eine vorhandene Datei
gleich(nameMitZaehler('RE-2026-00006.pdf', 1), 'RE-2026-00006 (1).pdf', 'Zusatz vor der Endung');
gleich(nameMitZaehler('DATEV_Export_2026-10-01_2026-10-31.csv', 2), 'DATEV_Export_2026-10-01_2026-10-31 (2).csv', 'Zusatz CSV');
gleich(nameMitZaehler('Beleg', 1), 'Beleg (1)', 'ohne Endung');

// Namen, die Windows oder der Browser ablehnen
gleich(sichererName('Zahlungserinnerung_RE:1?.pdf'), 'Zahlungserinnerung_RE_1_.pdf', 'verbotene Zeichen');
gleich(sichererName('a/b\\c.pdf'), 'a_b_c.pdf', 'Pfadtrenner');
gleich(sichererName('RE-1.pdf. '), 'RE-1.pdf', 'Punkt und Leerzeichen am Ende');
gleich(sichererName('..'), 'Beleg', 'nur Punkte');
gleich(belegablage('Entwürfe', '2026-10-09', 'Entwurf-B<>.pdf', jetzt).datei, 'Entwurf-B__.pdf', 'Ablage nimmt sicheren Namen');

// Exporte bekommen nie einen Ersetzen-Dialog
gleich(istExport('Lastschriften'), true, 'SEPA-CSV ist Export');
gleich(istExport('DATEV-Exporte'), true, 'DATEV ist Export');
gleich(istExport('Rechnungen'), false, 'Rechnung ist Beleg');

console.log(`belegpfad.check: ${faelle} Fälle ok`);
