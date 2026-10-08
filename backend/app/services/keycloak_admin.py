"""Keycloak-Admin-Helper: User im Realm provisionieren.

Wird vom Platform-Admin-Flow genutzt, um beim Anlegen eines neuen Tenants
gleich einen Login-User mit dem passenden ``tenant_slug``-Attribut + Rolle
anzulegen — damit "Kunde anlegen" wirklich Zero-Touch ist.

Auth gegen Keycloak: master-Realm-Admin via Env
    KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
Ziel-Realm: KEYCLOAK_REALM (Default: novaerp)
Keycloak-Basis-URL: KEYCLOAK_URL

Benutzerverwaltung je Mandant (unten, /api/v1/users): Realm = settings.keycloak_realm,
also derselbe Realm wie die Token-Prüfung (core/security.py). Zugang NUR über einen
Service-Account im Ziel-Realm (KEYCLOAK_USERS_CLIENT_ID, KEYCLOAK_USERS_CLIENT_SECRET;
Client-Rollen manage-users, view-users, view-realm). Fehlt er, antwortet die
Benutzerverwaltung mit 503. Den master-Admin nutzt sie nie.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import string
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class KeycloakAdminError(Exception):
    pass


# Defense-in-Depth: Slug-Validierung direkt in diesem Modul, damit URLs/Attribute
# nie aus ungeprüftem Input gebaut werden (OAuth-Redirect-URI-Injection / Open-Redirect),
# unabhängig davon ob der Caller bereits validiert hat.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")


def _require_safe_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise KeycloakAdminError(f"Ungültiger Tenant-Slug für Keycloak-Operation: {slug!r}")
    return slug


def _cfg() -> dict:
    url = os.environ.get("KEYCLOAK_URL", "").rstrip("/")
    realm = os.environ.get("KEYCLOAK_REALM", "novaerp")
    admin_user = os.environ.get("KEYCLOAK_ADMIN_USER", "")
    admin_pw = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "")
    if not (url and admin_user and admin_pw):
        raise KeycloakAdminError(
            "Keycloak-Admin nicht konfiguriert (KEYCLOAK_URL/ADMIN_USER/ADMIN_PASSWORD fehlen)."
        )
    return {"url": url, "realm": realm, "admin_user": admin_user, "admin_pw": admin_pw}


def _admin_token(c: dict, client: httpx.Client) -> str:
    r = client.post(
        f"{c['url']}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "username": c["admin_user"],
            "password": c["admin_pw"],
            "grant_type": "password",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if r.status_code != 200:
        raise KeycloakAdminError(f"Admin-Login fehlgeschlagen: HTTP {r.status_code}")
    return r.json()["access_token"]


def _gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length)) + "!A9"


def create_tenant_user(
    *,
    email: str,
    tenant_slug: str,
    role: str = "admin",
    password: Optional[str] = None,
    temporary_password: bool = True,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> dict:
    """Legt einen User im Ziel-Realm an: Email als Username, tenant_slug-Attribut,
    Realm-Rolle, Passwort (generiert falls None).

    Returns: {username, email, tenant_slug, role, password, temporary}
    Raises: KeycloakAdminError
    """
    tenant_slug = _require_safe_slug(tenant_slug)
    c = _cfg()
    realm = c["realm"]
    pw = password or _gen_password()
    # Default-Namen aus der Email ableiten, damit VERIFY_PROFILE den ersten Login
    # nicht blockt (Realm verlangt firstName/lastName).
    local = email.split("@", 1)[0]
    fname = first_name or (local.split(".")[0].capitalize() if local else "Admin")
    lname = last_name or (tenant_slug.replace("-", " ").title())

    with httpx.Client(verify=True) as client:
        token = _admin_token(c, client)
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 1) User anlegen
        resp = client.post(
            f"{c['url']}/admin/realms/{realm}/users",
            headers=h,
            json={
                "username": email,
                "email": email,
                "firstName": fname,
                "lastName": lname,
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
                "attributes": {"tenant_slug": [tenant_slug]},
                "credentials": [
                    {"type": "password", "value": pw, "temporary": temporary_password}
                ],
            },
            timeout=15,
        )
        if resp.status_code == 409:
            raise KeycloakAdminError(f"User '{email}' existiert bereits im Realm.")
        if resp.status_code not in (201, 204):
            raise KeycloakAdminError(f"User-Anlage fehlgeschlagen: HTTP {resp.status_code} {resp.text[:200]}")

        # 2) User-ID holen
        lookup = client.get(
            f"{c['url']}/admin/realms/{realm}/users",
            headers=h,
            params={"username": email, "exact": "true"},
            timeout=15,
        )
        users = lookup.json() if lookup.status_code == 200 else []
        if not users:
            raise KeycloakAdminError("User angelegt, aber Lookup fehlgeschlagen.")
        user_id = users[0]["id"]

        # 3) Realm-Rolle holen + zuweisen
        #
        # Eine fehlende Rolle MUSS hier scheitern. Früher wurde sie still
        # übersprungen: der Aufrufer bekam "angelegt, Rolle production_staff"
        # zurück, im Token stand aber keine. Genau so fehlten production_staff
        # und accounting unbemerkt im Realm — solange niemand Rollen prüfte,
        # bedeutete das sogar Vollzugriff.
        role_resp = client.get(f"{c['url']}/admin/realms/{realm}/roles/{role}", headers=h, timeout=15)
        if role_resp.status_code != 200:
            raise KeycloakAdminError(
                f"Rolle '{role}' gibt es im Realm '{realm}' nicht — '{email}' wurde "
                f"angelegt, hat aber keine Rechte. Rolle in Keycloak anlegen und "
                f"den Aufruf wiederholen."
            )
        zuweisung = client.post(
            f"{c['url']}/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
            headers=h,
            json=[role_resp.json()],
            timeout=15,
        )
        if zuweisung.status_code >= 400:
            raise KeycloakAdminError(
                f"Rolle '{role}' konnte '{email}' nicht zugewiesen werden "
                f"(HTTP {zuweisung.status_code})."
            )

    return {
        "username": email,
        "email": email,
        "tenant_slug": tenant_slug,
        "role": role,
        "password": pw,
        "temporary": temporary_password,
    }


def add_tenant_redirect_uri(slug: str, *, client_id: str = "novaerp-frontend") -> bool:
    """Fügt die konkrete Redirect-URI + Web-Origin eines Tenants zum Frontend-Client.

    Keycloak honoriert Host-Wildcards (*.domain) in Redirect-URIs nicht zuverlässig,
    deshalb wird pro Tenant die exakte URI ergänzt. Idempotent.

    Returns: True wenn etwas hinzugefügt wurde, False wenn schon vorhanden / nicht konfiguriert.
    """
    slug = _require_safe_slug(slug)
    try:
        c = _cfg()
    except KeycloakAdminError:
        return False
    realm = c["realm"]
    # Root-Domain ebenfalls validieren (kommt aus Env, aber defensiv).
    root = os.environ.get("SPROUDDESK_ROOT_DOMAIN", "novaerp.de").strip().lower()
    if not re.match(r"^[a-z0-9.-]+$", root):
        raise KeycloakAdminError(f"Ungültige ROOT_DOMAIN: {root!r}")
    redirect = f"https://{slug}.{root}/*"
    origin = f"https://{slug}.{root}"

    with httpx.Client(verify=True) as client:
        token = _admin_token(c, client)
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Client per clientId finden
        lookup = client.get(
            f"{c['url']}/admin/realms/{realm}/clients",
            headers=h, params={"clientId": client_id}, timeout=15,
        )
        clients = lookup.json() if lookup.status_code == 200 else []
        if not clients:
            return False
        cl = clients[0]
        cid = cl["id"]
        redirects = set(cl.get("redirectUris") or [])
        origins = set(cl.get("webOrigins") or [])
        changed = False
        if redirect not in redirects:
            redirects.add(redirect); changed = True
        if origin not in origins and "+" not in origins:
            origins.add(origin); changed = True
        if not changed:
            return False
        upd = client.put(
            f"{c['url']}/admin/realms/{realm}/clients/{cid}",
            headers=h,
            json={**cl, "redirectUris": sorted(redirects), "webOrigins": sorted(origins)},
            timeout=15,
        )
        return upd.status_code in (200, 204)


def is_configured() -> bool:
    try:
        _cfg()
        return True
    except KeycloakAdminError:
        return False


# ---------------------------------------------------------------------------
# Benutzerverwaltung je Mandant (Paket 4, B8)
#
# Ein Realm für alle Mandanten: getrennt wird NUR über das Attribut
# tenant_slug. Deshalb prüft jede Funktion hier vor jedem Lesen oder
# Schreiben, dass der Zielbenutzer genau diesen tenant_slug trägt. Ein
# Benutzer eines anderen Mandanten ist für den Aufrufer "nicht gefunden".
# ---------------------------------------------------------------------------

#: Rollen, die ein Mandanten-Admin vergeben darf. Reihenfolge = Rangfolge wie
#: ROLLEN_RANGFOLGE in frontend/src/components/common/Layout.tsx.
MANDANTEN_ROLLEN: tuple[str, ...] = (
    "admin", "production_planner", "sales", "accounting", "production_staff",
)

_SEITE = 100
_MAX_SEITEN = 10
#: Token des Service-Accounts, bis kurz vor Ablauf: {(url, realm, client_id): (token, gültig_bis)}.
_token_cache: dict[tuple, tuple[str, float]] = {}
_token_lock = threading.Lock()


class KeycloakNichtErreichbar(KeycloakAdminError):
    """Keycloak antwortet nicht oder mit 5xx, oder der Zugang fehlt bzw. wird abgelehnt."""


class KeycloakNichtGefunden(KeycloakAdminError):
    """Benutzer gibt es nicht — oder er gehört zu einem anderen Mandanten."""

    def __init__(self, fremd: bool = False) -> None:
        super().__init__("Benutzer nicht gefunden.")
        self.fremd = fremd


class KeycloakKonflikt(KeycloakAdminError):
    """E-Mail-Adresse ist im Realm schon vergeben."""


class BenutzerSchutzregel(KeycloakAdminError):
    """Änderung würde den eigenen Zugang sperren oder den Mandanten ohne Admin lassen."""


class BenutzerVomSupportVerwaltet(BenutzerSchutzregel):
    """Konto hat Rechte außerhalb der App-Rollen (Client-Rollen, Gruppen, fremde
    oder zusammengesetzte Realm-Rollen). Ein Mandanten-Admin ändert es nicht."""

    def __init__(self) -> None:
        super().__init__("Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden.")


class RolleNichtErlaubt(KeycloakAdminError):
    """Rolle liegt außerhalb von MANDANTEN_ROLLEN."""


def _http_client() -> httpx.Client:
    """Fabrik für den HTTP-Client. Tests hängen hier einen httpx.MockTransport ein."""
    return httpx.Client(verify=True, timeout=15)


def _require_user_id(user_id: str) -> str:
    """Keycloak-IDs sind UUIDs. Alles andere ist "nicht gefunden", bevor es in
    einen URL-Pfad gelangt — httpx löst '..' auf (/users/../roles/admin wäre
    /roles/admin), '?' finge eine Query an."""
    try:
        return str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise KeycloakNichtGefunden() from None


def _users_cfg() -> dict:
    """Zugang der Benutzerverwaltung.

    Realm = der Realm, gegen den die App Tokens prüft (settings.keycloak_realm,
    core/security.py:69) — nicht der KEYCLOAK_REALM-Default 'novaerp' aus _cfg().
    Sonst verwaltete ein Mandanten-Admin Benutzer in einem anderen Realm als dem,
    aus dem sein Token stammt.

    Ausschließlich ein Service-Account im Ziel-Realm (T5 R5, Risiko 2; E-M16).
    Ohne ihn: 503. Einen Rückfall auf den master-Admin gibt es nicht, auch wenn
    KEYCLOAK_ADMIN_USER/_PASSWORD gesetzt sind (die nutzt nur das Onboarding).
    """
    url = os.environ.get("KEYCLOAK_URL", "").rstrip("/")
    realm = get_settings().keycloak_realm
    svc_id = os.environ.get("KEYCLOAK_USERS_CLIENT_ID", "").strip()
    svc_secret = os.environ.get("KEYCLOAK_USERS_CLIENT_SECRET", "")
    if not url:
        raise KeycloakNichtErreichbar("Benutzerverwaltung ist nicht eingerichtet (KEYCLOAK_URL fehlt).")
    if not (svc_id and svc_secret):
        raise KeycloakNichtErreichbar(
            "Benutzerverwaltung ist nicht eingerichtet "
            "(Service-Account fehlt: KEYCLOAK_USERS_CLIENT_ID/_SECRET)."
        )
    return {"url": url, "realm": realm, "svc_id": svc_id, "svc_secret": svc_secret}


def _neues_token(c: dict, client: httpx.Client) -> tuple[str, float]:
    """Anmeldung des Service-Accounts (client_credentials) im Ziel-Realm.
    Rückgabe: (Token, gültig bis — monotone Uhr, 30 s Puffer)."""
    url = f"{c['url']}/realms/{c['realm']}/protocol/openid-connect/token"
    daten = {"grant_type": "client_credentials",
             "client_id": c["svc_id"], "client_secret": c["svc_secret"]}
    try:
        r = client.post(url, data=daten, headers={"Content-Type": "application/x-www-form-urlencoded"})
    except httpx.TransportError as e:
        raise KeycloakNichtErreichbar("Keycloak ist nicht erreichbar.") from e
    if r.status_code != 200:
        raise KeycloakNichtErreichbar(
            f"Anmeldung der Benutzerverwaltung bei Keycloak abgelehnt (HTTP {r.status_code})."
        )
    antwort = r.json()
    laufzeit = float(antwort.get("expires_in") or 60)
    return antwort["access_token"], time.monotonic() + max(0.0, laufzeit - 30)


def _users_token(c: dict, client: httpx.Client, *, erneuern: bool = False) -> str:
    """Token aus dem Prozess-Cache; neu anmelden erst kurz vor Ablauf."""
    schluessel = (c["url"], c["realm"], c["svc_id"])
    with _token_lock:
        if erneuern:
            _token_cache.pop(schluessel, None)
        eintrag = _token_cache.get(schluessel)
        if eintrag and eintrag[1] > time.monotonic():
            return eintrag[0]
    token, gueltig_bis = _neues_token(c, client)
    with _token_lock:
        _token_cache[schluessel] = (token, gueltig_bis)
    return token


class _Benutzerzugang:
    """Eine Keycloak-Sitzung je API-Aufruf: Client, Token, Basis-URL des Realms."""

    def __init__(self) -> None:
        self.c = _users_cfg()
        self.base = f"{self.c['url']}/admin/realms/{self.c['realm']}"
        self.client = _http_client()
        try:
            self.h = {"Authorization": f"Bearer {_users_token(self.c, self.client)}"}
        except Exception:
            self.client.close()
            raise

    def __enter__(self) -> "_Benutzerzugang":
        return self

    def __exit__(self, *exc) -> None:
        self.client.close()

    def _senden(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            return self.client.request(method, f"{self.base}{path}", headers=self.h, **kw)
        except httpx.TransportError as e:
            raise KeycloakNichtErreichbar("Keycloak ist nicht erreichbar.") from e

    def call(self, method: str, path: str, **kw) -> httpx.Response:
        r = self._senden(method, path, **kw)
        if r.status_code == 401:
            # Token aus dem Cache abgelaufen oder widerrufen: einmal neu anmelden.
            self.h = {"Authorization": f"Bearer {_users_token(self.c, self.client, erneuern=True)}"}
            r = self._senden(method, path, **kw)
        if r.status_code >= 500:
            raise KeycloakNichtErreichbar(f"Keycloak meldet einen Serverfehler (HTTP {r.status_code}).")
        return r


def _gehoert_zum_mandanten(rep: dict, tenant_slug: str) -> bool:
    """Genau ein Wert, genau dieser Mandant. Fehlt das Attribut: fremd."""
    return (rep.get("attributes") or {}).get("tenant_slug") == [tenant_slug]


def _lade_mandanten_user(kc: _Benutzerzugang, user_id: str, tenant_slug: str) -> dict:
    user_id = _require_user_id(user_id)
    r = kc.call("GET", f"/users/{user_id}")
    if r.status_code == 404:
        raise KeycloakNichtGefunden()
    if r.status_code != 200:
        raise KeycloakAdminError(f"Benutzer konnte nicht gelesen werden (HTTP {r.status_code}).")
    rep = r.json()
    if not _gehoert_zum_mandanten(rep, tenant_slug):
        raise KeycloakNichtGefunden(fremd=True)
    return rep


def _rollen_mappings(kc: _Benutzerzugang, user_id: str) -> list[dict]:
    r = kc.call("GET", f"/users/{user_id}/role-mappings/realm")
    if r.status_code != 200:
        raise KeycloakAdminError(f"Rollen konnten nicht gelesen werden (HTTP {r.status_code}).")
    return r.json()


def _app_rollen(kc: _Benutzerzugang, user_id: str) -> list[str]:
    """Direkt zugewiesene App-Rollen, in Rangfolge. Andere Realm-Rollen fallen heraus."""
    namen = {m.get("name") for m in _rollen_mappings(kc, user_id)}
    return [r for r in MANDANTEN_ROLLEN if r in namen]


def _als_benutzer(rep: dict, rollen: list[str]) -> dict:
    ts = rep.get("createdTimestamp")
    return {
        "id": rep["id"],
        "email": rep.get("email") or rep.get("username") or "",
        "first_name": rep.get("firstName") or "",
        "last_name": rep.get("lastName") or "",
        "enabled": bool(rep.get("enabled", False)),
        "roles": rollen,
        "role": rollen[0] if rollen else None,
        "created_at": datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None,
    }


def _mandanten_reps(kc: _Benutzerzugang, tenant_slug: str) -> list[dict]:
    """Alle Benutzer des Mandanten: Keycloak-Attributsuche plus exakter Filter in Python.

    Die q-Suche kann je nach Keycloak-Version auch Teiltreffer liefern
    (q=tenant_slug:minga träfe minga-test). Maßgeblich ist der Python-Filter.
    """
    treffer: list[dict] = []
    first = 0
    for _ in range(_MAX_SEITEN):
        r = kc.call("GET", "/users", params={
            "q": f"tenant_slug:{tenant_slug}",
            "exact": "true",
            "briefRepresentation": "false",
            "first": first,
            "max": _SEITE,
        })
        if r.status_code != 200:
            raise KeycloakAdminError(f"Benutzerliste konnte nicht gelesen werden (HTTP {r.status_code}).")
        seite = r.json()
        treffer.extend(seite)
        if len(seite) < _SEITE:
            break
        first += _SEITE
    else:
        raise KeycloakAdminError("Mehr als 1000 Treffer — Benutzerliste wäre unvollständig.")
    return [u for u in treffer if _gehoert_zum_mandanten(u, tenant_slug)]


def list_tenant_users(tenant_slug: str) -> list[dict]:
    tenant_slug = _require_safe_slug(tenant_slug)
    with _Benutzerzugang() as kc:
        benutzer = [_als_benutzer(u, _app_rollen(kc, u["id"])) for u in _mandanten_reps(kc, tenant_slug)]
    return sorted(benutzer, key=lambda b: (b["last_name"].lower(), b["first_name"].lower(), b["email"]))


def get_tenant_user(tenant_slug: str, user_id: str) -> dict:
    tenant_slug = _require_safe_slug(tenant_slug)
    user_id = _require_user_id(user_id)
    with _Benutzerzugang() as kc:
        rep = _lade_mandanten_user(kc, user_id, tenant_slug)
        return _als_benutzer(rep, _app_rollen(kc, user_id))


_HALB_ANGELEGT = (
    "Benutzer wurde angelegt, die Rolle aber nicht zugewiesen. Er ist deaktiviert; "
    "bitte über „Bearbeiten“ Rolle setzen und aktivieren."
)
_HALB_ANGELEGT_AKTIV = (
    "Benutzer wurde angelegt, die Rolle aber nicht zugewiesen, und er konnte nicht "
    "deaktiviert werden — bitte den Support informieren."
)


def _deaktivieren_best_effort(kc: _Benutzerzugang, user_id: str, username: str) -> bool:
    """Kein Hard-Delete: ein halb angelegter Benutzer wird gesperrt, nicht gelöscht.

    Nur, wenn die ID wirklich zu dem gerade angelegten Benutzernamen gehört —
    sonst träfe ein Fehler bei der ID-Ermittlung einen fremden Benutzer.
    Rückgabe: True, wenn er jetzt deaktiviert ist."""
    try:
        r = kc.call("GET", f"/users/{_require_user_id(user_id)}")
        if r.status_code == 200 and r.json().get("username") == username:
            p = kc.call("PUT", f"/users/{user_id}", json={**r.json(), "enabled": False})
            if p.status_code in (200, 204):
                return True
    except KeycloakAdminError:
        pass
    logger.error("[keycloak] Benutzer %s konnte nach Fehler nicht deaktiviert werden", user_id)
    return False


def _rolle_rep(kc: _Benutzerzugang, role: str) -> dict:
    r = kc.call("GET", f"/roles/{role}")
    if r.status_code == 404:
        raise KeycloakNichtErreichbar(
            f"Rolle '{role}' fehlt in Keycloak — bitte den Support informieren."
        )
    if r.status_code != 200:
        raise KeycloakAdminError(f"Rolle '{role}' konnte nicht gelesen werden (HTTP {r.status_code}).")
    rolle = r.json()
    if rolle.get("composite"):
        # Eine zusammengesetzte Rolle vergäbe mehr als ihren Namen (z. B. realm-management).
        raise KeycloakNichtErreichbar(
            f"Rolle '{role}' ist in Keycloak zusammengesetzt und wird hier nicht vergeben — "
            "bitte den Support informieren."
        )
    return rolle


def _neue_user_id(kc: _Benutzerzugang, antwort: httpx.Response, username: str) -> str:
    """ID des gerade angelegten Benutzers: aus dem Location-Header, sonst über
    eine Suche, die genau EINEN Treffer mit genau diesem Benutzernamen verlangt."""
    kandidat = antwort.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    try:
        return _require_user_id(kandidat)
    except KeycloakNichtGefunden:
        pass
    lookup = kc.call("GET", "/users", params={"username": username, "exact": "true"})
    treffer = [u for u in (lookup.json() if lookup.status_code == 200 else [])
               if u.get("username") == username]
    if len(treffer) != 1:
        logger.error("[keycloak] Neu angelegter Benutzer nicht eindeutig wiedergefunden (%d Treffer)", len(treffer))
        raise KeycloakAdminError("Benutzer angelegt, aber nicht eindeutig wiedergefunden — bitte den Support informieren.")
    return _require_user_id(treffer[0]["id"])


def create_user_for_tenant(
    *, tenant_slug: str, email: str, first_name: str, last_name: str, role: str,
) -> dict:
    """Legt einen Benutzer im Mandanten an. Rückgabe enthält das Einmalpasswort.

    Reihenfolge ist Absicht:
      1. Rolle im Realm prüfen — VOR der Anlage (create_tenant_user prüft erst
         danach und hinterlässt bei fehlender Rolle einen Benutzer ohne Rechte).
      2. Anlegen mit tenant_slug-Attribut, Passwort temporär.
      3. Prüfen, dass Keycloak das Attribut gespeichert hat — VOR der Rollenvergabe.
      4. Rolle zuweisen.
    Scheitert 3 oder 4 (auch durch Ausfall), wird der Benutzer deaktiviert, nicht gelöscht.
    """
    tenant_slug = _require_safe_slug(tenant_slug)
    if role not in MANDANTEN_ROLLEN:
        raise RolleNichtErlaubt(f"Rolle '{role}' ist nicht erlaubt.")
    email = email.strip().lower()
    pw = _gen_password()
    with _Benutzerzugang() as kc:
        rolle = _rolle_rep(kc, role)
        r = kc.call("POST", "/users", json={
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
            "attributes": {"tenant_slug": [tenant_slug]},
            "credentials": [{"type": "password", "value": pw, "temporary": True}],
        })
        if r.status_code == 409:
            raise KeycloakKonflikt("Diese E-Mail-Adresse ist bereits vergeben.")
        if r.status_code not in (201, 204):
            raise KeycloakAdminError(f"Benutzer-Anlage abgelehnt (HTTP {r.status_code}).")
        user_id = _neue_user_id(kc, r, email)

        try:
            rep = kc.call("GET", f"/users/{user_id}")
            if rep.status_code != 200 or not _gehoert_zum_mandanten(rep.json(), tenant_slug):
                raise KeycloakAdminError(
                    "Keycloak hat das Attribut tenant_slug nicht gespeichert (User-Profile prüfen). "
                    "Der Benutzer wurde deaktiviert und hat keine Rolle."
                )
            z = kc.call("POST", f"/users/{user_id}/role-mappings/realm", json=[rolle])
            if z.status_code >= 400:
                raise KeycloakNichtErreichbar(_HALB_ANGELEGT)
        except KeycloakNichtErreichbar as e:
            gesperrt = _deaktivieren_best_effort(kc, user_id, email)
            raise KeycloakNichtErreichbar(_HALB_ANGELEGT if gesperrt else _HALB_ANGELEGT_AKTIV) from e
        except KeycloakAdminError:
            _deaktivieren_best_effort(kc, user_id, email)
            raise
        benutzer = _als_benutzer(rep.json(), [role])
    return {**benutzer, "temporary_password": pw}
