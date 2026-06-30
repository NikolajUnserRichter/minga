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
import secrets
import string
from typing import Optional

import httpx


class KeycloakAdminError(Exception):
    pass


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
) -> dict:
    """Legt einen User im Ziel-Realm an: Email als Username, tenant_slug-Attribut,
    Realm-Rolle, Passwort (generiert falls None).

    Returns: {username, email, tenant_slug, role, password, temporary}
    Raises: KeycloakAdminError
    """
    c = _cfg()
    realm = c["realm"]
    pw = password or _gen_password()

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


def is_configured() -> bool:
    try:
        _cfg()
        return True
    except KeycloakAdminError:
        return False
