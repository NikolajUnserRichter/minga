"""Pydantic-Schemas für den Dienstplan (StaffShift)."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


def _validate_hhmm(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    parts = v.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("Zeit bitte als HH:MM angeben")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Zeit bitte als HH:MM angeben")
    return f"{h:02d}:{m:02d}"


class StaffShiftBase(BaseModel):
    employee_name: str = Field(..., min_length=1, max_length=200, description="Mitarbeiter-Name")
    datum: date = Field(..., description="Arbeitstag")
    start_time: Optional[str] = Field(None, description="Beginn (HH:MM)")
    end_time: Optional[str] = Field(None, description="Ende (HH:MM)")
    aufgabe: Optional[str] = Field(None, max_length=200, description="Aufgabe/Bereich (z.B. Aussaat, Auslieferung)")
    notizen: Optional[str] = None

    _v_start = field_validator("start_time")(_validate_hhmm)
    _v_end = field_validator("end_time")(_validate_hhmm)


class StaffShiftCreate(StaffShiftBase):
    pass


class StaffShiftUpdate(BaseModel):
    employee_name: Optional[str] = Field(None, min_length=1, max_length=200)
    datum: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    aufgabe: Optional[str] = Field(None, max_length=200)
    notizen: Optional[str] = None

    _v_start = field_validator("start_time")(_validate_hhmm)
    _v_end = field_validator("end_time")(_validate_hhmm)


class StaffShiftResponse(StaffShiftBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
