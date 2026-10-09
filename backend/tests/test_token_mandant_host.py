import pytest
from fastapi.testclient import TestClient

from app import database, main, tenancy
from app.api import deps
from app.core import security


@pytest.fixture
def tenant_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPROUDDESK_ROOT_DOMAIN", "novaerp.de")
    monkeypatch.setattr(tenancy, "ROOT_DOMAIN", "novaerp.de")
    monkeypatch.setattr(tenancy, "TENANTS_DIR", tmp_path)
    for module in (tenancy, database, main):
        monkeypatch.setattr(module, "DEFAULT_TENANT_SLUG", "minga")
    monkeypatch.setattr(deps.settings, "auth_disabled", False)
    monkeypatch.setattr(main.settings, "auth_disabled", False)
    monkeypatch.setattr(main.settings, "basic_auth_enabled", False)

    registry = tenancy._TenantRegistry()
    monkeypatch.setattr(tenancy, "registry", registry)
    monkeypatch.setattr(database, "registry", registry)
    monkeypatch.setattr(main, "tenant_registry", registry)
    for dependency in (deps.get_current_user, deps._tenant_db, database.get_db):
        monkeypatch.delitem(main.app.dependency_overrides, dependency, raising=False)

    test_client = TestClient(main.app, base_url="https://novaerp.de")
    try:
        for slug in ("minga", "demo"):
            tenancy.provision_tenant(slug, seed_defaults=False)
        yield test_client
    finally:
        test_client.close()
        registry.dispose_all()


@pytest.mark.parametrize(
    "host, token_tenant, expected_status, expected_detail",
    [
        pytest.param(
            "novaerp.de", "demo", 403,
            "Anmeldung nur ueber die Adresse des eigenen Arbeitsbereichs moeglich.",
            id="a_apex_demo_token",
        ),
        pytest.param(
            "admin.novaerp.de", "demo", 403,
            "Anmeldung nur ueber die Adresse des eigenen Arbeitsbereichs moeglich.",
            id="b_admin_demo_token",
        ),
        pytest.param(
            "novaerp.de", None, 403,
            "Anmeldung nur ueber die Adresse des eigenen Arbeitsbereichs moeglich.",
            id="c_apex_token_without_tenant",
        ),
        pytest.param(
            "minga.novaerp.de", "minga", 200, None,
            id="d_minga_matching_token",
        ),
        pytest.param(
            "minga.novaerp.de", "demo", 403,
            "Token gehört zu Tenant 'demo', Request ist für Tenant 'minga'.",
            id="e_minga_demo_token",
        ),
        pytest.param(
            "demo.novaerp.de", "demo", 200, None,
            id="f_demo_matching_token",
        ),
    ],
)
def test_token_requires_matching_tenant_host(
    tenant_client, monkeypatch, host, token_tenant, expected_status, expected_detail,
):
    payload = {
        "sub": "123e4567-e89b-12d3-a456-426614174000",
        "preferred_username": "testuser",
        "email": "test@example.com",
        "realm_access": {"roles": ["admin"]},
    }
    if token_tenant is not None:
        payload["tenant_slug"] = token_tenant

    def verify_token(token):
        return payload

    for module in (deps, main, security):
        monkeypatch.setattr(module, "verify_token", verify_token)

    response = tenant_client.get(
        "/api/v1/sales/customers",
        headers={"Host": host, "Authorization": "Bearer x"},
    )

    assert response.status_code == expected_status, response.text
    if expected_detail is not None:
        assert response.json()["detail"] == expected_detail
    else:
        assert response.json() == {"items": [], "total": 0}


def test_g_apex_health_without_token(tenant_client):
    response = tenant_client.get("/health", headers={"Host": "novaerp.de"})

    assert response.status_code == 200, response.text
