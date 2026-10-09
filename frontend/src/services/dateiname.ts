/**
 * Dateiname eines Downloads aus dem Kopf Content-Disposition (B7, Paket 3).
 *
 * Der Server benennt Belege nach ihrer Nummer (RE-2026-00002.pdf,
 * AB-…pdf, LS-…pdf, PL-…pdf, Entwurf-…pdf); das Frontend übernimmt den
 * Namen und erfindet keinen eigenen. Nach RFC 6266 geht filename* (UTF-8,
 * prozentkodiert, RFC 5987) vor filename. Fehlt der Kopf — etwa weil der
 * Browser ihn cross-origin nicht lesen darf —, gilt der Ersatzname des
 * Aufrufers.
 *
 * Bewusst ohne Importe: tests/unit/dateiname.check.ts lädt die Datei direkt
 * mit Node.
 */
export function dateinameAusHeader(kopf: unknown, ersatz: string): string {
  if (typeof kopf !== 'string' || !kopf) return ersatz;

  const erweitert = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(kopf);
  if (erweitert) {
    try {
      const name = ohnePfad(decodeURIComponent(erweitert[1].trim()));
      if (name) return name;
    } catch {
      // kaputte Prozentkodierung: weiter mit filename=
    }
  }

  const einfach = /filename\s*=\s*(?:"([^"]*)"|([^;]*))/i.exec(kopf);
  const name = ohnePfad((einfach?.[1] ?? einfach?.[2] ?? '').trim());
  return name || ersatz;
}

/** Pfadtrenner aus dem Kopf dürfen nie einen Ordner im Dateinamen bilden. */
function ohnePfad(name: string): string {
  return name.replace(/[\\/]/g, '_');
}
