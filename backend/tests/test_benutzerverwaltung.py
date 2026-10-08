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


def _als(rollen=("admin",), tenant=MANDANT, uid=ADMIN_ID,
         username="chefin@beispielfirma.de", email="chefin@beispielfirma.de"):
    async def override():
        u = {"id": uid, "username": username, "email": email, "roles": list(rollen)}
        if tenant is not None:
            u["tenant_slug"] = tenant
        return u
    app.dependency_overrides[get_current_user] = override


@pytest.fixture
def admin(client, kc):
    from app.api.v1 import users as benutzer_api
    benutzer_api._schreibzeiten.clear()  # Schreibbremse je Test frisch
    vorher = app.dependency_overrides.get(get_current_user)
    _als()
    yield client
    app.dependency_overrides[get_current_user] = vorher


def _audit_zeilen(caplog):
    return [json.loads(r.getMessage().split(" ", 1)[1])
            for r in caplog.records if r.name == "app.audit.benutzer"]


class TestZugriff:
    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_liest(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert admin.get("/api/v1/users").status_code == 403
        assert admin.get(f"/api/v1/users/{ADMIN_ID}").status_code == 403
        assert kc.calls == []

    def test_ohne_mandant_im_token(self, admin, kc):
        """Basic-Auth und AUTH_DISABLED liefern keinen tenant_slug (deps.py:38-57)."""
        _als(tenant=None)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_ohne_sub_im_token(self, admin, kc):
        """Ohne Benutzer-ID griffe der Selbstschutz ins Leere (acting_user_id 'None')."""
        _als(uid=None)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_token_anderer_mandant(self, admin, kc):
        _als(tenant=FREMD)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_kein_loeschen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.delete(f"/api/v1/users/{uid}").status_code == 405
        assert uid in kc.users


class TestListe:
    def test_nur_eigener_mandant(self, admin, kc):
        eigen = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.add_user("x@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        r = admin.get("/api/v1/users")
        assert r.status_code == 200, r.text
        assert sorted(b["id"] for b in r.json()["items"]) == sorted([ADMIN_ID, eigen])
        assert r.json()["total"] == 2

    def test_felder_und_eigener_eintrag(self, admin, kc):
        kc.add_user("ben@beispielfirma.de", MANDANT, roles={"sales"}, first="Ben", last="Verkauf")
        items = {b["email"]: b for b in admin.get("/api/v1/users").json()["items"]}
        assert items["chefin@beispielfirma.de"]["is_self"] is True
        ben = items["ben@beispielfirma.de"]
        assert ben["is_self"] is False
        assert (ben["first_name"], ben["last_name"], ben["role"], ben["enabled"]) == ("Ben", "Verkauf", "sales", True)
        assert ben["created_at"].startswith("2025-10-08")


class TestDemoListe:
    """E-M6: Im Mandanten demo sieht jeder Besucher die Liste — dort nur die
    öffentlichen Demo-Konten, und die Oberfläche erfährt, dass nichts änderbar ist."""

    def test_nur_demo_logins_schreibgeschuetzt(self, admin, kc, monkeypatch):
        from app.api.v1 import users
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        anna = kc.add_user("anna@demo.novaerp.de", MANDANT, roles={"admin"})
        ben = kc.add_user("ben@demo.novaerp.de", MANDANT, roles={"sales"})
        mia = kc.add_user("mia@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.get("/api/v1/users")
        assert r.status_code == 200, r.text
        assert sorted(b["id"] for b in r.json()["items"]) == sorted([anna, ben])
        assert (r.json()["total"], r.json()["schreibgeschuetzt"]) == (2, True)
        versteckt = admin.get(f"/api/v1/users/{mia}")
        assert (versteckt.status_code, versteckt.json()) == (404, {"detail": "Benutzer nicht gefunden."})
        assert admin.get(f"/api/v1/users/{anna}").status_code == 200

    def test_sonst_vollstaendig_und_schreibbar(self, admin, kc):
        mia = kc.add_user("mia@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.get("/api/v1/users")
        assert r.status_code == 200, r.text
        assert sorted(b["id"] for b in r.json()["items"]) == sorted([ADMIN_ID, mia])
        assert r.json()["schreibgeschuetzt"] is False


class TestFremderMandantLesen:
    def test_fremd_wie_unbekannt(self, admin, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        r = admin.get(f"/api/v1/users/{fremd}")
        unbekannt = admin.get(f"/api/v1/users/{uuid.uuid4()}")
        assert r.status_code == unbekannt.status_code == 404
        assert r.json() == unbekannt.json() == {"detail": "Benutzer nicht gefunden."}

    def test_benutzer_ohne_attribut_ist_fremd(self, admin, kc):
        uid = kc.add_user("svc@intern.de", None)
        assert admin.get(f"/api/v1/users/{uid}").status_code == 404
        assert ("GET", f"/admin/realms/{REALM}/users/{uid}") in [c[:2] for c in kc.calls]

    def test_aehnlicher_slug_ist_fremd(self, admin, kc):
        uid = kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        assert admin.get(f"/api/v1/users/{uid}").status_code == 404
        assert ("GET", f"/admin/realms/{REALM}/users/{uid}") in [c[:2] for c in kc.calls]

    def test_ungueltige_id(self, admin, kc):
        assert admin.get("/api/v1/users/kein-uuid").status_code == 422
        assert admin.get("/api/v1/users/..%2F..%2Froles").status_code in (404, 422)
        assert kc.calls == []

    def test_fremdzugriff_im_audit(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        admin.get(f"/api/v1/users/{fremd}")
        z = _audit_zeilen(caplog)
        assert z[-1]["aktion"] == "FREMDZUGRIFF_ABGEWIESEN"
        assert (z[-1]["ziel_id"], z[-1]["mandant"], z[-1]["von_id"]) == (fremd, MANDANT, ADMIN_ID)


class TestAusfallLesen:
    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        r = admin.get("/api/v1/users")
        assert r.status_code == 503
        assert r.json()["detail"] == "Benutzerverwaltung derzeit nicht verfügbar: Keycloak ist nicht erreichbar."

    @pytest.mark.parametrize("variable", ["KEYCLOAK_URL", "KEYCLOAK_USERS_CLIENT_ID"])
    def test_nicht_eingerichtet(self, admin, kc, monkeypatch, variable):
        monkeypatch.delenv(variable)
        r = admin.get("/api/v1/users")
        assert r.status_code == 503
        assert "nicht eingerichtet" in r.json()["detail"]
        assert kc.calls == []


def test_rollenlisten_stimmen_ueberein():
    from app.main import ALLE_ROLLEN
    from app.schemas.user import Rolle
    assert set(get_args(Rolle)) == set(keycloak_admin.MANDANTEN_ROLLEN) == set(ALLE_ROLLEN)
    assert keycloak_admin.MANDANTEN_ROLLEN == APP_ROLLEN


def _neu(admin, **kw):
    body = {"email": "lena@beispielfirma.de", "first_name": "Lena", "last_name": "Lager",
            "role": "production_staff", **kw}
    return admin.post("/api/v1/users", json=body)


class TestAnlegen:
    def test_mitarbeiter_anlegen(self, admin, kc):
        r = _neu(admin)
        assert r.status_code == 201, r.text
        assert r.headers["cache-control"] == "no-store"
        b = r.json()
        assert (b["role"], b["roles"], b["enabled"]) == ("production_staff", ["production_staff"], True)
        assert len(b["temporary_password"]) >= 16
        assert kc.users[b["id"]]["attributes"] == {"tenant_slug": [MANDANT]}
        assert kc.mappings[b["id"]] == {STANDARDROLLE, "production_staff"}
        assert kc.passwords[b["id"]] == {"type": "password", "value": b["temporary_password"], "temporary": True}

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_legt_an(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert _neu(admin).status_code == 403
        assert kc.calls == []

    def test_mandant_aus_body_abgelehnt(self, admin, kc):
        assert _neu(admin, tenant_slug=FREMD).status_code == 422
        assert _neu(admin, attributes={"tenant_slug": [FREMD]}).status_code == 422
        assert kc.schreibende_calls() == []

    @pytest.mark.parametrize("rolle", ["realm-admin", "readonly", "offline_access", "ADMIN", ""])
    def test_rolle_ausserhalb_allowlist(self, admin, kc, rolle):
        assert _neu(admin, role=rolle).status_code == 422
        assert kc.schreibende_calls() == []

    def test_rolle_fehlt_im_realm_nichts_angelegt(self, admin, kc):
        del kc.roles["production_staff"]
        r = _neu(admin)
        assert r.status_code == 503, r.text
        assert "production_staff" in r.json()["detail"]
        assert kc.schreibende_calls() == []

    def test_zusammengesetzte_rolle_nicht_vergeben(self, admin, kc):
        """Enthielte eine App-Rolle in Produktion z. B. realm-management-Rollen,
        vergäbe der Mandanten-Admin mehr, als die Allowlist zeigt."""
        kc.roles["sales"]["composite"] = True
        r = _neu(admin, role="sales")
        assert r.status_code == 503, r.text
        assert "zusammengesetzt" in r.json()["detail"]
        assert kc.schreibende_calls() == []

    def test_email_vergeben(self, admin, kc, caplog):
        """E-M7: Die Adresse gehört womöglich einem anderen Mandanten — im Audit nur ihr Hash."""
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        fremd = kc.add_user("lena@beispielfirma.de", FREMD)
        r = _neu(admin, email="Lena@Beispielfirma.DE")
        assert r.status_code == 409
        assert r.json()["detail"] == "Diese E-Mail-Adresse ist bereits vergeben."
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["attributes"] == {"tenant_slug": [FREMD]}
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["von_id"]) == ("ANLAGE_KONFLIKT", ADMIN_ID)
        assert z[-1]["ziel_email_sha256"] == hashlib.sha256(b"lena@beispielfirma.de").hexdigest()
        assert "ziel_email" not in z[-1]
        assert "lena@beispielfirma.de" not in caplog.text.lower()
        assert "lena@beispielfirma.de" not in r.text.lower()

    def test_email_klein_geschrieben(self, admin, kc):
        r = _neu(admin, email="Lena.Lager@Beispielfirma.DE")
        assert r.status_code == 201, r.text
        assert kc.users[r.json()["id"]]["username"] == "lena.lager@beispielfirma.de"

    def test_umlaut_in_email(self, admin, kc):
        assert _neu(admin, email="jürgen@beispielfirma.de").status_code == 422
        assert kc.schreibende_calls() == []

    def test_attribut_nicht_gespeichert_keine_rolle(self, admin, kc):
        kc.attribute_verwerfen = True
        r = _neu(admin)
        assert r.status_code == 502, r.text
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False
        assert kc.mappings[neu["id"]] == {STANDARDROLLE}

    def test_lesen_nach_anlage_scheitert_deaktiviert(self, admin, kc, monkeypatch):
        """Keycloak legt an und fällt dann aus: der Benutzer bleibt nicht aktiv ohne Rolle."""
        orig = kc.handler
        ausgefallen = []

        def handler(request):
            angelegt = any(c[0] == "POST" and c[1].endswith("/users") for c in kc.calls)
            if (angelegt and not ausgefallen and request.method == "GET"
                    and re.fullmatch(rf"/admin/realms/{REALM}/users/[0-9a-f-]+", request.url.path)):
                ausgefallen.append(request.url.path)
                return httpx.Response(503, json={"error": "kurz weg"})
            return orig(request)

        monkeypatch.setattr(keycloak_admin, "_http_client",
                            lambda: httpx.Client(transport=httpx.MockTransport(handler)))
        r = _neu(admin)
        assert r.status_code == 503, r.text
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False
        assert kc.mappings[neu["id"]] == {STANDARDROLLE}
        assert "deaktiviert" in r.json()["detail"]

    def test_rueckfall_suche_trifft_keinen_fremden(self, admin, kc, monkeypatch):
        """201 ohne Location-Header und eine username-Suche mit Teiltreffern:
        weder Weiterarbeit noch Deaktivierung darf einen anderen Benutzer treffen."""
        fremd = kc.add_user("xlena@beispielfirma.de", FREMD, roles={"admin"})
        kc.attribute_verwerfen = True
        orig = kc.handler

        def handler(request):
            pfad = request.url.path
            if pfad == f"/admin/realms/{REALM}/users" and request.method == "POST":
                antwort = orig(request)
                return httpx.Response(201) if antwort.status_code == 201 else antwort
            if pfad == f"/admin/realms/{REALM}/users" and "username" in request.url.params:
                kc.calls.append(("GET", pfad, dict(request.url.params), None))
                name = request.url.params["username"]
                treffer = sorted((u for u in kc.users.values() if name in u["username"]),
                                 key=lambda u: u["username"] != "xlena@beispielfirma.de")
                return httpx.Response(200, json=copy.deepcopy(treffer))
            return orig(request)

        monkeypatch.setattr(keycloak_admin, "_http_client",
                            lambda: httpx.Client(transport=httpx.MockTransport(handler)))
        r = _neu(admin)
        assert r.status_code == 502, r.text
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["enabled"] is True
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        """Demo-Logins sind öffentlich; der Demo-Reset setzt Keycloak nicht zurück."""
        from app.api.v1 import users
        assert users.DEMO_MANDANT == "demo"
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.get("/api/v1/users").status_code == 200
        assert _neu(admin).status_code == 403
        assert kc.schreibende_calls() == []

    @pytest.mark.parametrize("username,email", [
        ("anna@demo.novaerp.de", "anna@demo.novaerp.de"),
        ("anna@demo.novaerp.de", "umbenannt@beispielfirma.de"),
        ("ANNA@demo.novaerp.de", None),
    ])
    def test_demo_login_schreibt_in_keinem_mandanten(self, admin, kc, username, email):
        """Öffentlicher Demo-Login (demo1234) mit verstelltem tenant_slug: Mandant
        ist nicht 'demo', die Slug-Sperre griffe nicht — die Login-Sperre schon."""
        _als(username=username, email=email)
        assert _neu(admin, role="admin").status_code == 403
        assert kc.schreibende_calls() == []

    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        r = _neu(admin)
        assert r.status_code == 503
        assert "nicht erreichbar" in r.json()["detail"]

    def test_audit_ohne_passwort(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        r = _neu(admin)
        z = _audit_zeilen(caplog)
        assert len(z) == 1
        assert (z[0]["aktion"], z[0]["mandant"], z[0]["von_id"]) == ("BENUTZER_ANGELEGT", MANDANT, ADMIN_ID)
        assert (z[0]["ziel_id"], z[0]["ziel_email"], z[0]["rolle"]) == (r.json()["id"], "lena@beispielfirma.de", "production_staff")
        assert r.json()["temporary_password"] not in caplog.text

    def test_dienst_prueft_rolle_selbst(self, kc):
        with pytest.raises(keycloak_admin.RolleNichtErlaubt):
            keycloak_admin.create_user_for_tenant(tenant_slug=MANDANT, email="a@beispielfirma.de",
                                                  first_name="A", last_name="B", role="realm-admin")
        assert kc.calls == []


def _supportkonto(kc, art):
    """Konto mit tenant_slug dieses Mandanten, aber mehr Rechten, als die App-Rollen zeigen."""
    if art == "client_rolle":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin"},
                           client_roles={"realm-management": ["realm-admin"]})
    if art == "gruppe":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin"}, groups=["support"])
    if art == "fremde_realmrolle":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin", "realm-admin"})
    kc.roles["sales"]["composite"] = True
    return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"sales"})


SUPPORTKONTEN = ["client_rolle", "gruppe", "fremde_realmrolle", "zusammengesetzt"]


class TestAendern:
    def test_name_aendern_behaelt_mandant(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena"})
        assert r.status_code == 200, r.text
        assert r.json()["first_name"] == "Helena"
        assert kc.users[uid]["attributes"] == {"tenant_slug": [MANDANT]}

    def test_rolle_wechseln_genau_eine_approlle(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT,
                          roles={"production_staff", "sales", "offline_access"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"role": "accounting"})
        assert r.status_code == 200, r.text
        assert kc.mappings[uid] == {"accounting", "offline_access"}
        assert r.json()["roles"] == ["accounting"]

    def test_rollenwechsel_beendet_sitzungen(self, admin, kc):
        b = kc.add_user("b@beispielfirma.de", MANDANT, roles={"admin"})
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 200
        assert ("POST", f"/admin/realms/{REALM}/users/{b}/logout") in [c[:2] for c in kc.calls]

    def test_standardkonto_ist_aenderbar(self, admin, kc):
        """Keycloak-Standardrollen und die Account-Konsole machen kein Supportkonto."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT,
                          roles={"production_staff", STANDARDROLLE, "offline_access", "uma_authorization"},
                          client_roles={"account": ["manage-account", "view-profile"]})
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 200

    def test_deaktivieren_statt_loeschen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"enabled": False})
        assert r.status_code == 200, r.text
        assert kc.users[uid]["enabled"] is False
        assert ("POST", f"/admin/realms/{REALM}/users/{uid}/logout") in [c[:2] for c in kc.calls]
        assert not [c for c in kc.calls if c[0] == "DELETE" and c[1].endswith(f"/users/{uid}")]

    def test_reaktivieren(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, enabled=False)
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": True}).json()["enabled"] is True

    def test_leerer_patch(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={}).status_code == 422

    def test_email_aendern_nicht_vorgesehen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={"email": "neu@beispielfirma.de"}).status_code == 422

    def test_rolle_ausserhalb_allowlist(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={"role": "realm-admin"}).status_code == 422
        assert kc.schreibende_calls(uid) == []

    def test_fehlende_rolle_nichts_geschrieben(self, admin, kc):
        """Rolle wird VOR dem ersten Schreiben gelesen — kein halb geänderter Benutzer."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        del kc.roles["accounting"]
        r = admin.patch(f"/api/v1/users/{uid}",
                        json={"enabled": False, "first_name": "Helena", "role": "accounting"})
        assert r.status_code == 503, r.text
        assert kc.schreibende_calls(uid) == []
        assert kc.users[uid]["enabled"] is True and kc.users[uid]["firstName"] == "Lena"

    def test_teilweise_geaendert_im_audit(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        kc.fehler_bei = ("POST", f"/users/{uid}/role-mappings/realm")
        r = admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena", "role": "sales"})
        assert r.status_code == 503, r.text
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["ziel_id"]) == ("BENUTZER_TEILWEISE_GEAENDERT", uid)
        assert z[-1]["aenderungen"] == {"first_name": ["Lena", "Helena"], "roles": [["production_staff"], []]}

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_aendert(self, admin, kc, rolle):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        _als(rollen=(rolle,))
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 403
        assert kc.calls == []

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        from app.api.v1 import users
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "X"}).status_code == 403
        assert kc.schreibende_calls() == []

    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "X"}).status_code == 503

    def test_audit_mit_aenderungen(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena", "role": "sales"})
        z = _audit_zeilen(caplog)
        assert z[-1]["aktion"] == "BENUTZER_GEAENDERT" and z[-1]["ziel_id"] == uid
        assert z[-1]["aenderungen"] == {"first_name": ["Lena", "Helena"],
                                        "roles": [["production_staff"], ["sales"]]}

    def test_dienst_prueft_rolle_selbst(self, kc):
        with pytest.raises(keycloak_admin.RolleNichtErlaubt):
            keycloak_admin.update_tenant_user(tenant_slug=MANDANT, user_id=ADMIN_ID,
                                              acting_user_id="x", role="realm-admin")
        assert kc.calls == []


class TestFremderMandantAendern:
    @pytest.mark.parametrize("body", [
        {"enabled": False}, {"role": "admin"}, {"first_name": "Gehackt"},
    ])
    def test_404_und_kein_schreibzugriff(self, admin, kc, body):
        fremd = kc.add_user("x@fremdfirma.de", FREMD, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{fremd}", json=body)
        unbekannt = admin.patch(f"/api/v1/users/{uuid.uuid4()}", json=body)
        assert r.status_code == 404, r.text
        assert r.json() == unbekannt.json() == {"detail": "Benutzer nicht gefunden."}
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["enabled"] is True and kc.users[fremd]["firstName"] == "Vor"
        assert kc.mappings[fremd] == {"production_staff"}

    def test_benutzer_ohne_attribut(self, admin, kc):
        uid = kc.add_user("svc@intern.de", None)
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 404
        assert kc.schreibende_calls(uid) == []


class TestSupportkontenAendern:
    @pytest.mark.parametrize("art", SUPPORTKONTEN)
    @pytest.mark.parametrize("body", [{"enabled": False}, {"role": "production_staff"}, {"first_name": "X"}])
    def test_abgewiesen_ohne_schreibzugriff(self, admin, kc, caplog, art, body):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = _supportkonto(kc, art)
        r = admin.patch(f"/api/v1/users/{uid}", json=body)
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden."
        assert kc.schreibende_calls(uid) == []
        assert kc.users[uid]["enabled"] is True and kc.users[uid]["firstName"] == "Vor"
        assert (_audit_zeilen(caplog)[-1]["aktion"], _audit_zeilen(caplog)[-1]["ziel_id"]) == (
            "SUPPORTKONTO_ABGEWIESEN", uid)


class TestSchutzregeln:
    def test_selbst_deaktivieren(self, admin, kc):
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        r = admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"enabled": False})
        assert r.status_code == 409
        assert kc.users[ADMIN_ID]["enabled"] is True

    def test_ohne_sub_kein_selbstdeaktivieren(self, admin, kc):
        """Token ohne sub: acting_user_id wäre 'None', der Selbstschutz griffe nicht."""
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        _als(uid=None)
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"enabled": False}).status_code == 403
        assert kc.users[ADMIN_ID]["enabled"] is True
        assert kc.schreibende_calls() == []

    def test_selbst_herabstufen(self, admin, kc):
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        r = admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"role": "sales"})
        assert r.status_code == 409
        assert kc.mappings[ADMIN_ID] == {"admin", STANDARDROLLE}

    def test_eigenen_namen_aendern_erlaubt(self, admin, kc):
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "Neu"}).status_code == 200

    def test_letzter_aktiver_admin(self, admin, kc):
        """Der Aufrufer hat admin nur im Token (z. B. über eine Gruppe); in
        Keycloak ist B der einzige direkte, aktive Admin des Mandanten."""
        kc.mappings[ADMIN_ID] = set()
        b = kc.add_user("b@beispielfirma.de", MANDANT, roles={"admin"})
        kc.add_user("fremdadmin@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("inaktiv@beispielfirma.de", MANDANT, roles={"admin"}, enabled=False)
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 409
        assert admin.patch(f"/api/v1/users/{b}", json={"enabled": False}).status_code == 409
        assert kc.mappings[b] == {"admin"} and kc.users[b]["enabled"] is True
        kc.add_user("c@beispielfirma.de", MANDANT, roles={"admin"})
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 200


class TestPasswort:
    def test_reset_liefert_einmalpasswort(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        assert r.json()["user"]["id"] == uid
        assert kc.passwords[uid] == {"type": "password", "value": r.json()["temporary_password"], "temporary": True}

    def test_reset_beendet_sitzungen(self, admin, kc):
        """Nach einem kompromittierten Konto bliebe der Angreifer sonst per Refresh-Token drin."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.post(f"/api/v1/users/{uid}/reset-password").status_code == 200
        schreibend = [c[:2] for c in kc.schreibende_calls(uid)]
        assert schreibend == [("PUT", f"/admin/realms/{REALM}/users/{uid}/reset-password"),
                              ("POST", f"/admin/realms/{REALM}/users/{uid}/logout")]

    def test_logout_scheitert_passwort_trotzdem_geliefert(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.fehler_bei = ("POST", f"/users/{uid}/logout")
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        assert kc.passwords[uid]["value"] == r.json()["temporary_password"]

    def test_fremd_404_und_kein_schreibzugriff(self, admin, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD, roles={"production_staff"})
        r = admin.post(f"/api/v1/users/{fremd}/reset-password")
        unbekannt = admin.post(f"/api/v1/users/{uuid.uuid4()}/reset-password")
        assert r.status_code == 404
        assert r.json() == unbekannt.json()
        assert kc.schreibende_calls(fremd) == [] and fremd not in kc.passwords

    @pytest.mark.parametrize("art", SUPPORTKONTEN)
    def test_supportkonto_nicht_uebernehmbar(self, admin, kc, caplog, art):
        """Angriff: Mandanten-Admin setzt das Passwort eines Betreiberkontos mit
        tenant_slug seines Mandanten zurück und verwaltet danach den ganzen Realm."""
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = _supportkonto(kc, art)
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 409, r.text
        assert "temporary_password" not in r.text
        assert kc.schreibende_calls(uid) == [] and uid not in kc.passwords
        assert _audit_zeilen(caplog)[-1]["aktion"] == "SUPPORTKONTO_ABGEWIESEN"

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert admin.post(f"/api/v1/users/{ADMIN_ID}/reset-password").status_code == 403
        assert kc.calls == []

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        from app.api.v1 import users
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.post(f"/api/v1/users/{ADMIN_ID}/reset-password").status_code == 403
        assert kc.schreibende_calls() == []

    def test_audit_ohne_passwort(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        pw = admin.post(f"/api/v1/users/{uid}/reset-password").json()["temporary_password"]
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["ziel_id"]) == ("PASSWORT_ZURUECKGESETZT", uid)
        assert pw not in caplog.text

    def test_dienst_prueft_id_selbst(self, kc):
        """T5 R4 will die Dienstfunktionen auch hinter Plattform-Endpunkten nutzen."""
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.reset_tenant_user_password(tenant_slug=MANDANT, user_id="../roles/admin")
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.update_tenant_user(tenant_slug=MANDANT, user_id="../roles/admin",
                                              acting_user_id=ADMIN_ID, enabled=False)
        assert kc.calls == []


class TestSchreibbremse:
    """Die globale slowapi-Grenze wirkt nicht (keine SlowAPIMiddleware): ohne eigene
    Bremse könnte ein Mandanten-Admin Keycloak mit Schreibaufrufen fluten und
    fremde E-Mail-Adressen per 409 in Serie abklopfen."""

    def test_schreibbremse_je_mandant(self, admin, kc, monkeypatch):
        from app.api.v1 import users as benutzer_api
        monkeypatch.setattr(benutzer_api, "SCHREIBEN_JE_MINUTE", 3)
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        for _ in range(3):
            assert admin.post(f"/api/v1/users/{uid}/reset-password").status_code == 200
        passwort, schreibend = kc.passwords[uid], len(kc.schreibende_calls())
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 429
        assert r.json()["detail"] == "Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen."
        assert _neu(admin, email="neu@beispielfirma.de").status_code == 429
        assert admin.patch(f"/api/v1/users/{uid}", json={"first_name": "X"}).status_code == 429
        assert (kc.passwords[uid], len(kc.schreibende_calls())) == (passwort, schreibend)
        assert admin.get("/api/v1/users").status_code == 200  # Lesen bleibt frei
        assert benutzer_api._schreibbremse(FREMD) == FREMD  # anderer Mandant, eigener Zähler
