/**
 * Belegordner (Abschnitt O, Gernot 09.10.2026): Belege landen direkt in einem
 * gewählten Ordner, sortiert nach <Belegart>/<JJJJ-MM>/ (belegpfad.ts), statt
 * im Download-Ordner. File System Access API — nur Chrome und Edge am
 * Computer, nur über https bzw. localhost.
 *
 * Die Wahl gilt je Browser und Gerät: Das Ordner-Handle liegt in IndexedDB
 * dieser Adresse (jeder Mandant hat seine eigene Subdomain), der Server weiß
 * nichts davon. Die Schreibfreigabe fragt der Browser je Sitzung neu ab
 * (Chrome/Edge bieten „Bei jedem Besuch zulassen" an). Nach „Nicht zulassen"
 * fragt Chrome in dieser Sitzung nicht mehr (siehe freigabe).
 *
 * Rückfall auf den normalen Download — wie vor Abschnitt O — ohne Ordner, in
 * Browsern ohne die API, ohne Freigabe und bei jedem Schreibfehler. Eine Datei
 * geht nie verloren: Die SEPA-Einreichung und die Mahnstufe sind beim Abruf
 * schon vermerkt, ein zweiter Abruf ist nicht immer möglich.
 *
 * Bewusst ohne React-Import (Toast kommt als Parameter): Die Node-Prüfungen in
 * backend/tests (test_nachtrag_0910.py, Paket-3-Abnahme der SEPA-Liste) laden
 * diese Datei samt ihren Importen direkt.
 */
import { dateinameAusHeader } from './dateiname';
import { ablageAnzeige, belegablage, istExport, nameMitZaehler, type Belegart } from './belegpfad';

type Erlaubnis = 'granted' | 'denied' | 'prompt';

// Nicht in lib.dom (nur Chromium): Freigabe am Handle und der Ordnerdialog.
interface Ordner extends FileSystemDirectoryHandle {
  queryPermission(d: { mode: 'readwrite' }): Promise<Erlaubnis>;
  requestPermission(d: { mode: 'readwrite' }): Promise<Erlaubnis>;
}
type OrdnerDialog = (o: { id?: string; mode?: 'readwrite'; startIn?: string }) => Promise<FileSystemDirectoryHandle>;

const DB_NAME = 'novaerp-belegordner';
const STORE = 'ordner';
const SCHLUESSEL = 'belege';

function ordnerDialog(): OrdnerDialog | undefined {
  return (window as unknown as { showDirectoryPicker?: OrdnerDialog }).showDirectoryPicker;
}

/** Kann dieser Browser Belege in einen Ordner schreiben? */
export function belegordnerMoeglich(): boolean {
  return typeof window !== 'undefined'
    && window.isSecureContext
    && typeof ordnerDialog() === 'function'
    && typeof indexedDB !== 'undefined';
}

function datenbank(): Promise<IDBDatabase> {
  return new Promise((ok, fehler) => {
    const anfrage = indexedDB.open(DB_NAME, 1);
    anfrage.onupgradeneeded = () => anfrage.result.createObjectStore(STORE);
    anfrage.onsuccess = () => ok(anfrage.result);
    anfrage.onerror = () => fehler(anfrage.error);
  });
}

async function speicher<T>(modus: IDBTransactionMode, tun: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await datenbank();
  try {
    return await new Promise<T>((ok, fehler) => {
      const anfrage = tun(db.transaction(STORE, modus).objectStore(STORE));
      anfrage.onsuccess = () => ok(anfrage.result);
      anfrage.onerror = () => fehler(anfrage.error);
    });
  } finally {
    db.close(); // wartet auf laufende Transaktionen
  }
}

async function gespeicherterOrdner(): Promise<Ordner | null> {
  if (!belegordnerMoeglich()) return null;
  try {
    return ((await speicher('readonly', (s) => s.get(SCHLUESSEL))) as Ordner | undefined) ?? null;
  } catch {
    return null;
  }
}

/** Name des gewählten Ordners, sonst null. */
export async function belegordnerName(): Promise<string | null> {
  return (await gespeicherterOrdner())?.name ?? null;
}

/** Freigabe-Stand für die Einstellungen; null = kein Ordner gewählt. */
export async function belegordnerErlaubnis(): Promise<Erlaubnis | null> {
  const ordner = await gespeicherterOrdner();
  if (!ordner) return null;
  try {
    return await ordner.queryPermission({ mode: 'readwrite' });
  } catch {
    return 'denied';
  }
}

/** Ordner wählen (Einstellungen, direkt aus dem Klick). null = Dialog abgebrochen. */
export async function belegordnerWaehlen(): Promise<string | null> {
  const dialog = ordnerDialog();
  if (!dialog || !belegordnerMoeglich()) return null;
  try {
    const ordner = await dialog({ id: 'novaerp-belege', mode: 'readwrite', startIn: 'documents' });
    await speicher('readwrite', (s) => s.put(ordner, SCHLUESSEL));
    return ordner.name;
  } catch (e) {
    if ((e as { name?: string })?.name === 'AbortError') return null;
    throw e;
  }
}

/** Ordner vergessen: Belege landen wieder im Download-Ordner. */
export async function belegordnerZuruecksetzen(): Promise<void> {
  if (!belegordnerMoeglich()) return;
  await speicher('readwrite', (s) => s.delete(SCHLUESSEL));
}

/**
 * Schreibfreigabe sichern. requestPermission verlangt eine frische
 * Nutzeraktion (Klick, wenige Sekunden): deshalb ruft belegHerunterladen das
 * VOR dem Abruf beim Server auf. Ergebnis (Chromium,
 * chrome_file_system_access_permission_context.cc):
 * - 'granted': frei.
 * - 'prompt': noch offen — Frage weggeklickt, oder ohne Nutzeraktion
 *   (SecurityError). Der Knopf „Zugriff erlauben" in den Einstellungen fragt neu.
 * - 'denied': „Nicht zulassen" bzw. in den Website-Einstellungen gesperrt.
 *   Chrome fragt in dieser Sitzung nicht mehr, auch nicht über den Knopf
 *   (requestPermission endet ohne Frage), erst nachdem alle Tabs dieser Seite
 *   geschlossen waren: ZUGRIFF_WIEDER_ERLAUBEN.
 */
async function freigabe(ordner: Ordner): Promise<Erlaubnis> {
  try {
    if ((await ordner.queryPermission({ mode: 'readwrite' })) === 'granted') return 'granted';
    return await ordner.requestPermission({ mode: 'readwrite' });
  } catch {
    return 'prompt';
  }
}

/** Der Weg nach „Nicht zulassen" (Warn-Toast und Karte in den Einstellungen). */
export const ZUGRIFF_WIEDER_ERLAUBEN = 'Wieder erlauben: alle Tabs dieser Seite schließen und neu öffnen '
  + 'oder Symbol links in der Adresszeile → Website-Einstellungen.';

/** Freigabe aus den Einstellungen anfragen (Knopf „Zugriff erlauben"). */
export async function belegordnerFreigeben(): Promise<boolean> {
  const ordner = await gespeicherterOrdner();
  return ordner ? (await freigabe(ordner)) === 'granted' : false;
}

export interface BelegAngaben {
  art: Belegart;
  /** Belegdatum (JJJJ-MM-TT oder Zeitstempel); fehlt es, gilt heute in Berlin. */
  datum?: string | null;
  /** Dateiname, falls der Server keinen Content-Disposition-Kopf schickt. */
  ersatzname: string;
  /** Standard application/pdf */
  mime?: string;
}

/** Was `laden` liefert: eine Axios-Antwort oder nur die Daten (DATEV). */
export interface Geladen {
  data: BlobPart;
  headers?: unknown;
}

export type BelegErgebnis =
  | { ort: 'ordner'; pfad: string }
  | { ort: 'download'; dateiname: string; hinweis?: string };

/** Das Nötige aus useToast(). */
export interface BelegToast {
  success: (meldung: string) => void;
  warning: (meldung: string, dauer?: number) => void;
}

/**
 * DIE Download-Funktion für Belege und Exporte. Reihenfolge: Ordner und
 * Freigabe (braucht die frische Nutzeraktion), dann `laden` (Server), dann
 * ablegen bzw. herunterladen. `laden` darf null liefern (Rückfrage
 * abgebrochen, nichts zu exportieren): dann geschieht nichts, Ergebnis null.
 * Fehler aus `laden` gehen an den Aufrufer; Fehler beim Ablegen enden im
 * normalen Download mit Hinweis. Mit `toast`: „Gespeichert in …" bzw. der
 * Hinweis; ohne Belegordner keine Meldung (Download wie bisher).
 */
export async function belegHerunterladen(
  angaben: BelegAngaben,
  laden: () => Promise<Geladen | null>,
  toast?: BelegToast,
): Promise<BelegErgebnis | null> {
  const ergebnis = await ablegenOderHerunterladen(angaben, laden);
  if (toast && ergebnis) {
    if (ergebnis.ort === 'ordner') toast.success(`Gespeichert in ${ergebnis.pfad}`);
    else if (ergebnis.hinweis) toast.warning(ergebnis.hinweis, 10000);
  }
  return ergebnis;
}

async function ablegenOderHerunterladen(
  angaben: BelegAngaben,
  laden: () => Promise<Geladen | null>,
): Promise<BelegErgebnis | null> {
  const ordner = await gespeicherterOrdner();
  const frei = ordner ? await freigabe(ordner) : null;

  const geladen = await laden();
  if (!geladen) return null;

  // B7: Der Server benennt die Datei (Belegnummer); ersatzname nur ohne Kopf
  const kopf = (geladen.headers as Record<string, unknown> | undefined)?.['content-disposition'];
  const dateiname = dateinameAusHeader(kopf, angaben.ersatzname);
  const blob = new Blob([geladen.data], { type: angaben.mime ?? 'application/pdf' });

  if (ordner && frei === 'granted') {
    try {
      return { ort: 'ordner', pfad: await ablegen(ordner, angaben, dateiname, blob) };
    } catch (e) {
      herunterladen(blob, dateiname);
      const grund = (e as { name?: string })?.name || 'Fehler';
      return {
        ort: 'download', dateiname,
        hinweis: `Belegordner „${ordner.name}" nicht beschreibbar (${grund}) — ${dateiname} liegt im Download-Ordner.`,
      };
    }
  }
  herunterladen(blob, dateiname);
  if (!ordner) return { ort: 'download', dateiname };
  if (frei === 'denied') {
    // Der Knopf in den Einstellungen hilft hier nicht (siehe freigabe)
    return {
      ort: 'download', dateiname,
      hinweis: `Zugriff auf den Belegordner „${ordner.name}" abgelehnt — ${dateiname} liegt im Download-Ordner. `
        + ZUGRIFF_WIEDER_ERLAUBEN,
    };
  }
  return {
    ort: 'download', dateiname,
    hinweis: `Kein Zugriff auf den Belegordner „${ordner.name}" — ${dateiname} liegt im Download-Ordner. `
      + 'Zugriff erlauben: Einstellungen → Belegordner.',
  };
}

/**
 * Schreibt nach <Ordner>/<Belegart>/<JJJJ-MM>/<Datei>. Liegt dort schon eine
 * Datei gleichen Namens: Belege nur nach Rückfrage ersetzen, sonst daneben als
 * „… (1).pdf"; Exporte immer daneben. Liefert den Pfad für den Toast.
 */
async function ablegen(wurzel: Ordner, angaben: BelegAngaben, dateiname: string, blob: Blob): Promise<string> {
  const ablage = belegablage(angaben.art, angaben.datum, dateiname);
  let ordner: FileSystemDirectoryHandle = wurzel;
  for (const teil of ablage.ordner) {
    ordner = await ordner.getDirectoryHandle(teil, { create: true });
  }

  let datei = ablage.datei;
  if (await vorhanden(ordner, datei)) {
    let n = 1;
    while (n < 1000 && (await vorhanden(ordner, nameMitZaehler(ablage.datei, n)))) n += 1;
    const daneben = nameMitZaehler(ablage.datei, n);
    const ersetzen = !istExport(angaben.art) && window.confirm(
      `„${ablage.datei}" liegt schon in ${[wurzel.name, ...ablage.ordner].join('/')}.\n\n`
      + `OK: ersetzen\nAbbrechen: daneben als „${daneben}" speichern`,
    );
    if (!ersetzen) datei = daneben;
  }

  const handle = await ordner.getFileHandle(datei, { create: true });
  const strom = await handle.createWritable();
  try {
    await strom.write(blob);
    await strom.close();
  } catch (e) {
    await strom.abort().catch(() => undefined);
    throw e;
  }
  return ablageAnzeige(wurzel.name, ablage, datei);
}

async function vorhanden(ordner: FileSystemDirectoryHandle, name: string): Promise<boolean> {
  try {
    await ordner.getFileHandle(name);
    return true;
  } catch (e) {
    const art = (e as { name?: string })?.name;
    if (art === 'NotFoundError') return false;
    if (art === 'TypeMismatchError') return true; // ein Ordner dieses Namens
    throw e;
  }
}

/**
 * Normaler Download wie bisher die Belege im Belegdialog
 * (_openPdfFromResponse): Link einhängen, klicken, wieder herausnehmen, die
 * URL erst nach 5 s freigeben (Safari, Firefox, Hallen-Tablet). Ohne
 * document.body bzw. setTimeout — nur im vm-Kontext der Node-Prüfungen — wie
 * bisher SEPA, DATEV und Mahnung: losgelöst, sofort freigeben.
 */
function herunterladen(blob: Blob, dateiname: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = dateiname;
  const seite = document.body;
  if (seite) seite.appendChild(a);
  a.click();
  if (seite) a.remove();
  if (typeof setTimeout === 'function') setTimeout(() => window.URL.revokeObjectURL(url), 5000);
  else window.URL.revokeObjectURL(url);
}
