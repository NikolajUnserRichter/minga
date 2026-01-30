from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.capacity import ResourceType

# Shared properties
class CapacityBase(BaseModel):
    ressource_typ: ResourceType
    name: Optional[str] = None
    max_kapazitaet: int = Field(..., ge=0, description="Maximale Kapazität")
    aktuell_belegt: int = Field(0, ge=0, description="Aktuell belegte Kapazität")

# Properties to receive on creation
class CapacityCreate(CapacityBase):
    pass

# Properties to receive on update
class CapacityUpdate(BaseModel):
    name: Optional[str] = None
    max_kapazitaet: Optional[int] = Field(None, ge=0)
    aktuell_belegt: Optional[int] = Field(None, ge=0)

# Properties to return to client
class Capacity(CapacityBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    # Computed properties
    verfuegbar: int
    auslastung_prozent: float
    ist_ueberlastet: bool

    class Config:
        from_attributes = True
