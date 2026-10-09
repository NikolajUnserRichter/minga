// Prüft dateinameAusHeader ohne Browser und ohne Testframework (B7, Paket 3 Q3).
// Lauf: node tests/unit/dateiname.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { dateinameAusHeader } from '../../src/services/dateiname.ts';

const faelle: Array<[unknown, string]> = [
  // so liefert das Backend nach Q3
  [`attachment; filename="RE-2026-00002.pdf"; filename*=UTF-8''RE-2026-00002.pdf`, 'RE-2026-00002.pdf'],
  // filename* geht vor filename (RFC 6266), UTF-8 wird dekodiert
  [`attachment; filename="Entwurf-Backerei _.pdf"; filename*=UTF-8''Entwurf-B%C3%A4ckerei%20%E2%82%AC.pdf`, 'Entwurf-Bäckerei €.pdf'],
  // ohne Anführungszeichen (heutige Inventur- und Warenfluss-Endpunkte)
  ['attachment; filename=Zaehlliste_INV-2026-0001.pdf', 'Zaehlliste_INV-2026-0001.pdf'],
  // kaputte Prozentkodierung: zurück auf filename=
  [`attachment; filename="AB-1.pdf"; filename*=UTF-8''%E2%28`, 'AB-1.pdf'],
  // Pfadtrenner aus dem Kopf landen nie im Dateinamen
  ['attachment; filename="../x/RE-1.pdf"', '.._x_RE-1.pdf'],
  // kein Kopf (z. B. fehlende CORS-Freigabe): Ersatzname des Aufrufers
  [undefined, 'Ersatz.pdf'],
  ['', 'Ersatz.pdf'],
  ['inline', 'Ersatz.pdf'],
];

for (const [kopf, erwartet] of faelle) {
  assert.equal(dateinameAusHeader(kopf, 'Ersatz.pdf'), erwartet, String(kopf));
}
console.log(`dateiname.check: ${faelle.length} Fälle ok`);
