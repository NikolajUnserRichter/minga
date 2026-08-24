/**
 * Drucken aus dem Browser heraus.
 *
 * Der ERP-Server steht im Rechenzentrum, der Etikettendrucker im Hofnetz —
 * eine direkte Verbindung gibt es also nicht. Gedruckt wird deshalb dort, wo
 * beide erreichbar sind: im Browser des Nutzers, über den Systemdruckdialog.
 * Der Drucker wird dort ausgewählt wie in jedem anderen Programm auch.
 */

/** Wie lange das versteckte iframe am Leben bleibt (ms). */
const AUFRAEUM_VERZOEGERUNG_MS = 60_000;

/**
 * Öffnet ein PDF im Druckdialog, ohne den Umweg über den Download-Ordner.
 *
 * @param daten PDF-Bytes, wie sie eine Axios-Antwort mit responseType 'blob' liefert
 */
export function druckePdf(daten: BlobPart): void {
  const url = window.URL.createObjectURL(new Blob([daten], { type: 'application/pdf' }));

  const rahmen = document.createElement('iframe');
  rahmen.style.position = 'fixed';
  rahmen.style.right = '0';
  rahmen.style.bottom = '0';
  rahmen.style.width = '0';
  rahmen.style.height = '0';
  rahmen.style.border = '0';
  rahmen.src = url;

  rahmen.onload = () => {
    try {
      rahmen.contentWindow?.focus();
      rahmen.contentWindow?.print();
    } catch {
      // Kein eingebauter PDF-Viewer (kommt auf Mobilgeräten vor): dann eben in
      // einem neuen Tab öffnen, von dort kann der Nutzer selbst drucken.
      window.open(url, '_blank');
    }
    // Erst aufräumen, wenn der Druckdialog durch ist — sonst zieht der Browser
    // dem laufenden Job das Dokument unter den Füßen weg.
    window.setTimeout(() => {
      rahmen.remove();
      window.URL.revokeObjectURL(url);
    }, AUFRAEUM_VERZOEGERUNG_MS);
  };

  document.body.appendChild(rahmen);
}

/** Speichert ein PDF als Datei — die Rückfalltür, wenn der Druckdialog klemmt. */
export function ladePdfHerunter(daten: BlobPart, dateiname: string): void {
  const url = window.URL.createObjectURL(new Blob([daten], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', dateiname);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
