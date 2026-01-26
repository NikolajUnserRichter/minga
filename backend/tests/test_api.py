"""
API Tests für Minga-Greens ERP
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


# Test-Datenbank (SQLite in-memory)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Test-DB Session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Test Client mit frischer Datenbank"""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


class TestHealth:
    """Health Check Tests"""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Minga-Greens" in response.json()["message"]


class TestSeeds:
    """Saatgut API Tests"""

    def test_list_seeds_empty(self, client):
        response = client.get("/api/v1/seeds")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_create_seed(self, client):
        seed_data = {
            "name": "Sonnenblume",
            "sorte": "Black Oil",
            "keimdauer_tage": 2,
            "wachstumsdauer_tage": 8,
            "erntefenster_min_tage": 9,
            "erntefenster_optimal_tage": 11,
            "erntefenster_max_tage": 14,
            "ertrag_gramm_pro_tray": 350,
            "verlustquote_prozent": 5.0,
        }
        response = client.post("/api/v1/seeds", json=seed_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Sonnenblume"
        assert data["gesamte_wachstumsdauer"] == 10
        assert "id" in data

    def test_create_seed_invalid_erntefenster(self, client):
        """Erntefenster: min > optimal sollte fehlschlagen"""
        seed_data = {
            "name": "Test",
            "keimdauer_tage": 2,
            "wachstumsdauer_tage": 8,
            "erntefenster_min_tage": 15,  # Ungültig: min > optimal
            "erntefenster_optimal_tage": 11,
            "erntefenster_max_tage": 14,
            "ertrag_gramm_pro_tray": 350,
        }
        response = client.post("/api/v1/seeds", json=seed_data)
        assert response.status_code == 400

    def test_get_seed(self, client):
        # Erst anlegen
        seed_data = {
            "name": "Erbse",
            "keimdauer_tage": 2,
            "wachstumsdauer_tage": 10,
            "erntefenster_min_tage": 11,
            "erntefenster_optimal_tage": 13,
            "erntefenster_max_tage": 16,
            "ertrag_gramm_pro_tray": 400,
        }
        create_response = client.post("/api/v1/seeds", json=seed_data)
        seed_id = create_response.json()["id"]

        # Dann abrufen
        response = client.get(f"/api/v1/seeds/{seed_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Erbse"

    def test_get_seed_not_found(self, client):
        response = client.get("/api/v1/seeds/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_update_seed(self, client):
        # Anlegen
        seed_data = {
            "name": "Radieschen",
            "keimdauer_tage": 1,
            "wachstumsdauer_tage": 6,
            "erntefenster_min_tage": 6,
            "erntefenster_optimal_tage": 8,
            "erntefenster_max_tage": 10,
            "ertrag_gramm_pro_tray": 250,
        }
        create_response = client.post("/api/v1/seeds", json=seed_data)
        seed_id = create_response.json()["id"]

        # Update
        update_data = {"ertrag_gramm_pro_tray": 280}
        response = client.patch(f"/api/v1/seeds/{seed_id}", json=update_data)
        assert response.status_code == 200
        # Convert to string for comparison or float
        assert float(response.json()["ertrag_gramm_pro_tray"]) == 280.0

    def test_list_seeds_filter_aktiv(self, client):
        # Aktives Seed anlegen
        seed1 = {
            "name": "Aktiv",
            "keimdauer_tage": 1,
            "wachstumsdauer_tage": 5,
            "erntefenster_min_tage": 5,
            "erntefenster_optimal_tage": 6,
            "erntefenster_max_tage": 8,
            "ertrag_gramm_pro_tray": 150,
        }
        client.post("/api/v1/seeds", json=seed1)

        # Filtern
        response = client.get("/api/v1/seeds?aktiv=true")
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestProduction:
    """Produktion API Tests"""

    def test_dashboard_summary(self, client):
        response = client.get("/api/v1/production/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert "chargen_nach_status" in data
        assert "erntereife_chargen" in data

    def test_list_grow_batches_empty(self, client):
        response = client.get("/api/v1/production/grow-batches")
        assert response.status_code == 200
        assert response.json()["items"] == []


class TestSales:
    """Vertrieb API Tests"""

    def test_list_customers_empty(self, client):
        response = client.get("/api/v1/sales/customers")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_create_customer(self, client):
        customer_data = {
            "name": "Test Restaurant",
            "typ": "GASTRO",
            "email": "test@example.com",
            "liefertage": [1, 3, 5],
        }
        response = client.post("/api/v1/sales/customers", json=customer_data)
        assert response.status_code == 201
        assert response.json()["name"] == "Test Restaurant"

    def test_list_orders_empty(self, client):
        response = client.get("/api/v1/sales/orders")
        assert response.status_code == 200
        assert response.json()["items"] == []


class TestForecasting:
    """Forecasting API Tests"""

    def test_list_forecasts_empty(self, client):
        response = client.get("/api/v1/forecasting/forecasts")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_list_production_suggestions_empty(self, client):
        response = client.get("/api/v1/forecasting/production-suggestions")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["warnungen_gesamt"] == 0
