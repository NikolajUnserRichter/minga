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
        try:
            deduct_inventory_for_order(db, order, commit=False)
        except Exception as e:  # noqa: BLE001 — jeder Fehler muss zum Rollback führen
            raise BestandsbuchungFehler(str(e)) from e




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
