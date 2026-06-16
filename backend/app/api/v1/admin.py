"""Admin-Endpoints: Runtime-Settings (SMTP etc.) + Test-Aktionen.

Workflow:
    GET  /admin/settings              → Alle bekannten Settings inkl. Werte
                                         (Secrets sind als "***" maskiert)
    PATCH /admin/settings             → Bulk-Update {key: value, ...}
    POST /admin/test-email            → Test-Mail an angegebene Adresse

Auth: keine zusätzliche Permission-Check — Auth-Layer (Basic-Auth oder
Keycloak) reicht für den Demo. Späterer Schritt: Role-Check (Admin only).
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import DBSession
from app.services.settings_service import KNOWN_SETTINGS, get_setting, set_setting
from app.services.email_service import send_email, EmailNotConfiguredError

router = APIRouter(prefix="/admin", tags=["Admin"])


class SettingResponse(BaseModel):
    key: str
    label: str
    is_secret: bool
    has_value: bool             # ob ein Wert (DB oder env) gesetzt ist
    value: Optional[str] = None  # bei is_secret: None oder "***"; sonst der echte Wert
    source: str                  # "db" | "env" | "none"


@router.get("/settings", response_model=list[SettingResponse])
def list_settings(db: DBSession):
    """Liste aller bekannten Settings + aktuelle Werte (Secrets maskiert)."""
    out: list[SettingResponse] = []
    for key, meta in KNOWN_SETTINGS.items():
        db_val = get_setting(db, key, env_fallback=False)
        env_val = os.getenv(key)
        if db_val is not None:
            source, has_value = "db", True
        elif env_val is not None:
            source, has_value = "env", True
        else:
            source, has_value = "none", False
        if meta["is_secret"]:
            display = "***" if has_value else None
        else:
            display = db_val if db_val is not None else env_val
        out.append(SettingResponse(
            key=key,
            label=meta["label"],
            is_secret=meta["is_secret"],
            has_value=has_value,
            value=display,
            source=source,
        ))
    return out


@router.patch("/settings")
def update_settings(db: DBSession, updates: dict[str, Optional[str]] = Body(...)):
    """Bulk-Update. Leerer String oder None → löscht den DB-Eintrag (Fallback
    auf env-Var wirkt dann wieder). Bei Secrets darf "***" gesendet werden
    um den Wert unverändert zu lassen."""
    changed = 0
    for key, raw_value in updates.items():
        if key not in KNOWN_SETTINGS:
            raise HTTPException(status_code=400, detail=f"Unbekannter Setting-Key: {key}")
        # "***" bei Secrets = no-op (Wert behalten)
        if KNOWN_SETTINGS[key]["is_secret"] and raw_value == "***":
            continue
        # Empty/None löscht (lässt env-Fallback durchscheinen)
        if raw_value is None or raw_value == "":
            from app.models.app_setting import AppSetting
            existing = db.get(AppSetting, key)
            if existing:
                db.delete(existing)
                changed += 1
            continue
        set_setting(db, key, raw_value)
        changed += 1
    db.commit()
    return {"changed": changed}


@router.post("/test-email")
def send_test_email(db: DBSession, to: str = Query(..., description="Empfänger der Test-Mail")):
    """Versendet eine Test-Mail mit den aktuellen SMTP-Settings."""
    try:
        send_email(
            db=db,
            to=to,
            subject="Minga-Greens — SMTP-Test",
            body=(
                "Hallo,\n\n"
                "dies ist eine Test-Mail aus dem Minga-Greens-ERP.\n"
                "Wenn du diese Nachricht erhältst, sind die SMTP-Einstellungen korrekt.\n\n"
                "Viele Grüße\nMinga-Greens-Backend"
            ),
        )
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP-Test fehlgeschlagen: {e}")
    return {"sent_to": to, "ok": True}


# ============== Scheduler-Debug ==============

@router.get("/scheduler/jobs")
def list_scheduled_jobs():
    """Liefert die aktuell geplanten Hintergrund-Jobs + nächste Fire-Time."""
    from app.services.scheduler_service import get_jobs
    return {"jobs": get_jobs()}


@router.post("/scheduler/run/{job_id}")
def run_scheduled_job_now(job_id: str):
    """Triggert einen geplanten Job einmalig sofort (für Admin-UI / Test)."""
    from app.services.scheduler_service import _scheduler  # type: ignore
    if _scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler ist nicht aktiv")
    job = _scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' nicht gefunden")
    try:
        job.func()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job-Ausführung fehlgeschlagen: {e}")
    return {"job_id": job_id, "status": "ok"}
