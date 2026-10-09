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
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DBSession
from app.api.v1.platform import DEMO_USERS
from app.models.benutzer_audit import BenutzerAudit
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


def _mandant(request: Request, user: CurrentUser, db: DBSession) -> str:
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
    try:
        request.state.benutzerverwaltung_aufrufer = kc.pruefe_aktuellen_admin(host_mandant, str(user["id"]))
    except (kc.KeycloakNichtGefunden, kc.ZugangGeaendert) as fehler:
        _audit(db, "ZUGANG_GEAENDERT_ABGEWIESEN", host_mandant, user)
        raise HTTPException(status_code=403, detail="Ihr Zugang wurde geändert — bitte neu anmelden.") from fehler
    except kc.KeycloakAdminError as fehler:
        raise _fehler(fehler, host_mandant, user, db) from fehler
    return host_mandant


Mandant = Annotated[str, Depends(_mandant)]


#: Antwort, wenn die Audit-Zeile nicht in die Mandanten-DB kommt (Task 6b, E-M1).
AUDIT_NICHT_GESPEICHERT = (
    "Die Aktion konnte nicht protokolliert werden. Eine Änderung in Keycloak kann trotzdem "
    "ausgeführt sein — bitte die Liste neu laden und den Support informieren."
)
#: Felder der Audit-Zeile mit eigener Spalte in benutzer_audit. Alle übrigen außer
#: aktion, mandant und zeit landen in details.
_AUDIT_SPALTEN = {
    "von_id": "ausgefuehrt_von",
    "ziel_id": "ziel_user_id",
    "ziel_email": "ziel_email",
    "ziel_email_sha256": "ziel_email_sha256",
}


def _audit(db: Session, aktion: str, mandant: str, user: dict, **felder) -> None:
    """Audit-Zeile als WARNING ins Container-Log (wie bisher) UND dauerhaft in die
    Tabelle benutzer_audit der Mandanten-DB (E-M1).

    Die Logzeile kommt zuerst; sie steht auch dann im Log, wenn die Datenbank
    streikt. Scheitert das Speichern, antwortet die API mit 500 statt mit einem
    Erfolg: Keine Benutzeraktion gilt als erledigt, ohne dass sie dauerhaft
    protokolliert ist. Keycloak und Mandanten-DB haben keine gemeinsame
    Transaktion — die Keycloak-Änderung davor ist dann schon geschehen, bei
    Anlage und Passwort-Reset geht das Einmalpasswort verloren (neuer Reset hilft).
    """
    jetzt = datetime.now(timezone.utc)
    zeile = {
        "aktion": aktion,
        "mandant": mandant,
        "von_id": user.get("id"),
        "von_name": user.get("username"),
        "zeit": jetzt.isoformat(timespec="seconds"),
        **felder,
    }
    audit_logger.warning(
        "[benutzer-audit] %s", json.dumps(zeile, ensure_ascii=False, sort_keys=True, default=str)
    )
    spalten = {spalte: (None if zeile.get(feld) is None else str(zeile[feld]))
               for feld, spalte in _AUDIT_SPALTEN.items()}
    details = {k: v for k, v in zeile.items() if k not in ("aktion", "mandant", "zeit", *_AUDIT_SPALTEN)}
    try:
        db.add(BenutzerAudit(zeitpunkt=jetzt, aktion=aktion, details=details or None, **spalten))
        db.commit()
    except Exception as e:
        db.rollback()
        # Nur die Fehlerklasse: Die Meldung der Datenbank enthielte die Werte des Datensatzes.
        audit_logger.error(
            "[benutzer-audit] %s nicht in benutzer_audit gespeichert (%s)", aktion, type(e).__name__
        )
        raise HTTPException(status_code=500, detail=AUDIT_NICHT_GESPEICHERT) from None


def _fehler(e: kc.KeycloakAdminError, mandant: str, user: dict, db: Session,
            ziel_id: str | None = None) -> HTTPException:
    if isinstance(e, kc.KeycloakErgebnisUnbekannt):
        return HTTPException(status_code=503, detail=(
            "Der Ausgang der Änderung ist unbekannt — bitte den Stand des Kontos prüfen, "
            "bevor Sie die Aktion erneut ausführen."
        ))
    if isinstance(e, kc.KeycloakNichtGefunden):
        if e.fremd:
            _audit(db, "FREMDZUGRIFF_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
        return HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if isinstance(e, kc.BenutzerVomSupportVerwaltet):
        _audit(db, "SUPPORTKONTO_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
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
def list_users(mandant: Mandant, user: CurrentUser, db: DBSession):
    try:
        benutzer = kc.list_tenant_users(mandant)
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, db)
    items = [_antwort(b, user) for b in benutzer if _sichtbar(mandant, b)]
    return BenutzerListResponse(items=items, total=len(items), schreibgeschuetzt=mandant == DEMO_MANDANT)


@router.get("/{user_id}", response_model=BenutzerResponse)
def get_user(user_id: UUID, mandant: Mandant, user: CurrentUser, db: DBSession):
    try:
        b = kc.get_tenant_user(mandant, str(user_id))
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, db, str(user_id))
    if not _sichtbar(mandant, b):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    return _antwort(b, user)


def _ist_demo_login(user: dict) -> bool:
    """Die öffentlichen Demo-Logins schreiben in KEINEM Mandanten — auch nicht, wenn
    ihr tenant_slug verstellt wurde (B8-Plan, Deploy-Gate D5). Benutzername UND E-Mail,
    weil sich die E-Mail je nach Realm-Einstellung selbst ändern lässt."""
    return any((user.get(k) or "").strip().lower() in DEMO_LOGINS for k in ("username", "email"))


def _mandant_schreiben(request: Request, mandant: Mandant, user: CurrentUser) -> str:
    if mandant == DEMO_MANDANT:
        raise HTTPException(status_code=403, detail="In der Demo können Benutzer nicht geändert werden.")
    if _ist_demo_login(user) or _ist_demo_login(request.state.benutzerverwaltung_aufrufer):
        raise HTTPException(status_code=403, detail="Mit einem Demo-Login können Benutzer nicht geändert werden.")
    return mandant


MandantSchreiben = Annotated[str, Depends(_mandant_schreiben)]

#: Schreibbremse je Mandant für Anlegen, Ändern und Passwort-Reset. Die globale
#: Grenze in main.py (Limiter(default_limits=...)) wirkt nicht, weil keine
#: SlowAPIMiddleware eingebunden ist. Zähler im Prozess, also je Worker — wie
#: slowapi ohne storage_uri. Bremst das Abklopfen fremder E-Mail-Adressen (409)
#: und Lastspitzen gegen Keycloak (jede Anlage und jede Änderung ruft es mehrfach).
SCHREIBEN_JE_MINUTE = 30
_schreibzeiten: defaultdict[str, deque] = defaultdict(deque)
_schreib_sperre = threading.Lock()


def _schreibbremse(mandant: MandantSchreiben) -> str:
    jetzt = time.monotonic()
    with _schreib_sperre:
        zeiten = _schreibzeiten[mandant]
        while zeiten and jetzt - zeiten[0] >= 60:
            zeiten.popleft()
        if len(zeiten) >= SCHREIBEN_JE_MINUTE:
            raise HTTPException(
                status_code=429,
                detail="Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen.",
            )
        zeiten.append(jetzt)
    return mandant


MandantSchreibenGebremst = Annotated[str, Depends(_schreibbremse)]


def _email_hash(email: str) -> str:
    """SHA-256 der klein geschriebenen Adresse (E-M7): wiederholtes Abklopfen bleibt
    erkennbar, ohne dass eine womöglich fremde Adresse im Klartext gespeichert wird."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@router.post("", response_model=BenutzerAngelegtResponse, status_code=201)
def create_user(body: BenutzerCreate, mandant: MandantSchreibenGebremst, user: CurrentUser,
                response: Response, db: DBSession):
    try:
        b = kc.create_user_for_tenant(
            tenant_slug=mandant, email=body.email, first_name=body.first_name,
            last_name=body.last_name, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        if isinstance(e, kc.KeycloakErgebnisUnbekannt):
            _audit(db, "BENUTZER_ANGELEGT", mandant, user,
                   ziel_id=getattr(e, "angelegt", {}).get("ziel_id"), ziel_email=body.email,
                   ergebnis="ERGEBNIS_UNBEKANNT", aenderungen=body.model_dump(),
                   deaktiviert=getattr(e, "angelegt", {}).get("deaktiviert"))
        elif isinstance(e, kc.KeycloakKonflikt):
            # Die 409 verrät, dass die Adresse irgendwo im Realm existiert, womöglich
            # bei einem anderen Mandanten: festhalten, aber nur als Hash (E-M7).
            _audit(db, "ANLAGE_KONFLIKT", mandant, user, ziel_email_sha256=_email_hash(body.email),
                   grund="E-Mail vergeben")
        elif getattr(e, "angelegt", None):
            # Das Konto gibt es in Keycloak (eigener Mandant, gesperrt, wenn möglich), die
            # Anlage ist aber nicht fertig: festhalten, sonst fehlte die Spur (E-M1).
            _audit(db, "ANLAGE_TEILWEISE", mandant, user, **e.angelegt, rolle=body.role, fehler=str(e))
        raise _fehler(e, mandant, user, db)
    _audit(db, "BENUTZER_ANGELEGT", mandant, user, ziel_id=b["id"], ziel_email=b["email"], rolle=body.role)
    response.headers["Cache-Control"] = "no-store"
    pw = b.pop("temporary_password")
    return BenutzerAngelegtResponse(**_antwort(b, user).model_dump(), temporary_password=pw)


@router.patch("/{user_id}", response_model=BenutzerResponse)
def update_user(user_id: UUID, body: BenutzerUpdate, mandant: MandantSchreibenGebremst, user: CurrentUser,
                db: DBSession):
    try:
        b, aenderungen = kc.update_tenant_user(
            tenant_slug=mandant, user_id=str(user_id), acting_user_id=str(user.get("id")),
            first_name=body.first_name, last_name=body.last_name,
            enabled=body.enabled, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        teil = getattr(e, "teil_aenderungen", None)
        if isinstance(e, kc.KeycloakErgebnisUnbekannt):
            _audit(db, "BENUTZER_GEAENDERT", mandant, user, ziel_id=str(user_id),
                   ergebnis="ERGEBNIS_UNBEKANNT", aenderungen=body.model_dump(exclude_none=True),
                   bestaetigte_aenderungen=teil or {})
        elif teil:
            _audit(db, "BENUTZER_TEILWEISE_GEAENDERT", mandant, user, ziel_id=str(user_id),
                   aenderungen=teil, fehler=str(e))
        raise _fehler(e, mandant, user, db, str(user_id))
    if aenderungen:
        _audit(db, "BENUTZER_GEAENDERT", mandant, user, ziel_id=b["id"], ziel_email=b["email"],
               aenderungen=aenderungen)
    return _antwort(b, user)


@router.post("/{user_id}/reset-password", response_model=PasswortZurueckgesetztResponse)
def reset_password(user_id: UUID, mandant: MandantSchreibenGebremst, user: CurrentUser, response: Response,
                   db: DBSession):
    try:
        r = kc.reset_tenant_user_password(tenant_slug=mandant, user_id=str(user_id))
    except kc.KeycloakAdminError as e:
        if isinstance(e, kc.KeycloakErgebnisUnbekannt):
            _audit(db, "PASSWORT_ZURUECKGESETZT", mandant, user, ziel_id=str(user_id),
                   ergebnis="ERGEBNIS_UNBEKANNT", aenderungen={"passwort_zurueckgesetzt": True, "temporary": True})
        raise _fehler(e, mandant, user, db, str(user_id))
    _audit(db, "PASSWORT_ZURUECKGESETZT", mandant, user, ziel_id=r["user"]["id"], ziel_email=r["user"]["email"])
    response.headers["Cache-Control"] = "no-store"
    return PasswortZurueckgesetztResponse(
        user=_antwort(r["user"], user), temporary_password=r["temporary_password"],
    )
