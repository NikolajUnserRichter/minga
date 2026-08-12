"""
Dienstplan-API — CRUD für Arbeitsschichten.

    GET    /staff-shifts?von_datum&bis_datum  → Schichten im Zeitraum
    GET    /staff-shifts/employees            → bekannte Mitarbeiter-Namen (für Vorschläge)
    POST   /staff-shifts                      → Schicht anlegen
    PATCH  /staff-shifts/{id}                 → Schicht ändern
    DELETE /staff-shifts/{id}                 → Schicht löschen
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, distinct

from app.api.deps import DBSession
from app.models.staff import StaffShift
from app.schemas.staff import StaffShiftCreate, StaffShiftUpdate, StaffShiftResponse

router = APIRouter(prefix="/staff-shifts", tags=["Dienstplan"])


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
