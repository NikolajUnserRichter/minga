import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import database, main, tenancy
from app.api import deps
from app.core import security


@pytest.fixture
def token_payload(monkeypatch):
    payload = {
        "sub": "123e4567-e89b-12d3-a456-426614174000",
        "preferred_username": "testuser",
        "email": "test@example.com",
        "realm_access": {"roles": ["admin"]},
    }

    def verify_token(token):
        return payload

    monkeypatch.setattr(deps.settings, "auth_disabled", False)
    for module in (deps, main, security):
        monkeypatch.setattr(module, "verify_token", verify_token)
    return payload


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
    "host, token_tenant, expected_statuses, expected_detail",
    [
        pytest.param(
            "novaerp.de", "demo", (403, 404), None,
            id="a_apex_demo_token",
        ),
        pytest.param(
            "admin.novaerp.de", "demo", (403, 404), None,
            id="b_admin_demo_token",
        ),
        pytest.param(
            "novaerp.de", None, (403, 404), None,
            id="c_apex_token_without_tenant",
        ),
        pytest.param(
            "minga.novaerp.de", "minga", (200,), None,
            id="d_minga_matching_token",
        ),
        pytest.param(
            "minga.novaerp.de", "demo", (403,),
            "Token gehört zu Tenant 'demo', Request ist für Tenant 'minga'.",
            id="e_minga_demo_token",
        ),
        pytest.param(
            "demo.novaerp.de", "demo", (200,), None,
            id="f_demo_matching_token",
        ),
    ],
)
def test_token_requires_matching_tenant_host(
    tenant_client, token_payload, host, token_tenant, expected_statuses, expected_detail,
):
    if token_tenant is not None:
        token_payload["tenant_slug"] = token_tenant

    response = tenant_client.get(
        "/api/v1/sales/customers",
        headers={"Host": host, "Authorization": "Bearer x"},
    )

    assert response.status_code in expected_statuses, response.text
    if response.status_code in (403, 404):
        assert set(response.json()) == {"detail"}
        assert isinstance(response.json()["detail"], str)
        assert response.json()["detail"]
        if expected_detail is not None:
            assert response.json()["detail"] == expected_detail
    else:
        assert response.json() == {"items": [], "total": 0}


def test_g_apex_health_without_token(tenant_client):
    response = tenant_client.get("/health", headers={"Host": "novaerp.de"})

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("host", ["novaerp.de", "admin.novaerp.de"])
@pytest.mark.parametrize("token_tenant", ["demo", None])
def test_get_current_user_rejects_request_without_tenant(host, token_tenant, token_payload):
    request = Request({"type": "http", "headers": [(b"host", host.encode())]})
    if token_tenant is not None:
        token_payload["tenant_slug"] = token_tenant

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(deps.get_current_user(request, token="x"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Anmeldung nur über die Adresse des eigenen Arbeitsbereichs möglich."
    )


def test_get_current_user_accepts_matching_tenant(token_payload):
    request = Request({"type": "http", "headers": [(b"host", b"minga.novaerp.de")]})
    tenancy.set_request_tenant(request, "minga")
    token_payload["tenant_slug"] = "minga"

    user = asyncio.run(deps.get_current_user(request, token="x"))

    assert user["id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert user["username"] == "testuser"
    assert user["tenant_slug"] == "minga"
    assert user["roles"] == ["admin"]
