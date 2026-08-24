from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination
from app.models.production import GrowBatch, Harvest, GrowBatchStatus
from app.models.order import Order, OrderLine, OrderStatus
from app.schemas.production import (
    GrowBatchCreate, GrowBatchUpdate, GrowBatchResponse,
    HarvestCreate, HarvestResponse, DashboardSummary
)
from app.services.label_service import LabelService

router = APIRouter(tags=["Produktion"])

# ========================================
# GROW BATCHES
# ========================================

@router.get("/grow-batches", response_model=List[GrowBatchResponse])
def list_grow_batches(
    db: DBSession,
    status: Optional[GrowBatchStatus] = None,
    erntereif: Optional[bool] = None,
):
    """Listet Wachstumschargen."""
    from app.models.seed import SeedBatch
    # Seed mitladen: GrowBatch.seed_name läuft über seed_batch.seed
    query = select(GrowBatch).options(
        joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed)
    ).order_by(desc(GrowBatch.aussaat_datum))
    
    if status:
        query = query.where(GrowBatch.status == status)
        
    if erntereif:
         # Logik für Erntereif: status != GEERNTET/VERLUST und Datum im Fenster
         today = date.today()
         query = query.where(
             GrowBatch.status.in_([GrowBatchStatus.KEIMUNG, GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF]),
             GrowBatch.erwartete_ernte_min <= today,
             # GrowBatch.erwartete_ernte_max >= today # Optional: auch überfällige anzeigen
         )

    batches = db.execute(query).scalars().unique().all()
    return batches

@router.post("/grow-batches", response_model=GrowBatchResponse, status_code=201)
def create_grow_batch(data: GrowBatchCreate, db: DBSession):
    """Erstellt eine neue Wachstumscharge.

    Berechnet das Erntefenster aus den Sortenparametern (Seed) und legt die
    GrowBatch im Status KEIMUNG an.
    """
    from datetime import timedelta
    from app.models.seed import Seed, SeedBatch
    from app.services.seed_mix import NichtGenugSaatgut, mische_charge

    if data.seed_batch_id:
        seed_batch = db.get(SeedBatch, data.seed_batch_id)
        if not seed_batch:
            raise HTTPException(status_code=404, detail="Saatgut-Charge nicht gefunden")
        seed = seed_batch.seed
    else:
        # Mischsorte: die Charge entsteht erst hier, aus dem Bestand der
        # Ausgangssorten. Erst mischen, dann wie gewohnt weiterrechnen.
        seed = db.get(Seed, data.seed_id)
        if not seed:
            raise HTTPException(status_code=404, detail="Saatgut-Sorte nicht gefunden")
        if not seed.is_mix:
            raise HTTPException(
                status_code=400,
                detail=f"'{seed.name}' ist keine Mischsorte — bitte eine Saatgut-Charge wählen.",
            )
        try:
            seed_batch = mische_charge(db, seed, data.tray_anzahl, data.aussaat_datum)
        except NichtGenugSaatgut as fehler:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(fehler))

    if not seed:
        raise HTTPException(status_code=400, detail="Saatgut-Charge hat keine Sorte zugeordnet")

    # Chargen-Abweichung aus dem Aussaat-Formular an der Saatgut-Charge persistieren
    if data.zusatz_tage is not None:
        seed_batch.zusatz_tage = data.zusatz_tage

    # Erntefenster ab Aussaatdatum. Erntefenster-Tage zählen AB AUSSAAT
    # (Keimdauer ist darin enthalten: Keim 3 + Wachstum 3 → Fenster 6/7/8).
    # Welcher Parametersatz gilt — Sorte, Winter oder Charge — entscheidet
    # resolve_growth_params.
    from app.services.growth_params import resolve_growth_params

    params = resolve_growth_params(db, seed, seed_batch)
    erwartete_ernte_min = data.aussaat_datum + timedelta(days=params.erntefenster_min_tage)
    erwartete_ernte_optimal = data.aussaat_datum + timedelta(days=params.erntefenster_optimal_tage)
    erwartete_ernte_max = data.aussaat_datum + timedelta(days=params.erntefenster_max_tage)

    grow_batch = GrowBatch(
        seed_batch_id=seed_batch.id,
        tray_anzahl=data.tray_anzahl,
        aussaat_datum=data.aussaat_datum,
        erwartete_ernte_min=erwartete_ernte_min,
        erwartete_ernte_optimal=erwartete_ernte_optimal,
        erwartete_ernte_max=erwartete_ernte_max,
        # Der Mitarbeiter muss sehen, wann die Keimung endet und die Kiste in
        # den Growroom kommt — sonst nützt ihm der Winter-Satz nichts.
        keimende_datum=data.aussaat_datum + timedelta(days=params.keimdauer_tage),
        parameter_quelle=params.quelle,
        regal_position=data.regal_position,
        notizen=data.notizen,
        status=GrowBatchStatus.KEIMUNG,
    )
    db.add(grow_batch)

    # Capacity-Decrement: erhöht aktuell_belegt für das Regal (Stringmatch auf Capacity.name).
    # Antwortet auf PDF-Hinweis "es ändert sich nichts an der Platz Verfügbarkeit".
    if data.regal_position:
        from app.models.capacity import Capacity, ResourceType
        cap = db.execute(
            select(Capacity).where(
                Capacity.name == data.regal_position,
                Capacity.ressource_typ == ResourceType.REGAL,
            )
        ).scalar_one_or_none()
        if cap:
            cap.aktuell_belegt = (cap.aktuell_belegt or 0) + data.tray_anzahl

    db.commit()
    db.refresh(grow_batch)
    return grow_batch

@router.get("/grow-batches/{batch_id}", response_model=GrowBatchResponse)
def get_grow_batch(batch_id: UUID, db: DBSession):
    """Holt eine Wachstumscharge."""
    batch = db.get(GrowBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    return batch

@router.post("/grow-batches/{batch_id}/status/{status}", response_model=GrowBatchResponse)
def update_grow_batch_status(batch_id: UUID, status: GrowBatchStatus, db: DBSession):
    """Aktualisiert Status."""
    batch = db.get(GrowBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    batch.status = status
    db.commit()
    db.refresh(batch)
    return batch

@router.get("/grow-batches/{batch_id}/label")
def get_grow_batch_label(batch_id: UUID, db: DBSession):
    """Generiert ein PDF-Label für die Charge."""
    from sqlalchemy.orm import joinedload
    from sqlalchemy import select
    from app.models.seed import SeedBatch
    batch = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.id == batch_id)
    ).unique().scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
        
    pdf_content = LabelService.generate_grow_label(batch)

    filename = f"Label_Charge_{batch.id}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )


@router.get("/labels/grow-batches")
def get_aussaat_label_sheet(
    db: DBSession,
    datum: Optional[date] = Query(None, description="Aussaattag, Vorgabe: heute"),
    format: str = Query("avery-48x17", description="Etikettenformat"),
):
    """Etikettenbogen für alle Aussaaten eines Tages — ein Etikett je Tray.

    Beklebt wird jedes Tray, nicht die Charge; gedruckt wird tagesweise für
    alle Sorten auf einmal (Avery Zweckform 48,5 × 16,9 mm, 64 je A4).
    """
    from app.services.label_service import (
        KeineAussaat, UnbekanntesFormat, baue_aussaat_etikettenbogen,
    )

    tag = datum or date.today()
    try:
        pdf_content, filename = baue_aussaat_etikettenbogen(db, tag, format)
    except UnbekanntesFormat as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    except KeineAussaat as fehler:
        raise HTTPException(status_code=404, detail=str(fehler))

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )

# ========================================
# GROWTH TIMELINE EVENTS
# ========================================

from app.models.growth_event import GrowthBatchEvent, GrowthEventType, GROWTH_EVENT_LABELS
from datetime import datetime, timezone
from pydantic import BaseModel, Field as PydField
from typing import Optional as Opt


class GrowthEventCreate(BaseModel):
    event_type: GrowthEventType
    occurred_at: Opt[datetime] = None
    employee_name: Opt[str] = PydField(None, max_length=200)
    notes: Opt[str] = None
    extra: Opt[dict] = None


class GrowthEventResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    grow_batch_id: UUID
    event_type: GrowthEventType
    occurred_at: datetime
    employee_name: Opt[str]
    notes: Opt[str]
    extra: Opt[dict]
    created_at: datetime


@router.get("/grow-batches/{batch_id}/events", response_model=List[GrowthEventResponse])
def list_grow_batch_events(batch_id: UUID, db: DBSession):
    """Listet alle Timeline-Events einer Charge, neueste zuerst."""
    if not db.get(GrowBatch, batch_id):
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    events = db.execute(
        select(GrowthBatchEvent)
        .where(GrowthBatchEvent.grow_batch_id == batch_id)
        .order_by(desc(GrowthBatchEvent.occurred_at))
    ).scalars().all()
    return events


@router.post("/grow-batches/{batch_id}/events", response_model=GrowthEventResponse, status_code=201)
def create_grow_batch_event(batch_id: UUID, data: GrowthEventCreate, db: DBSession):
    """Erfasst ein neues Timeline-Event für eine Charge."""
    if not db.get(GrowBatch, batch_id):
        raise HTTPException(status_code=404, detail="Charge nicht gefunden")
    event = GrowthBatchEvent(
        grow_batch_id=batch_id,
        event_type=data.event_type,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
        employee_name=data.employee_name,
        notes=data.notes,
        extra=data.extra,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/event-types")
def list_event_types():
    """Gibt alle bekannten Event-Typen + deutsche Labels zurück."""
    return [
        {"value": t.value, "label": GROWTH_EVENT_LABELS.get(t.value, t.value)}
        for t in GrowthEventType
    ]


# ========================================
# HARVESTS
# ========================================

@router.get("/harvests", response_model=List[HarvestResponse])
def list_harvests(
    db: DBSession,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
):
    """Listet Ernten."""
    query = select(Harvest).order_by(desc(Harvest.ernte_datum))
    if von_datum:
        query = query.where(Harvest.ernte_datum >= von_datum)
    if bis_datum:
        query = query.where(Harvest.ernte_datum <= bis_datum)
    harvests = db.execute(query).scalars().all()
    return harvests

@router.post("/harvests", response_model=HarvestResponse)
def create_harvest(data: HarvestCreate, db: DBSession):
    """Erfasst eine Ernte und gibt das Regal frei (Capacity-Decrement)."""
    from app.models.capacity import Capacity, ResourceType

    payload = data.model_dump()
    # Formular-Feld "notizen" landet in Harvest.quality_notes
    notizen = payload.pop("notizen", None)
    harvest = Harvest(**payload, quality_notes=notizen)
    db.add(harvest)

    batch = db.get(GrowBatch, data.grow_batch_id)
    if batch and batch.status != GrowBatchStatus.GEERNTET:
        # Markiere Charge als geerntet (vereinfachte Annahme: eine Ernte pro Charge)
        batch.status = GrowBatchStatus.GEERNTET

        # Regal-Kapazität freigeben
        if batch.regal_position:
            cap = db.execute(
                select(Capacity).where(
                    Capacity.name == batch.regal_position,
                    Capacity.ressource_typ == ResourceType.REGAL,
                )
            ).scalar_one_or_none()
            if cap:
                cap.aktuell_belegt = max(0, (cap.aktuell_belegt or 0) - batch.tray_anzahl)

    db.commit()
    db.refresh(harvest)
    return harvest

@router.get("/day-plan")
def get_day_plan(
    db: DBSession,
    target_date: date = Query(..., description="Tag, für den der Arbeitsplan erstellt wird"),
):
    """Tagesplan für Mitarbeiter: Aussaat, Ernte, Verpacken, Ausliefern an einem Tag.

    - aussaat: genehmigte Produktionsvorschläge mit Aussaatdatum = Tag
    - ernte: Chargen, deren Erntefenster den Tag umfasst (nicht geerntet)
    - verpacken: Bestellungen, deren Packtag der Tag ist (Standard: Liefertag - 1)
    - ausliefern: Bestellungen mit Lieferdatum = Tag
    """
    from datetime import timedelta
    from app.models.forecast import ProductionSuggestion, SuggestionStatus
    from app.models.seed import Seed, SeedBatch

    # Aussaat: genehmigte Vorschläge für diesen Tag
    suggestions = db.execute(
        select(ProductionSuggestion, Seed)
        .join(Seed, ProductionSuggestion.seed_id == Seed.id)
        .where(
            ProductionSuggestion.aussaat_datum == target_date,
            ProductionSuggestion.status.in_([SuggestionStatus.GENEHMIGT, SuggestionStatus.VORGESCHLAGEN]),
        )
    ).all()
    aussaat = [{
        "seed_name": seed.name,
        "trays": sug.empfohlene_trays,
        "substrat": seed.substrat,
        "saatgut_gramm": float(seed.saatgut_pro_einheit_gramm or 0) * sug.empfohlene_trays,
        "status": sug.status.value,
    } for sug, seed in suggestions]

    # Bereits angelegte Chargen mit Aussaatdatum = Tag. Ohne diesen Block
    # blieb der Tagesplan leer, sobald jemand die Charge direkt in der
    # Produktion anlegt statt über einen Produktionsvorschlag.
    gesaet = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.aussaat_datum == target_date)
        .order_by(GrowBatch.created_at)
    ).scalars().unique().all()
    for b in gesaet:
        seed_obj = b.seed_batch.seed if b.seed_batch else None
        aussaat.append({
            "seed_name": b.seed_name or "Unbekannt",
            "trays": b.tray_anzahl,
            "substrat": seed_obj.substrat if seed_obj else None,
            "saatgut_gramm": float(getattr(seed_obj, "saatgut_pro_einheit_gramm", 0) or 0) * b.tray_anzahl,
            "status": "ANGELEGT",
            "batch_id": str(b.id),
            "regal_position": b.regal_position,
        })

    # Ernte: Chargen im Erntefenster
    batches = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(
            GrowBatch.status.in_([GrowBatchStatus.KEIMUNG, GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF]),
            GrowBatch.erwartete_ernte_min <= target_date,
            GrowBatch.erwartete_ernte_max >= target_date,
        )
        .order_by(GrowBatch.erwartete_ernte_optimal)
    ).scalars().unique().all()
    ernte = [{
        "batch_id": str(b.id),
        "seed_name": b.seed_name or "Unbekannt",
        "trays": b.tray_anzahl,
        "regal_position": b.regal_position,
        "optimal": b.erwartete_ernte_optimal.isoformat(),
        "ist_optimal_heute": b.erwartete_ernte_optimal == target_date,
    } for b in batches]

    # Verpacken und Ausliefern. Verpackt wird am Vortag der Lieferung, damit der
    # Fahrer die Ware in der Früh abholen kann — abweichende Packtage stehen
    # explizit an der Bestellung (Order.packing_date).
    orders = db.execute(
        select(Order)
        .options(joinedload(Order.lines), joinedload(Order.customer))
        .where(
            or_(
                Order.requested_delivery_date.in_([target_date, target_date + timedelta(days=1)]),
                Order.packing_date == target_date,
            ),
            Order.status.in_([OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION]),
        )
        .order_by(Order.requested_delivery_date)
    ).scalars().unique().all()

    def _order_ref(o: Order) -> dict:
        return {
            "order_number": o.order_number,
            "customer_name": o.customer.name if o.customer else "—",
            "delivery_date": o.requested_delivery_date.isoformat(),
            "packing_date": o.effective_packing_date.isoformat() if o.effective_packing_date else None,
            "packing_date_explizit": o.packing_date is not None,
            "status": "Entwurf" if o.status == OrderStatus.ENTWURF else o.status.value,
            "positionen": len(o.lines),
        }

    verpacken = [_order_ref(o) for o in orders if o.effective_packing_date == target_date]
    ausliefern = [_order_ref(o) for o in orders if o.requested_delivery_date == target_date]

    # Dienst: wer ist an dem Tag eingeteilt (Dienstplan)
    from app.models.staff import StaffShift, StaffTask
    shifts = db.execute(
        select(StaffShift)
        .where(StaffShift.datum == target_date)
        .order_by(StaffShift.start_time, StaffShift.employee_name)
    ).scalars().all()
    dienst = [{
        "employee_name": s.employee_name,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "aufgabe": s.aufgabe,
    } for s in shifts]

    # Zusatzaufgaben ohne Produktionsbezug (Kisten spülen, Hanfmatten, Müll)
    tasks = db.execute(
        select(StaffTask)
        .where(StaffTask.datum == target_date)
        .order_by(StaffTask.titel)
    ).scalars().all()
    aufgaben = [{
        "id": str(t.id),
        "titel": t.titel,
        "beschreibung": t.beschreibung,
        "employee_name": t.employee_name,
        "erledigt": t.erledigt,
    } for t in tasks]

    return {
        "target_date": target_date,
        "aussaat": aussaat,
        "ernte": ernte,
        "verpacken": verpacken,
        "ausliefern": ausliefern,
        "dienst": dienst,
        "aufgaben": aufgaben,
    }


# ========================================
# DASHBOARD
# ========================================

@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: DBSession):
    """Gibt Produktions-Dashboard Metriken."""
    start_of_week = date.today() - timedelta(days=date.today().weekday())
    end_of_week = start_of_week + timedelta(days=6)

    week_filter = Harvest.ernte_datum >= start_of_week
    weekly_harvest_grams = db.scalar(
        select(func.sum(Harvest.menge_gramm)).where(week_filter)
    ) or 0
    weekly_loss_grams = db.scalar(
        select(func.sum(Harvest.verlust_gramm)).where(week_filter)
    ) or 0
    weekly_harvest_stueck = db.scalar(
        select(func.sum(Harvest.menge_stueck)).where(week_filter, Harvest.einheit == "STK")
    ) or 0
    weekly_loss_stueck = db.scalar(
        select(func.sum(Harvest.verlust_stueck)).where(week_filter, Harvest.einheit == "STK")
    ) or 0

    status_counts = {
        status.value: db.scalar(
            select(func.count(GrowBatch.id)).where(GrowBatch.status == status)
        ) or 0
        for status in GrowBatchStatus
    }
    harvest_ready = status_counts[GrowBatchStatus.ERNTEREIF.value]

    return {
        "active_batches": status_counts[GrowBatchStatus.KEIMUNG.value] + status_counts[GrowBatchStatus.WACHSTUM.value],
        "harvest_ready": harvest_ready,
        "weekly_harvest_kg": float(weekly_harvest_grams) / 1000.0,
        "weekly_harvest_stueck": int(weekly_harvest_stueck),
        # Felder, die das Dashboard-Frontend rendert
        "chargen_nach_status": status_counts,
        "erntereife_chargen": harvest_ready,
        "ernten_diese_woche_gramm": float(weekly_harvest_grams),
        "verluste_diese_woche_gramm": float(weekly_loss_grams),
        "ernten_diese_woche_stueck": int(weekly_harvest_stueck),
        "verluste_diese_woche_stueck": int(weekly_loss_stueck),
        "woche": {"start": start_of_week.isoformat(), "ende": end_of_week.isoformat()},
    }


# ========================================
# PACKAGING PLAN
# ========================================

@router.get("/packaging-plan")
def get_packaging_plan(
    db: DBSession,
    target_date: date = Query(..., description="Lieferdatum für das geplant werden soll"),
):
    """
    Erstellt einen Verpackungsplan für einen Pack-Tag.

    Verpackt wird standardmäßig 1 Tag vor Auslieferung (Order.packing_date
    überschreibt das). `items` listet die zu packenden Verkaufsartikel,
    `komponenten` löst Bundles in Sorten auf — der Produktionsmitarbeiter
    braucht die Sortenmengen, um die Kartons zusammenzubauen.
    Entwürfe werden mitgezählt und per Status gekennzeichnet, damit noch
    nicht bestätigte Bestellungen nicht unsichtbar bleiben.
    """
    from datetime import timedelta
    from decimal import Decimal
    from app.models.product import BundleComponent, Product

    # 1. Bestellungen finden, deren Packtag auf den Zieltag fällt
    orders = db.execute(
        select(Order)
        .options(
            joinedload(Order.lines).joinedload(OrderLine.product),
            joinedload(Order.customer),
        )
        .where(
            or_(
                Order.requested_delivery_date.in_([target_date, target_date + timedelta(days=1)]),
                Order.packing_date == target_date,
            ),
            Order.status.in_([OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION])
        )
        .order_by(Order.requested_delivery_date)
    ).scalars().unique().all()
    orders = [o for o in orders if o.effective_packing_date == target_date]

    # 2. Aggregieren
    plan = {}
    komponenten: dict = {}

    # Bundle-Zusammensetzungen einmal vorladen statt pro Position zu queryen
    bundle_ids = {
        line.product_id
        for o in orders for line in o.lines
        if line.product_id and line.product and line.product.is_bundle
    }
    components_by_parent: dict = {}
    if bundle_ids:
        for comp in db.execute(
            select(BundleComponent)
            .options(joinedload(BundleComponent.child_product))
            .where(BundleComponent.parent_product_id.in_(bundle_ids))
            .order_by(BundleComponent.sort_order)
        ).scalars().unique().all():
            components_by_parent.setdefault(comp.parent_product_id, []).append(comp)

    def _add_komponente(product_id, name, menge, quelle: Optional[str]):
        """Sortenbedarf aufsummieren — Bundles zählen wie Einzelverkäufe."""
        key = product_id or name
        entry = komponenten.setdefault(key, {
            "product_id": product_id,
            "product_name": name,
            "total_quantity": Decimal("0"),
            "aus_bundles": [],
        })
        entry["total_quantity"] += Decimal(str(menge))
        if quelle and quelle not in entry["aus_bundles"]:
            entry["aus_bundles"].append(quelle)

    for order in orders:
        for line in order.lines:
            # Key: Product ID oder Name (falls ID fehlt/Legacy)
            key = line.product_id if line.product_id else line.beschreibung
            product_name = line.product.name if line.product else line.beschreibung

            if key not in plan:
                plan[key] = {
                    "product_id": line.product_id,
                    "product_name": product_name,
                    "total_quantity": 0,
                    "unit": line.unit,
                    "orders": []
                }

            # Add Quantity (check unit consistency? Assuming same unit for same product for now)
            plan[key]["total_quantity"] += line.quantity

            # Add Order Reference (customer_name/status: vom Frontend so gerendert)
            plan[key]["orders"].append({
                "order_number": order.order_number,
                "customer_name": order.customer.name if order.customer else "—",
                "quantity": line.quantity,
                "unit": line.unit,
                "delivery_date": order.requested_delivery_date.isoformat(),
                "status": "Entwurf" if order.status == OrderStatus.ENTWURF else order.status.value,
                "same_day": order.requested_delivery_date == target_date,
            })

            # Sortenbedarf: Bundles in ihre Komponenten auflösen, damit der
            # Produktionsmitarbeiter weiß, wieviel er von welcher Sorte braucht.
            product = line.product
            if product and product.is_variable_bundle:
                for sel in (line.variable_bundle_selections or []):
                    child = db.get(Product, UUID(str(sel["product_id"]))) if sel.get("product_id") else None
                    if not child:
                        continue
                    _add_komponente(
                        child.id, child.name,
                        line.quantity * Decimal(str(sel.get("quantity", 1) or 1)),
                        product.name,
                    )
            elif product and product.is_bundle and components_by_parent.get(product.id):
                for comp in components_by_parent[product.id]:
                    child = comp.child_product
                    _add_komponente(
                        comp.child_product_id,
                        child.name if child else str(comp.child_product_id),
                        line.quantity * Decimal(str(comp.quantity or 1)),
                        product.name,
                    )
            else:
                # Einzelartikel zählen mit — sonst stimmt die Sortensumme nicht
                _add_komponente(line.product_id, product_name, line.quantity, None)

    return {
        "target_date": target_date,
        "items": list(plan.values()),
        "komponenten": sorted(komponenten.values(), key=lambda k: k["product_name"]),
    }
