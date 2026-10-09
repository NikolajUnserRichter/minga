"""Schemas der Benutzerverwaltung je Mandant (Paket 4, B8).

Der Mandant kommt nie aus dem Body: ``extra="forbid"`` lehnt ein mitgeschicktes
``tenant_slug`` (oder ``attributes``) mit 422 ab.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

#: Muss mit keycloak_admin.MANDANTEN_ROLLEN übereinstimmen (Test prüft das).
Rolle = Literal["admin", "production_planner", "sales", "accounting", "production_staff"]


class BenutzerResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: Optional[Rolle] = Field(None, description="Höchste App-Rolle nach Rangfolge; None = keine")
    roles: list[Rolle] = []
    enabled: bool
    created_at: Optional[datetime] = None
    is_self: bool = False


class BenutzerListResponse(BaseModel):
    items: list[BenutzerResponse]
    total: int
    #: True im Demo-Mandanten: Anlegen, Ändern und Passwort-Reset lehnt der Server
    #: dort ab; das Frontend blendet die Schreibknöpfe aus (E-M6).
    schreibgeschuetzt: bool = False


class BenutzerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: Rolle

    @field_validator("email")
    @classmethod
    def _nur_ascii(cls, v: str) -> str:
        if not v.isascii():
            raise ValueError("E-Mail-Adresse bitte ohne Umlaute oder Sonderzeichen.")
        return v.lower()


class BenutzerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[Rolle] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def _mindestens_ein_feld(self):
        if all(v is None for v in (self.first_name, self.last_name, self.role, self.enabled)):
            raise ValueError("Keine Änderung angegeben.")
        return self


class BenutzerAngelegtResponse(BenutzerResponse):
    temporary_password: str = Field(..., description="Einmalpasswort — wird nur jetzt angezeigt")


class PasswortZurueckgesetztResponse(BaseModel):
    user: BenutzerResponse
    temporary_password: str = Field(..., description="Einmalpasswort — wird nur jetzt angezeigt")
