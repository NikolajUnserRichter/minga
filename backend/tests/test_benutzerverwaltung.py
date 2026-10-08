"""Benutzerverwaltung je Mandant (Paket 4, B8).

Ein Keycloak-Realm für alle Mandanten, getrennt nur über das Benutzerattribut
tenant_slug. Geprüft wird vor allem, dass ein Mandanten-Admin Benutzer anderer
Mandanten weder sieht noch ändern kann. Keycloak ist vollständig durch einen
httpx.MockTransport ersetzt — kein Netzwerk.
"""
import copy
import hashlib
import json
import re
import uuid
from typing import get_args

import httpx
import pytest

from app.api.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.services import keycloak_admin
from app.tenancy import DEFAULT_TENANT_SLUG

# base_url=localhost → tenant_middleware setzt DEFAULT_TENANT_SLUG (tenancy.py:186-188)
MANDANT = DEFAULT_TENANT_SLUG
FREMD = "fremdfirma"
REALM = get_settings().keycloak_realm
ADMIN_ID = "11111111-1111-4111-8111-111111111111"
APP_ROLLEN = ("admin", "production_planner", "sales", "accounting", "production_staff")
STANDARDROLLE = f"default-roles-{REALM.lower()}"
TOKEN_PFAD = "/protocol/openid-connect/token"


class FakeKeycloak:
    """Keycloak-Admin-API im Speicher.

    Die q-Attributsuche liefert absichtlich TEILTREFFER (q=tenant_slug:dev
    trifft auch 'devx'), damit der exakte Python-Filter greifen muss. Ein PUT
    ohne "attributes" löscht die Attribute — der ungünstigste Fall je nach
    Keycloak-Version.
    """

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.mappings: dict[str, set] = {}
        self.client_mappings: dict[str, dict[str, list[str]]] = {}
        self.groups: dict[str, list[str]] = {}
        self.roles = {n: {"id": f"rid-{n}", "name": n, "composite": False}
                      for n in (*APP_ROLLEN, "readonly", "offline_access", "uma_authorization",
                                "realm-admin")}
        self.roles[STANDARDROLLE] = {"id": "rid-default", "name": STANDARDROLLE, "composite": True}
        self.calls: list[tuple] = []
        self.passwords: dict[str, dict] = {}
        self.down = False
        self.fehler_500 = False
        self.fehler_bei: tuple | None = None   # (Methode, Pfad ab /users…) → 500
        self.token_abgelehnt = 0               # so viele Admin-Aufrufe → 401
        self.attribute_verwerfen = False

    def add_user(self, email, tenant, roles=(), enabled=True, uid=None, first="Vor", last="Nach",
                 client_roles=None, groups=()):
        uid = uid or str(uuid.uuid4())
        self.users[uid] = {
            "id": uid, "username": email, "email": email,
            "firstName": first, "lastName": last, "enabled": enabled,
            "emailVerified": True, "createdTimestamp": 1759900000000,
            "attributes": {"tenant_slug": [tenant]} if tenant else {},
            "requiredActions": [],
        }
        self.mappings[uid] = set(roles)
        self.client_mappings[uid] = dict(client_roles or {})
        self.groups[uid] = list(groups)
        return uid

    def schreibende_calls(self, uid=None):
        return [c for c in self.calls if c[0] in ("POST", "PUT", "DELETE")
                and TOKEN_PFAD not in c[1]
                and (uid is None or uid in c[1])]

    def token_calls(self):
        return [c[1] for c in self.calls if c[1].endswith(TOKEN_PFAD)]

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("Verbindung abgelehnt", request=request)
        path = request.url.path
        body = None
        if request.content and request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
        self.calls.append((request.method, path, dict(request.url.params), body))
        if path.endswith(TOKEN_PFAD):
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 300})
        if self.token_abgelehnt:
            self.token_abgelehnt -= 1
            return httpx.Response(401, json={"error": "HTTP 401 Unauthorized"})
        if self.fehler_500:
            return httpx.Response(500, json={"error": "boom"})
        m = re.fullmatch(r"/admin/realms/([^/]+)(/.*)", path)
        assert m, f"unerwarteter Pfad {path}"
        realm, rest = m.groups()
        assert realm == REALM, f"falscher Realm {realm}"
        meth = request.method
        if self.fehler_bei == (meth, rest):
            return httpx.Response(500, json={"error": "boom"})

        if rest == "/users" and meth == "GET":
            p = request.url.params
            if "q" in p:
                key, val = p["q"].split(":", 1)
                treffer = [u for u in self.users.values()
                           if any(val in v for v in u["attributes"].get(key, []))]
            elif "username" in p:
                treffer = [u for u in self.users.values() if u["username"] == p["username"]]
            else:
                treffer = list(self.users.values())
            first, mx = int(p.get("first", 0)), int(p.get("max", 100))
            return httpx.Response(200, json=copy.deepcopy(treffer[first:first + mx]))
        if rest == "/users" and meth == "POST":
            if any(u["username"] == body["username"] for u in self.users.values()):
                return httpx.Response(409, json={"errorMessage": "User exists with same username"})
            uid = str(uuid.uuid4())
            rep = {k: v for k, v in body.items() if k != "credentials"}
            rep["id"] = uid
            rep["createdTimestamp"] = 1759900000000
            if self.attribute_verwerfen:
                rep["attributes"] = {}
            self.users[uid] = rep
            self.mappings[uid] = {STANDARDROLLE}
            self.client_mappings[uid] = {}
            self.groups[uid] = []
            self.passwords[uid] = body["credentials"][0]
            return httpx.Response(201, headers={"Location": f"{request.url}/{uid}"})
        m = re.fullmatch(r"/roles/([^/]+)", rest)
        if m and meth == "GET":
            r = self.roles.get(m.group(1))
            return httpx.Response(200, json=r) if r else httpx.Response(404, json={"error": "Could not find role"})
        m = re.fullmatch(r"/users/([^/]+)(/.*)?", rest)
        if m:
            uid, sub = m.group(1), m.group(2) or ""
            if uid not in self.users:
                return httpx.Response(404, json={"error": "User not found"})
            if sub == "" and meth == "GET":
                return httpx.Response(200, json=copy.deepcopy(self.users[uid]))
            if sub == "" and meth == "PUT":
                u = self.users[uid]
                for k in ("firstName", "lastName", "enabled", "email"):
                    if k in body:
                        u[k] = body[k]
                u["attributes"] = body.get("attributes") or {}
                return httpx.Response(204)
            if sub == "/role-mappings" and meth == "GET":
                rep = {}
                if self.mappings[uid]:
                    rep["realmMappings"] = [self.roles[n] for n in sorted(self.mappings[uid])]
                if self.client_mappings[uid]:
                    rep["clientMappings"] = {
                        c: {"id": f"cid-{c}", "client": c,
                            "mappings": [{"id": f"crid-{n}", "name": n, "composite": False} for n in namen]}
                        for c, namen in self.client_mappings[uid].items()
                    }
                return httpx.Response(200, json=rep)
            if sub == "/groups" and meth == "GET":
                return httpx.Response(200, json=[{"id": f"gid-{g}", "name": g, "path": f"/{g}"}
                                                 for g in self.groups[uid]])
            if sub == "/role-mappings/realm":
                if meth == "GET":
                    return httpx.Response(200, json=[self.roles[n] for n in sorted(self.mappings[uid])])
                if meth == "POST":
                    self.mappings[uid] |= {r["name"] for r in body}
                    return httpx.Response(204)
                if meth == "DELETE":
                    self.mappings[uid] -= {r["name"] for r in body}
                    return httpx.Response(204)
            if sub == "/logout" and meth == "POST":
                return httpx.Response(204)
            if sub == "/reset-password" and meth == "PUT":
                self.passwords[uid] = body
                return httpx.Response(204)
        raise AssertionError(f"FakeKeycloak kennt {meth} {rest} nicht")


@pytest.fixture
def kc(monkeypatch):
    fake = FakeKeycloak()
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.test")
    monkeypatch.setenv("KEYCLOAK_USERS_CLIENT_ID", "novaerp-users")
    monkeypatch.setenv("KEYCLOAK_USERS_CLIENT_SECRET", "nur-im-test")
    for name in ("KEYCLOAK_ADMIN_USER", "KEYCLOAK_ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(keycloak_admin, "_token_cache", {})
    monkeypatch.setattr(
        keycloak_admin, "_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )
    fake.add_user("chefin@beispielfirma.de", MANDANT, roles={"admin", STANDARDROLLE}, uid=ADMIN_ID,
                  first="Gerda", last="Chefin")
    return fake


class TestDienstLesen:
    """keycloak_admin direkt, ohne API."""

    def test_liste_filtert_exakt(self, kc):
        eigen = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.add_user("x@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        kc.add_user("z@aehnlich.de", f"x{MANDANT}", roles={"admin"})
        kc.add_user("ohne@ohneattribut.de", None, roles={"admin"})
        ids = [b["id"] for b in keycloak_admin.list_tenant_users(MANDANT)]
        assert sorted(ids) == sorted([ADMIN_ID, eigen])
        suche = [c for c in kc.calls if c[0] == "GET" and c[1].endswith("/users")]
        assert suche[0][2]["q"] == f"tenant_slug:{MANDANT}"
        assert kc.schreibende_calls() == []

    def test_rollen_in_rangfolge_ohne_fremde_realmrollen(self, kc):
        uid = kc.add_user("ben@beispielfirma.de", MANDANT,
                          roles={"production_staff", "sales", "offline_access", "readonly"})
        b = keycloak_admin.get_tenant_user(MANDANT, uid)
        assert b["roles"] == ["sales", "production_staff"]
        assert b["role"] == "sales"

    def test_fremder_benutzer_ist_nicht_gefunden(self, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden) as e:
            keycloak_admin.get_tenant_user(MANDANT, fremd)
        assert e.value.fremd is True
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden) as e:
            keycloak_admin.get_tenant_user(MANDANT, str(uuid.uuid4()))
        assert e.value.fremd is False

    def test_slug_kann_die_suche_nicht_erweitern(self, kc):
        with pytest.raises(keycloak_admin.KeycloakAdminError):
            keycloak_admin.list_tenant_users(f"{MANDANT} tenant_slug:{FREMD}")
        assert kc.calls == []

    @pytest.mark.parametrize("uid", ["../roles/admin", f"{ADMIN_ID}/../../roles/admin",
                                     f"{ADMIN_ID}?first=0", "kein-uuid", ""])
    def test_id_ohne_uuid_erreicht_keycloak_nicht(self, kc, uid):
        """httpx löst '..' im Pfad auf: /users/../roles/admin wäre /roles/admin."""
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.get_tenant_user(MANDANT, uid)
        assert kc.calls == []

    def test_realm_wie_tokenpruefung(self, kc, monkeypatch):
        """Nicht der KEYCLOAK_REALM-Default 'novaerp' aus _cfg()."""
        monkeypatch.delenv("KEYCLOAK_REALM", raising=False)
        keycloak_admin.list_tenant_users(MANDANT)
        admin_pfade = [c[1] for c in kc.calls if "/admin/realms/" in c[1]]
        assert admin_pfade and all(p.startswith(f"/admin/realms/{REALM}/") for p in admin_pfade)

    def test_service_account_im_zielrealm(self, kc):
        keycloak_admin.list_tenant_users(MANDANT)
        assert kc.token_calls() == [f"/realms/{REALM}{TOKEN_PFAD}"]

    def test_ohne_service_account_geschlossen(self, kc, monkeypatch):
        """T5 Risiko 2: kein stiller Rückfall auf den master-Admin."""
        monkeypatch.delenv("KEYCLOAK_USERS_CLIENT_SECRET")
        monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "test-admin")
        monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "nur-im-test")
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="Service-Account fehlt"):
            keycloak_admin.list_tenant_users(MANDANT)
        assert kc.calls == []

    def test_ohne_client_id_kein_master_rueckfall(self, kc, monkeypatch):
        """E-M16: nur der Service-Account, auch wenn der master-Admin konfiguriert ist."""
        monkeypatch.delenv("KEYCLOAK_USERS_CLIENT_ID")
        monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "test-admin")
        monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "nur-im-test")
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="Service-Account fehlt"):
            keycloak_admin.list_tenant_users(MANDANT)
        assert kc.calls == []

    def test_token_wird_wiederverwendet(self, kc):
        """Ohne Cache löste jeder Aufruf eine eigene Keycloak-Anmeldung aus."""
        for _ in range(3):
            keycloak_admin.list_tenant_users(MANDANT)
        assert len(kc.token_calls()) == 1

    def test_abgelaufenes_token_wird_einmal_erneuert(self, kc):
        keycloak_admin.list_tenant_users(MANDANT)
        kc.token_abgelehnt = 1
        assert [b["id"] for b in keycloak_admin.list_tenant_users(MANDANT)] == [ADMIN_ID]
        assert len(kc.token_calls()) == 2

    def test_nicht_erreichbar(self, kc):
        kc.down = True
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="nicht erreichbar"):
            keycloak_admin.list_tenant_users(MANDANT)

    def test_serverfehler(self, kc):
        kc.fehler_500 = True
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar):
            keycloak_admin.list_tenant_users(MANDANT)

    def test_nicht_eingerichtet(self, kc, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_URL")
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="nicht eingerichtet"):
            keycloak_admin.list_tenant_users(MANDANT)
        assert kc.calls == []
