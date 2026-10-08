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
      'Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen. ' +
      'Kein Zugriff auf Rechnungen, Preislisten, Auswertungen und Einstellungen.',
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
      'Preislisten und Auswertungen. Kein Zugriff auf Tagesplan und Produktion.',
    hinweis: 'Darf Rechnungen anlegen, finalisieren und versenden.',
    badge: 'info',
  },
  {
    wert: 'accounting',
    label: 'Buchhaltung',
    beschreibung:
      'Rechnungen, Zahlungen, Mahnungen, DATEV-Export, Preislisten und Auswertungen; ' +
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

export function rollenInfo(rolle: string | null | undefined): RollenInfo | undefined {
  return MANDANTEN_ROLLEN.find((r) => r.wert === rolle);
}
