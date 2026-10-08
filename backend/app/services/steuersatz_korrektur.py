"""Einmalige Datenkorrektur: Steuersatz offener Bestellpositionen (A3, 08.10.2026).

Bis zu diesem Release setzte das Bestellformular jede Position fest auf 7 %.
Offene Bestellungen tragen deshalb für Pfandkisten (Produktstamm 19 %) den
falschen Satz — und mit ihm falsche line_vat/line_gross und Bestellsummen.

Korrigiert werden nur Positionen mit Produkt (direkt oder über die Variante),
deren Satz vom Produktstamm abweicht, und nur in Bestellungen, die noch nicht
abgerechnet sind:
- Status ENTWURF, BESTAETIGT, IN_PRODUKTION oder GELIEFERT,
- keine nicht-stornierte Rechnung mit dieser order_id (auch kein Entwurf),
- kein Lieferschein der Bestellung steckt in einer Sammelrechnung,
- orders.invoice_id ist leer.
Rechnungen werden nie angefasst: ihr PDF wird bei jedem Abruf aus der
Datenbank erzeugt, eine Änderung schriebe versendete Belege um (GoBD).

Jede geänderte Bestellung bekommt einen Audit-Log-Eintrag
STEUERSATZ_KORREKTUR mit altem und neuem Stand.

`korrektur_einmalig_ausfuehren` läuft aus tenancy._auto_migrate und setzt
danach einen Marker in app_settings, damit die Korrektur je Mandant genau
einmal läuft. `korrigiere_offene_bestellpositionen` ist zusätzlich gezielt
aufrufbar (nur_bestellungen), z. B. nach dem Storno einer betroffenen
Rechnung, bevor die Bestellung neu fakturiert wird.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.documents import DeliveryNote
from app.models.enums import InvoiceStatus, OrderStatus
from app.models.invoice import Invoice
from app.models.order import Order, OrderAuditLog
from app.services.steuersatz import produkt_der_position

logger = logging.getLogger(__name__)

MARKER = "DATENKORREKTUR_STEUERSATZ_261008"

OFFENE_STATUS = (
    OrderStatus.ENTWURF,
    OrderStatus.BESTAETIGT,
    OrderStatus.IN_PRODUKTION,
    OrderStatus.GELIEFERT,
)

GRUND = (
    "Datenkorrektur 08.10.2026: Steuersatz aus dem Produktstamm übernommen "
    "(Bestellformular hatte fest 7 % gesetzt)"
)


def korrigiere_offene_bestellpositionen(
    db: Session,
    nur_bestellungen: Optional[Iterable[UUID]] = None,
) -> dict:
    """Gleicht den Satz offener Produktpositionen an den Produktstamm an.

    Idempotent: ein zweiter Lauf findet nichts mehr. Committet nicht.

    Mit nur_bestellungen werden genau diese Bestellungen geprüft. Nicht
    offene (z. B. FAKTURIERT) und unbekannte IDs landen in
    uebersprungen_status, statt still herausgefiltert zu werden — der
    Aufrufer muss sehen, dass nichts geändert wurde.
    """
    # Späte Imports: die Rechenregeln der Bestell-API sind die einzige
    # Wahrheit für line_vat/line_gross und die Bestellsummen — dieselben
    # Funktionen wie beim Ändern einer Position über die Oberfläche.
    from app.api.v1.sales import _calculate_line_amounts, _calculate_order_totals

    mit_rechnung = set(db.execute(
        select(Invoice.order_id).where(
            Invoice.order_id.is_not(None),
            Invoice.status != InvoiceStatus.STORNIERT,
        )
    ).scalars())
    in_sammelrechnung = set(db.execute(
        select(DeliveryNote.order_id).where(DeliveryNote.invoice_id.is_not(None))
    ).scalars())

    gesucht = list(nur_bestellungen) if nur_bestellungen is not None else None
    abfrage = select(Order).order_by(Order.order_number)
    if gesucht is None:
        abfrage = abfrage.where(Order.status.in_(OFFENE_STATUS))
    else:
        # Gezielt: auch nicht offene laden, damit sie gemeldet werden können.
        abfrage = abfrage.where(Order.id.in_(gesucht))
    bestellungen = db.execute(abfrage).scalars().all()

    ergebnis = {
        "bestellungen": 0,
        "positionen": 0,
        "geaendert": [],
        "uebersprungen_mit_rechnung": [],
        "uebersprungen_status": [],
    }

    for order in bestellungen:
        if order.status not in OFFENE_STATUS:
            # Nur beim gezielten Aufruf erreichbar.
            ergebnis["uebersprungen_status"].append(f"{order.order_number} ({order.status.value})")
            continue
        abweichend = []
        for line in order.lines:
            produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
            if produkt is not None and produkt.tax_rate is not None and line.tax_rate != produkt.tax_rate:
                abweichend.append((line, produkt.tax_rate))
        if not abweichend:
            continue

        if order.id in mit_rechnung or order.id in in_sammelrechnung or order.invoice_id is not None:
            ergebnis["uebersprungen_mit_rechnung"].append(order.order_number)
            continue

        vorher = {"total_vat": str(order.total_vat), "total_gross": str(order.total_gross), "positionen": []}
        nachher = {"positionen": []}
        for line, satz in abweichend:
            vorher["positionen"].append({
                "position": line.position, "tax_rate": line.tax_rate.value,
                "line_vat": str(line.line_vat), "line_gross": str(line.line_gross),
            })
            line.tax_rate = satz
            _calculate_line_amounts(line)
            nachher["positionen"].append({
                "position": line.position, "tax_rate": line.tax_rate.value,
                "line_vat": str(line.line_vat), "line_gross": str(line.line_gross),
            })
        _calculate_order_totals(order)
        nachher["total_vat"] = str(order.total_vat)
        nachher["total_gross"] = str(order.total_gross)

        db.add(OrderAuditLog(
            order_id=order.id,
            user_id=None,
            user_name="Datenkorrektur",
            action="STEUERSATZ_KORREKTUR",
            old_values=vorher,
            new_values=nachher,
            reason=GRUND,
        ))
        ergebnis["bestellungen"] += 1
        ergebnis["positionen"] += len(abweichend)
        ergebnis["geaendert"].append(order.order_number)
        logger.info(
            "[steuersatz-korrektur] %s: %d Position(en), brutto %s → %s",
            order.order_number, len(abweichend), vorher["total_gross"], nachher["total_gross"],
        )

    if gesucht is not None:
        gefunden = {o.id for o in bestellungen}
        ergebnis["uebersprungen_status"] += [
            f"{oid} (nicht gefunden)" for oid in gesucht if oid not in gefunden
        ]

    db.flush()
    return ergebnis


def korrektur_einmalig_ausfuehren(db: Session) -> Optional[dict]:
    """Führt die Korrektur aus, falls der Marker noch fehlt. Committet nicht.

    Gibt None zurück, wenn sie in diesem Mandanten schon gelaufen ist.
    """
    if db.get(AppSetting, MARKER) is not None:
        return None
    ergebnis = korrigiere_offene_bestellpositionen(db)
    db.add(AppSetting(key=MARKER, value=json.dumps({
        "ausgefuehrt_am": datetime.now(timezone.utc).isoformat(),
        **ergebnis,
    })))
    db.flush()
    logger.info("[steuersatz-korrektur] einmalig ausgeführt: %s", ergebnis)
    return ergebnis
