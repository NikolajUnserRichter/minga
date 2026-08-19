"""
Dienstplan-API — CRUD für Arbeitsschichten und Zusatzaufgaben.

    GET    /staff-shifts?von_datum&bis_datum  → Schichten im Zeitraum
    GET    /staff-shifts/employees            → bekannte Mitarbeiter-Namen (für Vorschläge)
    GET    /staff-shifts/print                → Wochenplan als PDF-Aushang
    POST   /staff-shifts                      → Schicht anlegen
    PATCH  /staff-shifts/{id}                 → Schicht ändern
    DELETE /staff-shifts/{id}                 → Schicht löschen

    GET    /staff-tasks?von_datum&bis_datum   → Zusatzaufgaben im Zeitraum
    POST   /staff-tasks                       → Aufgabe (optional als Serie) anlegen
    PATCH  /staff-tasks/{id}                  → Aufgabe ändern / abhaken
    DELETE /staff-tasks/{id}?serie            → Termin oder Serie ab diesem Termin löschen
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select, distinct

from app.api.deps import DBSession
from app.models.staff import StaffShift, StaffTask
from app.schemas.staff import (
    StaffShiftCreate, StaffShiftUpdate, StaffShiftResponse,
    StaffTaskCreate, StaffTaskUpdate, StaffTaskResponse,
)

router = APIRouter(prefix="/staff-shifts", tags=["Dienstplan"])
tasks_router = APIRouter(prefix="/staff-tasks", tags=["Dienstplan"])

# Obergrenze für ausmaterialisierte Serien — schützt vor Tippfehlern im Enddatum
MAX_SERIE_TERMINE = 120


@router.get("", response_model=list[StaffShiftResponse])
def list_shifts(
    db: DBSession,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
):
    """Listet Schichten (typisch: eine Woche)."""
    query = select(StaffShift).order_by(StaffShift.datum, StaffShift.start_time, StaffShift.employee_name)
    if von_datum:
        query = query.where(StaffShift.datum >= von_datum)
    if bis_datum:
        query = query.where(StaffShift.datum <= bis_datum)
    return db.execute(query).scalars().all()


@router.get("/employees", response_model=list[str])
def list_employees(db: DBSession):
    """Bekannte Mitarbeiter-Namen aus bisherigen Schichten (für Autovervollständigung)."""
    rows = db.execute(
        select(distinct(StaffShift.employee_name)).order_by(StaffShift.employee_name)
    ).scalars().all()
    return list(rows)


@router.get("/print")
def print_shifts(
    db: DBSession,
    von_datum: date = Query(..., description="Erster Tag des Aushangs"),
    bis_datum: date = Query(..., description="Letzter Tag des Aushangs"),
):
    """Wochenplan als PDF — zum Aushängen für die Mitarbeiter.

    Enthält Schichten und Zusatzaufgaben desselben Zeitraums, damit am
    Schwarzen Brett ein Blatt für die ganze Woche hängt.
    """
    if bis_datum < von_datum:
        raise HTTPException(status_code=400, detail="bis_datum liegt vor von_datum")
    if (bis_datum - von_datum).days > 31:
        raise HTTPException(status_code=400, detail="Zeitraum bitte auf maximal 31 Tage begrenzen")

    shifts = db.execute(
        select(StaffShift)
        .where(StaffShift.datum >= von_datum, StaffShift.datum <= bis_datum)
        .order_by(StaffShift.datum, StaffShift.start_time, StaffShift.employee_name)
    ).scalars().all()
    tasks = db.execute(
        select(StaffTask)
        .where(StaffTask.datum >= von_datum, StaffTask.datum <= bis_datum)
        .order_by(StaffTask.datum, StaffTask.titel)
    ).scalars().all()

    from app.services.dienstplan_pdf import generate_dienstplan_pdf
    from app.services.pdf_service import load_company_settings

    pdf = generate_dienstplan_pdf(
        shifts=list(shifts),
        tasks=list(tasks),
        von_datum=von_datum,
        bis_datum=bis_datum,
        settings=load_company_settings(db),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=Dienstplan_{von_datum:%Y-%m-%d}.pdf"},
    )


@router.post("", response_model=StaffShiftResponse, status_code=201)
def create_shift(data: StaffShiftCreate, db: DBSession):
    shift = StaffShift(**data.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.patch("/{shift_id}", response_model=StaffShiftResponse)
def update_shift(shift_id: UUID, data: StaffShiftUpdate, db: DBSession):
    shift = db.get(StaffShift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Schicht nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shift, field, value)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: UUID, db: DBSession):
    shift = db.get(StaffShift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Schicht nicht gefunden")
    db.delete(shift)
    db.commit()


# ============== Zusatzaufgaben ==============

@tasks_router.get("", response_model=list[StaffTaskResponse])
def list_tasks(
    db: DBSession,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
    employee_name: Optional[str] = None,
    nur_offen: bool = False,
):
    """Zusatzaufgaben im Zeitraum (Kistenspülen, Reinigen, Müllabholung …)."""
    query = select(StaffTask).order_by(StaffTask.datum, StaffTask.titel)
    if von_datum:
        query = query.where(StaffTask.datum >= von_datum)
    if bis_datum:
        query = query.where(StaffTask.datum <= bis_datum)
    if employee_name:
        query = query.where(StaffTask.employee_name == employee_name)
    if nur_offen:
        query = query.where(StaffTask.erledigt == False)  # noqa: E712
    return db.execute(query).scalars().all()


@tasks_router.post("", response_model=list[StaffTaskResponse], status_code=201)
def create_task(data: StaffTaskCreate, db: DBSession):
    """Aufgabe anlegen — optional als Serie.

    Serien werden sofort in einzelne Termine aufgelöst: der Müllabholplan
    steht damit an jedem betroffenen Tag im Tagesplan und lässt sich pro
    Termin abhaken. Rückgabe ist immer eine Liste der angelegten Termine.
    """
    payload = data.model_dump(exclude={"wiederholung", "wiederholung_bis"})

    if not data.wiederholung:
        task = StaffTask(**payload)
        db.add(task)
        db.commit()
        db.refresh(task)
        return [task]

    schritt = timedelta(days=1 if data.wiederholung == "TAEGLICH" else 7)
    ende = data.wiederholung_bis or (data.datum + timedelta(weeks=8))
    if ende < data.datum:
        raise HTTPException(status_code=400, detail="wiederholung_bis liegt vor dem Startdatum")

    serie_id = uuid.uuid4()
    tasks: list[StaffTask] = []
    tag = data.datum
    while tag <= ende and len(tasks) < MAX_SERIE_TERMINE:
        tasks.append(StaffTask(**{**payload, "datum": tag}, serie_id=serie_id))
        tag += schritt

    db.add_all(tasks)
    db.commit()
    for task in tasks:
        db.refresh(task)
    return tasks


@tasks_router.patch("/{task_id}", response_model=StaffTaskResponse)
def update_task(task_id: UUID, data: StaffTaskUpdate, db: DBSession):
    """Aufgabe ändern oder abhaken — `erledigt` setzt den Zeitstempel mit."""
    task = db.get(StaffTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")

    update = data.model_dump(exclude_unset=True)
    if "erledigt" in update:
        task.erledigt_am = datetime.now(timezone.utc) if update["erledigt"] else None
    for field, value in update.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@tasks_router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    db: DBSession,
    serie: bool = Query(False, description="Auch alle späteren Termine derselben Serie löschen"),
):
    """Einen Termin löschen — mit `serie=true` diesen und alle folgenden.

    Frühere Termine der Serie bleiben stehen: sie sind bereits Historie.
    """
    task = db.get(StaffTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")

    if serie and task.serie_id:
        folge = db.execute(
            select(StaffTask).where(
                StaffTask.serie_id == task.serie_id,
                StaffTask.datum >= task.datum,
            )
        ).scalars().all()
        for t in folge:
            db.delete(t)
    else:
        db.delete(task)
    db.commit()
