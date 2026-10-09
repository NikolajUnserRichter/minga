/**
 * Rollen, die ein Mandanten-Admin in der Benutzerverwaltung vergeben darf.
 *
 * Genau die fünf Realm-Rollen der Rechte-Matrix (backend/app/main.py:
 * Konstanten ADMIN … BUCHHALTUNG, Zuordnung je Router über die _deps_*-Listen).
 * Plattform- und Realm-Rollen gehören nicht hierher; der Server lehnt alles
 * außerhalb dieser Liste ab.
 *
 * Die Beschreibungen fassen die Matrix in Alltagssprache zusammen. Wer die
 * Matrix in main.py ändert, muss diese Texte mitziehen.
 */

export type MandantenRolle =
  | 'admin'
  | 'sales'
  | 'production_planner'
  | 'production_staff'
  | 'accounting';

export interface RollenInfo {
  wert: MandantenRolle;
  label: string;
  beschreibung: string;
  /** Rechte, über die der Admin beim Vergeben stolpern soll. */
  hinweis?: string;
  badge: 'success' | 'info' | 'warning' | 'purple' | 'gray';
}

/** Reihenfolge = Auswahlliste: von wenig zu viel Rechten, Mitarbeiter zuerst. */
export const MANDANTEN_ROLLEN: RollenInfo[] = [
  {
    wert: 'production_staff',
    label: 'Produktion',
    beschreibung:
      'Der Mitarbeiter-Login. Tagesplan, Aussaat, Ernten und Lagerbuchungen; ' +
      'Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen; ' +
      'Kunden anlegen und ändern, ohne Konditionen und ohne Löschen. ' +
      'Kein Zugriff auf Rechnungen, DATEV, Preislisten, Auswertungen und Einstellungen.',
    badge: 'warning',
  },
  {
    wert: 'production_planner',
    label: 'Produktionsplanung',
    beschreibung:
      'Plant die Produktion: Tagesplan, Aussaat, Ernten, Kapazitäten, Dienstplan, ' +
      'Sorten, Lieferanten, Produkte, Einkauf und Prognosen; dazu Bestellungen, Auftragsbestätigungen und Lieferscheine. ' +
      'Kein Zugriff auf Rechnungen, Preislisten und Auswertungen.',
    badge: 'success',
  },
  {
    wert: 'sales',
    label: 'Vertrieb',
    beschreibung:
      'Kunden, Bestellungen, Abos, Auftragsbestätigungen, Lieferscheine, Produkte, ' +
      'Preislisten, Auswertungen und Belegstatus. Kein Zugriff auf Tagesplan und Produktion.',
    hinweis: 'Darf Rechnungen anlegen, finalisieren und versenden.',
    badge: 'info',
  },
  {
    wert: 'accounting',
    label: 'Buchhaltung',
    beschreibung:
      'Rechnungen, Belegstatus, Zahlungen, Mahnungen, DATEV-Export, Preislisten und Auswertungen; ' +
      'dazu Kunden, Bestellungen und Belege. Kein Zugriff auf Tagesplan und Produktion.',
    hinweis: 'Darf Rechnungen anlegen, finalisieren und versenden.',
    badge: 'gray',
  },
  {
    wert: 'admin',
    label: 'Administrator',
    beschreibung:
      'Alle Bereiche, zusätzlich Einstellungen, Belegvorlagen, Integrationen und diese Benutzerverwaltung.',
    hinweis: 'Kann selbst Benutzer anlegen, Rollen vergeben und Konten deaktivieren.',
    badge: 'purple',
  },
];

/*
 * Rollengruppen wie im Backend (backend/app/core/rollen.py; Gegenprüfung:
 * frontend/tests/unit/rollen.check.ts). Die Rollen kommen klein geschrieben
 * aus dem Token (useAuth().user.roles).
 */
/** Alle außer der Halle: sehen Kundenkonditionen und Sonderpreise, löschen Adressen und Ansprechpartner. */
export const ROLLEN_OHNE_HALLE: readonly MandantenRolle[] = ['admin', 'sales', 'accounting', 'production_planner'];
/** Kaufmännisch: ändern Konditionen, deaktivieren und reaktivieren Kunden. */
export const KAUFMAENNISCHE_ROLLEN: readonly MandantenRolle[] = ['admin', 'sales', 'accounting'];
/**
 * Konditionen eines Kunden (Backend: KUNDENFELDER_KAUFMAENNISCH). Die Halle
 * bekommt sie als null (P4-D.2) und schickt sie beim Speichern nicht mit:
 * Aus null machte das Formular seine Vorgaben, und der Server lehnte ab.
 */
export const KUNDEN_KONDITIONSFELDER = [
  'payment_terms', 'credit_limit', 'price_list_id', 'discount_percent', 'skonto_percent',
  'skonto_days', 'packaging_fee_amount', 'packaging_fee_percent', 'datev_account',
  'pfand_abrechnung', 'invoice_mode',
] as const;

/** Hat das Login (Rollen aus dem Token) mindestens eine der gesuchten Rollen? */
export function hatEineRolle(rollen: readonly string[] | undefined, gesucht: readonly string[]): boolean {
  return !!rollen?.some((r) => gesucht.includes(r));
}

/** Kopie der Kundendaten ohne die Konditionsfelder (Kundenformular der Halle, P4-D.3). */
export function ohneKonditionen<T extends object>(daten: T): Partial<T> {
  const konditionen: readonly string[] = KUNDEN_KONDITIONSFELDER;
  return Object.fromEntries(
    Object.entries(daten).filter(([feld]) => !konditionen.includes(feld)),
  ) as Partial<T>;
}

export function rollenInfo(rolle: string | null | undefined): RollenInfo | undefined {
  return MANDANTEN_ROLLEN.find((r) => r.wert === rolle);
}
