"""Keycloak-Admin-Helper: User im Realm provisionieren.

Wird vom Platform-Admin-Flow genutzt, um beim Anlegen eines neuen Tenants
gleich einen Login-User mit dem passenden ``tenant_slug``-Attribut + Rolle
anzulegen — damit "Kunde anlegen" wirklich Zero-Touch ist.

Auth gegen Keycloak: master-Realm-Admin via Env
    KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
Ziel-Realm: KEYCLOAK_REALM (Default: novaerp)
Keycloak-Basis-URL: KEYCLOAK_URL
"""
from __future__ import annotations

import os
import re
import secrets
import string
from typing import Optional

import httpx


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
        role_resp = client.get(f"{c['url']}/admin/realms/{realm}/roles/{role}", headers=h, timeout=15)
        if role_resp.status_code == 200:
            client.post(
                f"{c['url']}/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
                headers=h,
                json=[role_resp.json()],
                timeout=15,
            )
        # (Wenn Rolle fehlt: User existiert trotzdem, nur ohne Rolle — kein harter Fehler)

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
