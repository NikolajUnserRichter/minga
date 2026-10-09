"""Benutzer-Audit: dauerhafte Spur der Benutzerverwaltung (Paket 4, B8, E-M1).

Jede Audit-Zeile aus app/api/v1/users.py (_audit) steht als WARNING im
Container-Log, und das überlebt keinen Redeploy. Deshalb liegt jede Zeile
zusätzlich hier, in der Datenbank des Mandanten. Kein Fremdschlüssel: Die
Benutzer leben in Keycloak, nicht in dieser Datenbank, und werden nie gelöscht.

Eine vergebene E-Mail-Adresse (ANLAGE_KONFLIKT) steht nur als SHA-256 in
ziel_email_sha256, weil sie einem anderen Mandanten gehören kann (E-M7).
Passwörter stehen nie hier.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.types import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BenutzerAudit(Base):
    __tablename__ = "benutzer_audit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    zeitpunkt: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # BENUTZER_ANGELEGT, ANLAGE_KONFLIKT, ANLAGE_TEILWEISE, BENUTZER_GEAENDERT,
    # BENUTZER_TEILWEISE_GEAENDERT, PASSWORT_ZURUECKGESETZT, FREMDZUGRIFF_ABGEWIESEN,
    # SUPPORTKONTO_ABGEWIESEN
    aktion: Mapped[str] = mapped_column(String(50), nullable=False)
    # Keycloak-ID des Zielbenutzers; fehlt bei ANLAGE_KONFLIKT und bei ANLAGE_TEILWEISE,
    # wenn die ID des angelegten Kontos nicht ermittelt wurde
    ziel_user_id: Mapped[Optional[str]] = mapped_column(String(36))
    ziel_email: Mapped[Optional[str]] = mapped_column(String(255))
    ziel_email_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    # Keycloak-ID (Token-Claim sub) des Admins, der die Aktion ausgelöst hat
    ausgefuehrt_von: Mapped[Optional[str]] = mapped_column(String(255))
    # Übrige Felder der Logzeile: von_name, rolle, aenderungen, fehler, grund, deaktiviert
    details: Mapped[Optional[dict]] = mapped_column(JSON)

    def __repr__(self) -> str:
        return f"<BenutzerAudit({self.aktion}, ziel={self.ziel_user_id})>"
