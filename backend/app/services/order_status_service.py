"""Statuswechsel einer Bestellung — eine Regel für alle Wege.

Bis Oktober 2026 führten drei Wege nach GELIEFERT, jeder mit eigenen Regeln:
- POST /sales/orders/{id}/status prüfte die Übergänge, setzte aber kein
  Lieferdatum,
- PATCH /sales/delivery-notes/{id}/mark-delivered setzte das Lieferdatum,
  umging aber die Übergangsregel (sogar aus ENTWURF) und schrieb kein
  Audit-Log,
- POST /sales/orders/bulk-status prüfte gar nichts, buchte keinen Bestand und
  scheiterte am Ende an seinem eigenen Antwortschema.

Alle drei rufen jetzt `setze_status`. Die Funktion committet nicht — der
Aufrufer committet Status, Lieferdatum, Audit-Log und Bestandsbuchung in
einer Transaktion oder rollt alles zurück.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.order import Order, OrderAuditLog, OrderStatus
from app.services.order_fulfillment_service import deduct_inventory_for_order
from app.services.lieferschein_service import lieferschein_beim_ausliefern
from app.services.invoice_service import InvoiceService
from app.services.invoice_service import entwurf_bezeichnung
from app.models.enums import InvoiceStatus


# IN_PRODUKTION heißt in der Oberfläche "Gepackt" (Entscheidung 08.10.2026).
# Gepackt, aber nicht geliefert, darf storniert werden: Bestand wird erst
# beim Übergang nach GELIEFERT gebucht. Direkt aus ENTWURF nach GELIEFERT
# geht nicht — erst bestätigen.
ERLAUBTE_UEBERGAENGE: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.ENTWURF: (OrderStatus.BESTAETIGT, OrderStatus.STORNIERT),
    OrderStatus.BESTAETIGT: (OrderStatus.IN_PRODUKTION, OrderStatus.GELIEFERT, OrderStatus.STORNIERT),
    OrderStatus.IN_PRODUKTION: (OrderStatus.GELIEFERT, OrderStatus.STORNIERT),
    OrderStatus.GELIEFERT: (OrderStatus.FAKTURIERT,),
    OrderStatus.FAKTURIERT: (),
    OrderStatus.STORNIERT: (),
}

# Gleiche Wörter wie frontend/src/components/ui/statusLabels.ts — Fehlertexte
# landen als Toast beim Anwender und dürfen keine Enum-Werte zeigen.
STATUS_BEZEICHNUNG: dict[OrderStatus, str] = {
    OrderStatus.ENTWURF: "Entwurf",
    OrderStatus.BESTAETIGT: "Bestätigt",
    OrderStatus.IN_PRODUKTION: "Gepackt",
    OrderStatus.GELIEFERT: "Geliefert",
    OrderStatus.FAKTURIERT: "Fakturiert",
    OrderStatus.STORNIERT: "Storniert",
}


class StatuswechselFehler(Exception):
    """Fachlich unzulässig — der Aufrufer antwortet mit 400."""


class BestandsbuchungFehler(Exception):
    """Bestandsabzug beim Übergang nach GELIEFERT gescheitert — Rollback, 500."""


def heute_berlin() -> date:
    """Kalendertag in München. Der Server läuft in UTC; zwischen 0 und 2 Uhr
    wäre date.today() noch der Vortag."""
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def bezeichnung(status: OrderStatus) -> str:
    return STATUS_BEZEICHNUNG.get(status, status.value)


def pruefe_uebergang(alt: OrderStatus, neu: OrderStatus) -> None:
    if neu not in ERLAUBTE_UEBERGAENGE.get(alt, ()):
        raise StatuswechselFehler(
            f"Statuswechsel nicht möglich: {bezeichnung(alt)} → {bezeichnung(neu)}"
        )


def user_uuid(user: Optional[dict]) -> Optional[UUID]:
    """Keycloak liefert eine UUID; Basic-Auth-Nutzer heißen 'basic-auth:<name>'."""
    try:
        return UUID(str(user["id"])) if user and user.get("id") else None
    except ValueError:
        return None


def setze_status(
    db: Session,
    order: Order,
    neu: OrderStatus,
    *,
    user: Optional[dict],
    action: str = "STATUS_CHANGE",
    reason: Optional[str] = None,
    lieferdatum: Optional[date] = None,
) -> None:
    """Prüft den Übergang und setzt den Status — committet NICHT.

    Beim Übergang nach GELIEFERT zusätzlich: tatsächliches Lieferdatum
    (Standard heute, nie in der Zukunft) und Bestandsabzug in derselben
    Transaktion. Jeder Wechsel schreibt genau einen Audit-Log-Eintrag.
    """
    alt = order.status
    if neu == OrderStatus.STORNIERT:
        rechnung = InvoiceService(db).aktive_rechnung_zur_bestellung(order.id)
        if rechnung is not None and rechnung.status == InvoiceStatus.ENTWURF:
            # Ein Entwurf wird verworfen, nicht storniert (Paket 3, Q1)
            raise StatuswechselFehler(
                f"Bestellung steckt in einem {entwurf_bezeichnung(rechnung)} "
                "— erst den Entwurf verwerfen"
            )
        if rechnung is not None:
            raise StatuswechselFehler(
                f"Bestellung ist bereits berechnet ({rechnung.invoice_number}) "
                "— erst die Rechnung stornieren"
            )
    pruefe_uebergang(alt, neu)

    if lieferdatum is not None and neu != OrderStatus.GELIEFERT:
        raise StatuswechselFehler("Ein Lieferdatum gibt es nur beim Wechsel auf Geliefert")

    alte_werte: dict = {"status": alt.value}
    neue_werte: dict = {"status": neu.value}

    if neu == OrderStatus.GELIEFERT:
        tag = lieferdatum or heute_berlin()
        if tag > heute_berlin():
            raise StatuswechselFehler(f"Lieferdatum {tag:%d.%m.%Y} liegt in der Zukunft")
        alte_werte["actual_delivery_date"] = (
            order.actual_delivery_date.isoformat() if order.actual_delivery_date else None
        )
        neue_werte["actual_delivery_date"] = tag.isoformat()
        order.actual_delivery_date = tag

    user_id = user_uuid(user)
    order.status = neu
    order.updated_by = user_id
    order.updated_at = datetime.now(timezone.utc)
    db.add(OrderAuditLog(
        order_id=order.id,
        user_id=user_id,
        user_name=(user or {}).get("username"),
        action=action,
        old_values=alte_werte,
        new_values=neue_werte,
        reason=reason,
    ))

    if neu == OrderStatus.GELIEFERT:
        # Jede gelieferte Bestellung hat einen Lieferschein — Monats- und
        # Sammellauf rechnen über ihn ab (Paket 4, B; G31, X07).
        lieferschein_beim_ausliefern(db, order)
        try:
            deduct_inventory_for_order(db, order, commit=False)
        except Exception as e:  # noqa: BLE001 — jeder Fehler muss zum Rollback führen
            raise BestandsbuchungFehler(str(e)) from e




# Paket 4 (G10, Gernot 08.10.2026): „Gepackt“ und „Ausgeliefert“ im Tagesplan
# bestätigen einen Entwurf im selben Schritt. Gernot erfasst Bestellungen im
# Formular als Entwurf (Prod 09.10.: 4 von 6 Lieferungen); bis Paket 4 standen
# sie im Sortenbedarf, bis jemand sie in der Bestellliste bestätigte.
# ERLAUBTE_UEBERGAENGE bleibt unverändert: der Entwurf geht über `bestaetigen`
# (ENTWURF → BESTAETIGT, eigener Audit-Eintrag CONFIRM), danach gilt
# `setze_status` wie immer. Nur der Tagesplan schickt das Kennzeichen.
MIT_BESTAETIGUNG: dict[OrderStatus, str] = {
    OrderStatus.IN_PRODUKTION: "Beim Packen im Tagesplan bestätigt",
    OrderStatus.GELIEFERT: "Beim Ausliefern im Tagesplan bestätigt",
}


def bestaetigen(
    db: Session,
    order: Order,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
    bestaetigtes_lieferdatum: Optional[date] = None,
) -> None:
    """ENTWURF → BESTAETIGT — der eine Weg zum Bestätigen (POST /confirm und
    der Tagesplan). Committet NICHT.

    Bestätigt wird nur ein Entwurf mit mindestens einer Position. Das
    bestätigte Lieferdatum ist ohne Angabe das gewünschte."""
    if order.status != OrderStatus.ENTWURF:
        raise StatuswechselFehler(
            f"Bestellung hat Status {bezeichnung(order.status)}, kann nicht bestätigt werden"
        )
    if len(order.lines) == 0:
        raise StatuswechselFehler("Bestellung ohne Positionen kann nicht bestätigt werden")
    setze_status(db, order, OrderStatus.BESTAETIGT, user=user, action="CONFIRM", reason=reason)
    order.confirmed_delivery_date = bestaetigtes_lieferdatum or order.requested_delivery_date


def _im_tagesplan_bestaetigbar(order: Order) -> bool:
    """Ein Entwurf wird im Tagesplan nur bis zu seinem Liefertag bestätigt.

    An vergangenen Tagen stehen Entwürfe, die nie bestätigt wurden (Prod
    09.10.2026: 7, darunter die falsch erfasste Bierbichler-Bestellung und
    vier LfA-Abo-Lieferungen). Ein Klick dort würde sie bestätigen und bei
    „Ausgeliefert“ unumkehrbar liefern: aus GELIEFERT führt nur FAKTURIERT
    weiter, Bestand und Leergut wären gebucht. Gilt auch für „Gepackt“, sonst
    führten zwei Klicks (Gepackt, dann Ausgeliefert) zum selben Ergebnis.
    Solche Entwürfe klärt das Büro in der Bestellliste."""
    return order.requested_delivery_date >= heute_berlin()


def im_tagesplan_moeglich(order: Order, ziel: OrderStatus) -> bool:
    """Zeigt der Tagesplan den Knopf für `ziel` (Gepackt, Ausgeliefert)?
    Dieselbe Regel wie setze_status_im_tagesplan."""
    if not order.lines:
        return False
    if order.status == OrderStatus.ENTWURF and ziel in MIT_BESTAETIGUNG:
        return _im_tagesplan_bestaetigbar(order)
    return ziel in ERLAUBTE_UEBERGAENGE.get(order.status, ())


def setze_status_im_tagesplan(
    db: Session,
    order: Order,
    neu: OrderStatus,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
    lieferdatum: Optional[date] = None,
) -> bool:
    """Statuswechsel aus dem Tagesplan. Ein Entwurf wird vor „Gepackt“ bzw.
    „Ausgeliefert“ bestätigt, aber nur bis zu seinem Liefertag; sonst genau
    setze_status. Gibt zurück, ob bestätigt wurde. Committet NICHT —
    scheitert der Wechsel, rollt der Aufrufer die Bestätigung mit zurück."""
    bestaetigt = False
    if order.status == OrderStatus.ENTWURF and neu in MIT_BESTAETIGUNG:
        if not _im_tagesplan_bestaetigbar(order):
            raise StatuswechselFehler(
                f"Entwurf mit Liefertag {order.requested_delivery_date:%d.%m.%Y} liegt in der "
                "Vergangenheit — erst in der Bestellliste bestätigen oder stornieren"
            )
        bestaetigen(db, order, user=user, reason=MIT_BESTAETIGUNG[neu])
        bestaetigt = True
    setze_status(db, order, neu, user=user, reason=reason, lieferdatum=lieferdatum)
    return bestaetigt


def trage_lieferdatum_nach(
    db: Session,
    order: Order,
    tag: date,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
) -> bool:
    """Lieferdatum einer schon gelieferten Bestellung nachtragen — nur wenn es
    fehlt (Altfälle: Status-Endpunkt setzte es vor Oktober 2026 nicht).
    Ein vorhandenes Datum wird nie überschrieben. Committet NICHT."""
    if order.actual_delivery_date:
        return False
    order.actual_delivery_date = tag
    db.add(OrderAuditLog(
        order_id=order.id,
        user_id=user_uuid(user),
        user_name=(user or {}).get("username"),
        action="LIEFERDATUM_NACHGETRAGEN",
        old_values={"actual_delivery_date": None},
        new_values={"actual_delivery_date": tag.isoformat()},
        reason=reason,
    ))
    return True
