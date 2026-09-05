"""Warenfluss-Reports (AP5) — der Zertifizierungsnachweis aus dem Journal.

Je Sorte (Saatgut) bzw. Artikel (Substrat, Verpackung): Anfangsbestand,
Zugang, Verbrauch, Ausschuss/Sonstiges, Inventurkorrektur, Sollbestand Ende.
Alles wird aus InventoryMovement summiert — auch die importierte Historie,
deren Bewegungen im Drilldown als Import gekennzeichnet sind.

Einheiten: Saatgut-Bewegungen laufen teils in kg (Lager), teils in g
(Historien-Import). Der Report normalisiert Saatgut auf Gramm; Substrat und
Verpackung summieren in ihrer Stückeinheit.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.inventory import (
    InventoryItemType, InventoryMovement, MovementType,
    PackagingInventory, SeedInventory,
)
from app.models.production import GrowBatch
from app.models.seed import Seed, SeedBatch

router = APIRouter(prefix="/reports", tags=["Auswertungen"])

#: Zuordnung Bewegungsart → Reportspalte
_SPALTE_JE_TYP = {
    MovementType.EINGANG: "zugang",
    MovementType.PRODUKTION: "verbrauch",
    MovementType.ERNTE: "zugang",          # bei FERTIGWARE ist Ernte der Zugang
    MovementType.KORREKTUR: "korrektur",
    MovementType.VERLUST: "sonstiges",
    MovementType.AUSGANG: "sonstiges",
    MovementType.RUECKGABE: "sonstiges",
    MovementType.UMLAGERUNG: "sonstiges",  # netto 0, bleibt sichtbar
}


def _in_gramm(quantity: Decimal, unit: Optional[str]) -> Decimal:
    """Saatgut-Normalisierung: kg → g, alles andere gilt als Gramm."""
    if (unit or "").strip().lower() == "kg":
        return quantity * 1000
    return quantity


def _lade_bewegungen(db, material_type: InventoryItemType, bis: date):
    """Alle Bewegungen des Materials bis einschließlich `bis`, mit Zuordnung.

    Die Sorte hängt an der Bewegung entweder über den Bestand
    (seed_inventory → seed) oder — bei importierter Historie und Aussaat —
    über die Charge (grow_batch → seed_batch → seed).
    """
    movements = db.execute(
        select(InventoryMovement)
        .where(
            InventoryMovement.item_type == material_type,
            InventoryMovement.movement_date <= datetime.combine(bis, time.max),
        )
        .order_by(InventoryMovement.movement_date)
    ).scalars().all()

    seed_namen: dict = {}
    if material_type == InventoryItemType.SAATGUT:
        inv_zu_seed = dict(db.execute(
            select(SeedInventory.id, Seed.name).join(Seed, SeedInventory.seed_id == Seed.id)
        ).all())
        batch_zu_seed = dict(db.execute(
            select(GrowBatch.id, Seed.name)
            .join(SeedBatch, GrowBatch.seed_batch_id == SeedBatch.id)
            .join(Seed, SeedBatch.seed_id == Seed.id)
        ).all())
        seed_namen = {"inv": inv_zu_seed, "batch": batch_zu_seed}

    artikel_namen = dict(db.execute(
        select(PackagingInventory.id, PackagingInventory.name)
    ).all())

    def schluessel(m: InventoryMovement) -> Optional[str]:
        if material_type == InventoryItemType.SAATGUT:
            if m.seed_inventory_id and m.seed_inventory_id in seed_namen["inv"]:
                return seed_namen["inv"][m.seed_inventory_id]
            if m.grow_batch_id and m.grow_batch_id in seed_namen["batch"]:
                return seed_namen["batch"][m.grow_batch_id]
            return None
        if m.packaging_id:
            return artikel_namen.get(m.packaging_id)
        return None

    return [(m, schluessel(m)) for m in movements]


def _material_flow(db, material_type: InventoryItemType, von: date, bis: date) -> list[dict]:
    normalisieren = material_type == InventoryItemType.SAATGUT
    zeilen: dict[str, dict] = {}

    for m, key in _lade_bewegungen(db, material_type, bis):
        if key is None:
            key = "(nicht zuordenbar)"
        z = zeilen.setdefault(key, {
            "schluessel": key, "anfangsbestand": Decimal("0"), "zugang": Decimal("0"),
            "verbrauch": Decimal("0"), "sonstiges": Decimal("0"),
            "korrektur": Decimal("0"), "endbestand": Decimal("0"),
        })
        menge = _in_gramm(m.quantity, m.unit) if normalisieren else m.quantity
        if m.movement_date.date() < von:
            z["anfangsbestand"] += menge
        else:
            z[_SPALTE_JE_TYP.get(m.movement_type, "sonstiges")] += menge

    for z in zeilen.values():
        z["endbestand"] = (z["anfangsbestand"] + z["zugang"] + z["verbrauch"]
                           + z["sonstiges"] + z["korrektur"])
    return sorted(zeilen.values(), key=lambda z: z["schluessel"])


def _zeitraum(von: Optional[date], bis: Optional[date]) -> tuple[date, date]:
    """Default laut Anforderung: laufendes Geschäftsjahr (= Kalenderjahr)."""
    heute = date.today()
    return von or heute.replace(month=1, day=1), bis or heute


@router.get("/material-flow")
def material_flow(
    db: DBSession,
    material_type: InventoryItemType = Query(...),
    von: Optional[date] = Query(None),
    bis: Optional[date] = Query(None),
):
    """Warenfluss je Sorte/Artikel im Zeitraum (R5.1–R5.3)."""
    von, bis = _zeitraum(von, bis)
    return {
        "material_type": material_type.value,
        "von": von.isoformat(),
        "bis": bis.isoformat(),
        "zeilen": _material_flow(db, material_type, von, bis),
    }


@router.get("/material-flow/details")
def material_flow_details(
    db: DBSession,
    material_type: InventoryItemType = Query(...),
    von: Optional[date] = Query(None),
    bis: Optional[date] = Query(None),
    schluessel: Optional[str] = Query(None, description="Sorte/Artikel zum Filtern"),
):
    """Drilldown (R5.4): die Einzelbewegungen hinter den Summen, mit Herkunft."""
    von, bis = _zeitraum(von, bis)
    ergebnis = []
    for m, key in _lade_bewegungen(db, material_type, bis):
        if m.movement_date.date() < von:
            continue
        if schluessel and key != schluessel:
            continue
        ergebnis.append({
            "datum": m.movement_date.isoformat(),
            "sorte": key,
            "movement_type": m.movement_type.value,
            "menge": m.quantity,
            "einheit": m.unit,
            "referenz": m.reference_number,
            "grund": m.reason,
            # R5.6: importierte Historie ist als solche gekennzeichnet
            "aus_import": bool(m.reference_number and m.reference_number.startswith("IMPORT:")),
        })
    return ergebnis


_EXPORT_SPALTEN = ["schluessel", "anfangsbestand", "zugang", "verbrauch",
                   "sonstiges", "korrektur", "endbestand"]
_EXPORT_TITEL = ["Sorte/Artikel", "Anfangsbestand", "Zugang", "Verbrauch",
                 "Ausschuss/Sonstiges", "Inventurkorrektur", "Sollbestand Ende"]


@router.get("/material-flow/export")
def material_flow_export(
    db: DBSession,
    material_type: InventoryItemType = Query(...),
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    von: Optional[date] = Query(None),
    bis: Optional[date] = Query(None),
):
    """Export als Auditnachweis (R5.5): CSV für die Tabelle, PDF zum Vorzeigen."""
    von, bis = _zeitraum(von, bis)
    zeilen = _material_flow(db, material_type, von, bis)
    dateiname = f"Warenfluss_{material_type.value}_{von.isoformat()}_{bis.isoformat()}"

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(_EXPORT_TITEL)
        for z in zeilen:
            writer.writerow([z[s] for s in _EXPORT_SPALTEN])
        return Response(
            content=buf.getvalue().encode("utf-8-sig"),  # BOM: Excel öffnet Umlaute korrekt
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={dateiname}.csv"},
        )

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    kopf = (f"Warenfluss {material_type.value} · Zeitraum {von.strftime('%d.%m.%Y')}"
            f"–{bis.strftime('%d.%m.%Y')} · erstellt {date.today().strftime('%d.%m.%Y')}")
    einheit = "Angaben in Gramm" if material_type == InventoryItemType.SAATGUT else "Angaben in Stück"
    daten = [_EXPORT_TITEL] + [[str(z[s]) for s in _EXPORT_SPALTEN] for z in zeilen]
    tabelle = Table(daten, repeatRows=1)
    tabelle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4360")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    doc.build([
        Paragraph("Warenfluss-Nachweis", styles["Title"]),
        Paragraph(kopf, styles["Normal"]),
        Paragraph(einheit, styles["Normal"]),
        Spacer(1, 12),
        tabelle,
    ])
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={dateiname}.pdf"},
    )
