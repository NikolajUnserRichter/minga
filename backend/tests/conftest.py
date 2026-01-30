"""
Pytest Konfiguration und gemeinsame Fixtures
"""
import pytest
from datetime import date, timedelta
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


# Dependency Override
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db():
    """Datenbankverbindung für Tests"""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating tables: {e}")
        # Optionally re-raise if you want the test to error out immediately
        pass 
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Test Client mit frischer Datenbank"""
    # Auth Override
    from app.api.deps import get_current_user
    async def override_auth():
        return {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["admin", "production_planner"]
        }
    
    app.dependency_overrides[get_current_user] = override_auth
    
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    
    # Cleanup overrides
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def sample_seed(client):
    """Erstellt ein Test-Saatgut"""
    seed_data = {
        "name": "Sonnenblume",
        "sorte": "Black Oil",
        "lieferant": "BioSaat GmbH",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9,
        "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14,
        "ertrag_gramm_pro_tray": 350,
        "verlustquote_prozent": 5.0,
    }
    response = client.post("/api/v1/seeds", json=seed_data)
    return response.json()


@pytest.fixture
def sample_seeds(client):
    """Erstellt mehrere Test-Saatgut-Sorten"""
    seeds = []
    seed_configs = [
        {
            "name": "Sonnenblume",
            "keimdauer_tage": 2,
            "wachstumsdauer_tage": 8,
            "erntefenster_min_tage": 9,
            "erntefenster_optimal_tage": 11,
            "erntefenster_max_tage": 14,
            "ertrag_gramm_pro_tray": 350,
        },
        {
            "name": "Erbse",
            "keimdauer_tage": 2,
            "wachstumsdauer_tage": 10,
            "erntefenster_min_tage": 11,
            "erntefenster_optimal_tage": 13,
            "erntefenster_max_tage": 16,
            "ertrag_gramm_pro_tray": 400,
        },
        {
            "name": "Radieschen",
            "keimdauer_tage": 1,
            "wachstumsdauer_tage": 6,
            "erntefenster_min_tage": 6,
            "erntefenster_optimal_tage": 8,
            "erntefenster_max_tage": 10,
            "ertrag_gramm_pro_tray": 250,
        },
    ]
    for config in seed_configs:
        response = client.post("/api/v1/seeds", json=config)
        seeds.append(response.json())
    return seeds


@pytest.fixture
def sample_customer(client):
    """Erstellt einen Test-Kunden"""
    customer_data = {
        "name": "Test Restaurant",
        "typ": "GASTRO",
        "email": "test@example.com",
        "telefon": "089-12345678",
        "adresse": "Teststraße 1, 80333 München",
        "liefertage": [1, 3, 5],
    }
    response = client.post("/api/v1/sales/customers", json=customer_data)
    return response.json()


@pytest.fixture
def sample_customers(client):
    """Erstellt mehrere Test-Kunden"""
    customers = []
    customer_configs = [
        {"name": "Restaurant Schumann", "typ": "GASTRO", "liefertage": [1, 3, 5]},
        {"name": "BioMarkt München", "typ": "HANDEL", "liefertage": [0, 2, 4]},
        {"name": "Max Müller", "typ": "PRIVAT", "liefertage": [5]},
    ]
    for config in customer_configs:
        response = client.post("/api/v1/sales/customers", json=config)
        customers.append(response.json())
    return customers


@pytest.fixture
def sample_location(client):
    """Erstellt einen Test-Lagerort"""
    location_data = {
        "code": "LAGER-TEST",
        "name": "Test Lager",
        "location_type": "LAGER",
    }
    response = client.post("/api/v1/inventory/locations", json=location_data)
    return response.json()


@pytest.fixture
def sample_product(client, sample_seed):
    """Erstellt ein Test-Produkt"""
    product_data = {
        "sku": "MG-TEST-001",
        "name": "Test Microgreens",
        "category": "MICROGREEN",
        "seed_id": sample_seed["id"],
        "base_price": 0.08,
        "tax_rate": "REDUZIERT",
        "is_sellable": True,
    }
    response = client.post("/api/v1/products", json=product_data)
    return response.json()


@pytest.fixture
def sample_invoice(client, sample_customer):
    """Erstellt eine Test-Rechnung"""
    invoice_data = {
        "customer_id": sample_customer["id"],
        "invoice_date": date.today().isoformat(),
    }
    response = client.post("/api/v1/invoices", json=invoice_data)
    return response.json()


@pytest.fixture
def sample_grow_plan(client):
    """Erstellt einen Test-Wachstumsplan"""
    plan_data = {
        "code": "GP-TEST",
        "name": "Test Wachstumsplan",
        "germination_days": 2,
        "growth_days": 8,
        "harvest_window_start_days": 9,
        "harvest_window_optimal_days": 11,
        "harvest_window_end_days": 14,
        "expected_yield_grams_per_tray": 350,
        "soak_hours": 8,
        "blackout_days": 3,
    }
    response = client.post("/api/v1/grow-plans", json=plan_data)
    return response.json()


@pytest.fixture
def sample_price_list(client):
    """Erstellt eine Test-Preisliste"""
    price_list_data = {
        "code": "PL-TEST",
        "name": "Test Preisliste",
        "currency": "EUR",
        "is_default": True,
    }
    response = client.post("/api/v1/price-lists", json=price_list_data)
    return response.json()
