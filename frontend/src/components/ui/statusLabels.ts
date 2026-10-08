import type { OrderStatus } from '../../types';

/**
 * Anzeigenamen für Status-Werte. Das Backend liefert immer den Enum-Wert
 * (z. B. IN_PRODUKTION); übersetzt wird ausschließlich hier. Die Wörter
 * für Bestellungen stehen gleichlautend in
 * backend/app/services/order_status_service.py (STATUS_BEZEICHNUNG).
 *
 * IN_PRODUKTION heißt in der Oberfläche „Gepackt" (Entscheidung 08.10.2026).
 */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  ENTWURF: 'Entwurf',
  BESTAETIGT: 'Bestätigt',
  IN_PRODUKTION: 'Gepackt',
  GELIEFERT: 'Geliefert',
  FAKTURIERT: 'Fakturiert',
  STORNIERT: 'Storniert',
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status as OrderStatus] ?? status;
}

// Auftragsbestätigung (ENTWURF/VERSENDET), Lieferschein (ENTWURF/AUSGESTELLT/
// GELIEFERT) und Rechnung (InvoiceStatus) teilen sich die Wörter.
const BELEG_STATUS_LABELS: Record<string, string> = {
  ENTWURF: 'Entwurf',
  VERSENDET: 'Versendet',
  AUSGESTELLT: 'Ausgestellt',
  GELIEFERT: 'Geliefert',
  OFFEN: 'Offen',
  TEILBEZAHLT: 'Teilbezahlt',
  BEZAHLT: 'Bezahlt',
  UEBERFAELLIG: 'Überfällig',
  STORNIERT: 'Storniert',
  MAHNVERFAHREN: 'Im Mahnverfahren',
};

export function belegStatusLabel(status: string): string {
  return BELEG_STATUS_LABELS[status] ?? status;
}

// Tagesplan „Aussaat": Vorschlagsstatus oder eine bereits angelegte Charge
// (backend/app/api/v1/production.py get_day_plan, "status": "ANGELEGT").
const AUSSAAT_STATUS_LABELS: Record<string, string> = {
  VORGESCHLAGEN: 'Vorgeschlagen',
  GENEHMIGT: 'Genehmigt',
  ANGELEGT: 'Angelegt',
};

export function aussaatStatusLabel(status: string): string {
  return AUSSAAT_STATUS_LABELS[status] ?? status;
}

// lexoffice meldet eigene, englische Belegstatus.
const LEXOFFICE_STATUS_LABELS: Record<string, string> = {
  draft: 'Entwurf',
  open: 'Offen',
  overdue: 'Überfällig',
  paid: 'Bezahlt',
  paidoff: 'Bezahlt',
  voided: 'Storniert',
};

export function lexofficeStatusLabel(status: string): string {
  return LEXOFFICE_STATUS_LABELS[status] ?? status;
}

// Warnungen an Produktionsvorschlägen (backend/app/models/forecast.py
// WarningType). "UNBEKANNT" setzt forecasting.py, wenn der Typ fehlt.
const WARNUNG_TYP_LABELS: Record<string, string> = {
  UNTERDECKUNG: 'Unterdeckung',
  UEBERPRODUKTION: 'Überproduktion',
  KAPAZITAET: 'Kapazität',
  SAATGUT_NIEDRIG: 'Saatgut knapp',
  UNBEKANNT: 'Warnung',
};

export function warnungTypLabel(typ: string): string {
  return WARNUNG_TYP_LABELS[typ] ?? typ;
}
