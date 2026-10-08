"""Benutzerverwaltung je Mandant (Paket 4, B8).

Nur Rolle ``admin`` (Router-Abhängigkeit ``_deps_admin`` in main.py). Der
Mandant kommt aus dem Host (tenant_middleware) UND aus dem Token-Claim
``tenant_slug``; beide müssen gesetzt und gleich sein. Ein Benutzer eines
anderen Mandanten ist "nicht gefunden" (404), nie "verboten" (403) — sonst
verriete die Antwort, dass es die ID gibt.

Kein Löschen: Benutzer werden deaktiviert (``enabled: false``).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import CurrentUser
from app.api.v1.platform import DEMO_USERS
from app.schemas.user import (
    BenutzerAngelegtResponse, BenutzerCreate, BenutzerListResponse, BenutzerResponse,
    BenutzerUpdate, PasswortZurueckgesetztResponse,
)
from app.services import keycloak_admin as kc
from app.services.demo_reset_service import DEFAULT_DEMO_SLUG
from app.tenancy import get_request_tenant

router = APIRouter(prefix="/users", tags=["Benutzer"])

#: Eigene Logger-Kategorie für den Audit-Trail. WARNING, weil die App kein
#: Logging konfiguriert (uvicorn ohne --log-config): INFO aus app.* verwirft
#: Pythons lastResort-Handler, WARNING landet im Container-Log.
audit_logger = logging.getLogger("app.audit.benutzer")

#: Die Demo hat öffentlich bekannte Logins (platform.py: DEMO_USERS, DEMO_PASSWORD).
#: Keycloak-Änderungen setzt der nächtliche Demo-Reset NICHT zurück (er spielt
#: nur die SQLite-Datei zurück) — ein Besucher könnte sonst Demo-Logins sperren.
DEMO_MANDANT = DEFAULT_DEMO_SLUG
#: E-Mail-Adressen der öffentlichen Demo-Logins, klein geschrieben. Im Mandanten
#: demo zeigt die Liste nur diese Konten (E-M6); ab Task 3 schreiben diese Logins
#: in keinem Mandanten.
DEMO_LOGINS = frozenset(u["email"].lower() for u in DEMO_USERS)


def _mandant(request: Request, user: CurrentUser) -> str:
    """Mandant des Requests. Basic-Auth- und AUTH_DISABLED-Nutzer haben keinen
    tenant_slug im Token und kommen hier nicht durch; ein Token ohne ``sub``
    (Benutzer-ID) auch nicht — sonst griffe der Selbstschutz ins Leere."""
    host_mandant = get_request_tenant(request)
    token_mandant = user.get("tenant_slug")
    if not user.get("id") or not host_mandant or not token_mandant or host_mandant != token_mandant:
        raise HTTPException(
            status_code=403,
            detail="Benutzerverwaltung nur mit einem Keycloak-Login dieses Mandanten.",
        )
    return host_mandant


Mandant = Annotated[str, Depends(_mandant)]


def _audit(aktion: str, mandant: str, user: dict, **felder) -> None:
    zeile = {
        "aktion": aktion,
        "mandant": mandant,
        "von_id": user.get("id"),
        "von_name": user.get("username"),
        "zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **felder,
    }
    audit_logger.warning(
        "[benutzer-audit] %s", json.dumps(zeile, ensure_ascii=False, sort_keys=True, default=str)
    )


def _fehler(e: kc.KeycloakAdminError, mandant: str, user: dict, ziel_id: str | None = None) -> HTTPException:
    if isinstance(e, kc.KeycloakNichtGefunden):
        if e.fremd:
            _audit("FREMDZUGRIFF_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
        return HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if isinstance(e, kc.BenutzerVomSupportVerwaltet):
        _audit("SUPPORTKONTO_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, (kc.KeycloakKonflikt, kc.BenutzerSchutzregel)):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, kc.RolleNichtErlaubt):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, kc.KeycloakNichtErreichbar):
        return HTTPException(status_code=503, detail=f"Benutzerverwaltung derzeit nicht verfügbar: {e}")
    return HTTPException(status_code=502, detail=f"Keycloak hat die Anfrage abgelehnt: {e}")


def _antwort(b: dict, user: dict) -> BenutzerResponse:
    return BenutzerResponse(**b, is_self=(b["id"] == str(user.get("id"))))


def _sichtbar(mandant: str, b: dict) -> bool:
    """Im Demo-Mandanten sieht jeder Besucher die Liste: dort nur die öffentlichen
    Demo-Konten, keine Test- oder Betreiberkonten mit tenant_slug=demo (E-M6)."""
    return mandant != DEMO_MANDANT or (b.get("email") or "").lower() in DEMO_LOGINS


@router.get("", response_model=BenutzerListResponse)
def list_users(mandant: Mandant, user: CurrentUser):
    try:
        benutzer = kc.list_tenant_users(mandant)
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user)
    items = [_antwort(b, user) for b in benutzer if _sichtbar(mandant, b)]
    return BenutzerListResponse(items=items, total=len(items), schreibgeschuetzt=mandant == DEMO_MANDANT)


@router.get("/{user_id}", response_model=BenutzerResponse)
def get_user(user_id: UUID, mandant: Mandant, user: CurrentUser):
    try:
        b = kc.get_tenant_user(mandant, str(user_id))
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, str(user_id))
    if not _sichtbar(mandant, b):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    return _antwort(b, user)


def _ist_demo_login(user: dict) -> bool:
    """Die öffentlichen Demo-Logins schreiben in KEINEM Mandanten — auch nicht, wenn
    ihr tenant_slug verstellt wurde (B8-Plan, Deploy-Gate D5). Benutzername UND E-Mail,
    weil sich die E-Mail je nach Realm-Einstellung selbst ändern lässt."""
    return any((user.get(k) or "").strip().lower() in DEMO_LOGINS for k in ("username", "email"))


def _mandant_schreiben(mandant: Mandant, user: CurrentUser) -> str:
    if mandant == DEMO_MANDANT:
        raise HTTPException(status_code=403, detail="In der Demo können Benutzer nicht geändert werden.")
    if _ist_demo_login(user):
        raise HTTPException(status_code=403, detail="Mit einem Demo-Login können Benutzer nicht geändert werden.")
    return mandant


MandantSchreiben = Annotated[str, Depends(_mandant_schreiben)]


def _email_hash(email: str) -> str:
    """SHA-256 der klein geschriebenen Adresse (E-M7): wiederholtes Abklopfen bleibt
    erkennbar, ohne dass eine womöglich fremde Adresse im Klartext gespeichert wird."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@router.post("", response_model=BenutzerAngelegtResponse, status_code=201)
def create_user(body: BenutzerCreate, mandant: MandantSchreiben, user: CurrentUser, response: Response):
    try:
        b = kc.create_user_for_tenant(
            tenant_slug=mandant, email=body.email, first_name=body.first_name,
            last_name=body.last_name, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        if isinstance(e, kc.KeycloakKonflikt):
            # Die 409 verrät, dass die Adresse irgendwo im Realm existiert, womöglich
            # bei einem anderen Mandanten: festhalten, aber nur als Hash (E-M7).
            _audit("ANLAGE_KONFLIKT", mandant, user, ziel_email_sha256=_email_hash(body.email),
                   grund="E-Mail vergeben")
        raise _fehler(e, mandant, user)
    _audit("BENUTZER_ANGELEGT", mandant, user, ziel_id=b["id"], ziel_email=b["email"], rolle=body.role)
    response.headers["Cache-Control"] = "no-store"
    pw = b.pop("temporary_password")
    return BenutzerAngelegtResponse(**_antwort(b, user).model_dump(), temporary_password=pw)


@router.patch("/{user_id}", response_model=BenutzerResponse)
def update_user(user_id: UUID, body: BenutzerUpdate, mandant: MandantSchreiben, user: CurrentUser):
    try:
        b, aenderungen = kc.update_tenant_user(
            tenant_slug=mandant, user_id=str(user_id), acting_user_id=str(user.get("id")),
            first_name=body.first_name, last_name=body.last_name,
            enabled=body.enabled, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        teil = getattr(e, "teil_aenderungen", None)
        if teil:
            _audit("BENUTZER_TEILWEISE_GEAENDERT", mandant, user, ziel_id=str(user_id),
                   aenderungen=teil, fehler=str(e))
        raise _fehler(e, mandant, user, str(user_id))
    if aenderungen:
        _audit("BENUTZER_GEAENDERT", mandant, user, ziel_id=b["id"], ziel_email=b["email"],
               aenderungen=aenderungen)
    return _antwort(b, user)


@router.post("/{user_id}/reset-password", response_model=PasswortZurueckgesetztResponse)
def reset_password(user_id: UUID, mandant: MandantSchreiben, user: CurrentUser, response: Response):
    try:
        r = kc.reset_tenant_user_password(tenant_slug=mandant, user_id=str(user_id))
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, str(user_id))
    _audit("PASSWORT_ZURUECKGESETZT", mandant, user, ziel_id=r["user"]["id"], ziel_email=r["user"]["email"])
    response.headers["Cache-Control"] = "no-store"
    return PasswortZurueckgesetztResponse(
        user=_antwort(r["user"], user), temporary_password=r["temporary_password"],
    )
