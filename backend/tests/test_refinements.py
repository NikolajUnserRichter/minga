"""
Test Refinements - Phase 9 Features
"""
import pytest
from datetime import date, timedelta

# These tests verify the Phase 9 refinements are working.

def test_main_app_imports():
    """Verify app can be imported without errors."""
    from app.main import app
    assert app is not None
    assert app.title == "Minga-Greens ERP"

def test_weekly_harvest_endpoint_exists(client):
    """Verify the dashboard summary endpoint exists and returns expected fields."""
    response = client.get("/api/v1/production/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "weekly_harvest_kg" in data
    assert "active_batches" in data
    assert "harvest_ready" in data

def test_inventory_correction_endpoint_exists(client):
    """Verify the inventory correction endpoint is registered."""
    # A POST without data should fail validation, but not 404
    response = client.post("/api/v1/inventory/correction")
    # 422 = validation error (expected, as we didn't provide params)
    # 404 = route doesn't exist (bad)
    assert response.status_code != 404, "Correction endpoint should exist"

@pytest.mark.skip(reason="Uses PostgreSQL-specific to_char function, requires PostgreSQL for testing")
def test_analytics_endpoints_exist(client):
    """Verify analytics endpoints are registered."""
    response = client.get("/api/v1/analytics/revenue")
    # Should not be 404, can be 400/422 if params missing
    assert response.status_code != 404, "Revenue analytics endpoint should exist"

def test_capacity_endpoints_exist(client):
    """Verify capacity endpoints are registered."""
    response = client.get("/api/v1/capacity/utilization")
    assert response.status_code != 404, "Capacity utilization endpoint should exist"
