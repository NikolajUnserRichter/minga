import pytest
from datetime import date
from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.customer import CustomerType, SubscriptionInterval

# Test-Datenbank Setup (Kopie von test_erp.py)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_customer(client):
    customer_data = {
        "name": "Test Restaurant",
        "typ": "GASTRO",
        "pk": "test"
    }
    response = client.post("/api/v1/sales/customers", json=customer_data)
    assert response.status_code == 201
    return response.json()

@pytest.fixture
def sample_seed(client):
    seed_data = {
        "name": "Sonnenblume",
        "sorte": "Bio",
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
    return response.json()

class TestFeatures:
    def test_pdf_generation(self, client, sample_customer):
        # 1. Invoice erstellen
        invoice_response = client.post("/api/v1/invoices", json={
            "customer_id": sample_customer["id"],
            "invoice_date": date.today().isoformat()
        })
        assert invoice_response.status_code == 201
        invoice_id = invoice_response.json()["id"]

        # 2. PDF abrufen
        response = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        if response.status_code != 200:
             print(f"PDF Error: {response.json()}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 0
        assert b"%PDF" in response.content

    @pytest.mark.asyncio
    async def test_subscription_processing(self, client, sample_customer, sample_seed):
        # 1. Abo erstellen
        sub_data = {
            "kunde_id": sample_customer["id"],
            "seed_id": sample_seed["id"],
            "menge": 100,
            "einheit": "G",
            "intervall": "TAEGLICH",
            "gueltig_von": date.today().isoformat(),
            "aktiv": True
        }
        sub_response = client.post("/api/v1/sales/subscriptions", json=sub_data)
        assert sub_response.status_code == 201
        
        # Manuelles Ausführen der Logik mit Test-DB, da Celery eigene DB/Session hat
        from app.database import get_db
        # Wir müssen an die interne Session kommen, die 'client' benutzt.
        # client benutzt 'override_get_db' das 'TestingSessionLocal' benutzt.
        # Wir holen uns eine neue Session aus TestingSessionLocal für den Test.
        db = TestingSessionLocal()
        try:
            from app.models.customer import Subscription
            from app.tasks.subscription_tasks import _create_order_from_subscription, _is_subscription_due_today
            
            # Subscription laden
            sub = db.get(Subscription, UUID(sub_response.json()["id"]))
            assert sub is not None
            assert _is_subscription_due_today(sub) is True
            
            # Order erstellen
            _create_order_from_subscription(db, sub)
            db.commit()
            
            # Prüfen via API
            orders_response = client.get(f"/api/v1/sales/orders?kunde_id={sample_customer['id']}")
            assert orders_response.status_code == 200
            orders = orders_response.json()["items"]
            assert len(orders) == 1
            assert orders[0]["status"] == "ENTWURF"
        finally:
            db.close()

    def test_production_view(self, client, sample_customer, sample_seed):
        from unittest.mock import patch
        # 1. Mock Celery task to avoid Redis connection
        with patch("app.tasks.forecast_tasks.update_forecast_from_order.delay") as mock_task:
            # Order erstellen
            order_data = {
                "customer_id": sample_customer["id"],
                "requested_delivery_date": date.today().isoformat(),
                "lines": [
                    {
                        "product_name": "Test Produkt",
                        "quantity": 500,
                        "unit": "G",
                        "unit_price": 1.0,
                    }
                ]
            }
            order_response = client.post("/api/v1/sales/orders", json=order_data)
            assert order_response.status_code == 201
            order_id = order_response.json()["id"]
            
            # Bestätigen
            client.post(f"/api/v1/sales/orders/{order_id}/confirm")
        
        # 2. Production View abrufen
        response = client.get(f"/api/v1/production/packaging-plan?target_date={date.today().isoformat()}")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 1
        assert data["items"][0]["total_quantity"] == 500
