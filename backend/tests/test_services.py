"""
Service Layer Tests
Tests für Business Logic
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.seed import Seed, SeedBatch
from app.models.customer import Customer, CustomerType
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, TaxRate
from app.services.invoice_service import InvoiceService
from app.services.inventory_service import InventoryService


# Test-Datenbank
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Datenbankverbindung für Tests"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_customer_model(db):
    """Erstellt einen Test-Kunden direkt in der DB"""
    customer = Customer(
        name="Test Kunde",
        typ=CustomerType.GASTRO,
        email="test@example.com",
        liefertage=[1, 3, 5],
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@pytest.fixture
def sample_seed_model(db):
    """Erstellt ein Test-Saatgut direkt in der DB"""
    seed = Seed(
        name="Sonnenblume",
        keimdauer_tage=2,
        wachstumsdauer_tage=8,
        erntefenster_min_tage=9,
        erntefenster_optimal_tage=11,
        erntefenster_max_tage=14,
        ertrag_gramm_pro_tray=Decimal("350"),
    )
    db.add(seed)
    db.commit()
    db.refresh(seed)
    return seed


class TestInvoiceService:
    """Tests für InvoiceService"""

    def test_create_invoice(self, db, sample_customer_model):
        """Test: Rechnung erstellen"""
        service = InvoiceService(db)
        invoice = service.create_invoice(
            customer_id=sample_customer_model.id,
            invoice_date=date.today(),
        )

        assert invoice is not None
        assert invoice.customer_id == sample_customer_model.id
        assert invoice.status == InvoiceStatus.ENTWURF
        assert invoice.invoice_number.startswith("RE-")

    def test_invoice_number_generation(self, db, sample_customer_model):
        """Test: Rechnungsnummern werden korrekt generiert"""
        service = InvoiceService(db)

        invoice1 = service.create_invoice(customer_id=sample_customer_model.id)
        invoice2 = service.create_invoice(customer_id=sample_customer_model.id)
        invoice3 = service.create_invoice(customer_id=sample_customer_model.id)
        db.commit()

        # Nummern sollten sequenziell sein
        assert invoice1.invoice_number != invoice2.invoice_number
        assert invoice2.invoice_number != invoice3.invoice_number

    def test_add_line_calculates_totals(self, db, sample_customer_model):
        """Test: Positionen berechnen Summen korrekt"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        line = service.add_line(
            invoice_id=invoice.id,
            description="Sonnenblume Microgreens",
            quantity=Decimal("500"),
            unit="G",
            unit_price=Decimal("0.08"),
            tax_rate=TaxRate.REDUZIERT,
        )
        db.flush()

        # 500 * 0.08 = 40.00
        assert line.line_total == Decimal("40.00")
        # 7% von 40.00 = 2.80
        assert line.tax_amount == Decimal("2.80")

    def test_invoice_totals_update(self, db, sample_customer_model):
        """Test: Rechnungssummen werden aktualisiert"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Produkt 1",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
            tax_rate=TaxRate.REDUZIERT,
        )
        service.add_line(
            invoice_id=invoice.id,
            description="Produkt 2",
            quantity=Decimal("50"),
            unit="G",
            unit_price=Decimal("2.00"),
            tax_rate=TaxRate.REDUZIERT,
        )
        db.flush()
        db.refresh(invoice)

        # 100 + 100 = 200 Netto
        assert invoice.subtotal == Decimal("200.00")
        # 7% von 200 = 14
        assert invoice.tax_amount == Decimal("14.00")
        # Brutto
        assert invoice.total == Decimal("214.00")

    def test_finalize_invoice(self, db, sample_customer_model):
        """Test: Rechnung finalisieren"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
        )
        db.flush()

        finalized = service.finalize_invoice(invoice.id)

        assert finalized.status == InvoiceStatus.OFFEN
        assert finalized.due_date is not None

    def test_finalize_empty_invoice_fails(self, db, sample_customer_model):
        """Test: Leere Rechnung kann nicht finalisiert werden"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        with pytest.raises(ValueError) as exc_info:
            service.finalize_invoice(invoice.id)

        assert "keine Positionen" in str(exc_info.value).lower()

    def test_record_partial_payment(self, db, sample_customer_model):
        """Test: Teilzahlung erfassen"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
        )
        service.finalize_invoice(invoice.id)
        db.flush()

        # Teilzahlung
        payment = service.record_payment(
            invoice_id=invoice.id,
            amount=Decimal("50.00"),
            payment_method="UEBERWEISUNG",
        )
        db.refresh(invoice)

        assert payment is not None
        assert invoice.paid_amount == Decimal("50.00")
        assert invoice.status == InvoiceStatus.TEILBEZAHLT

    def test_record_full_payment(self, db, sample_customer_model):
        """Test: Vollständige Zahlung"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
        )
        service.finalize_invoice(invoice.id)
        db.flush()
        db.refresh(invoice)

        # Volle Zahlung
        service.record_payment(
            invoice_id=invoice.id,
            amount=invoice.total,
            payment_method="UEBERWEISUNG",
        )
        db.refresh(invoice)

        assert invoice.status == InvoiceStatus.BEZAHLT

    def test_cancel_invoice_creates_credit_note(self, db, sample_customer_model):
        """Test: Stornierung erstellt Gutschrift"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
        )
        service.finalize_invoice(invoice.id)
        db.flush()

        cancelled, credit_note = service.cancel_invoice(
            invoice_id=invoice.id,
            reason="Storno Test",
            create_credit_note=True,
        )
        db.flush()

        assert cancelled.status == InvoiceStatus.STORNIERT
        assert credit_note is not None
        assert credit_note.invoice_type.value == "GUTSCHRIFT"

    def test_check_overdue_invoices(self, db, sample_customer_model):
        """Test: Überfällige Rechnungen erkennen"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
        )
        service.finalize_invoice(invoice.id)
        db.flush()

        # Fälligkeitsdatum in Vergangenheit setzen
        invoice.due_date = date.today() - timedelta(days=1)
        db.commit()

        overdue = service.check_overdue_invoices()

        assert len(overdue) == 1
        assert overdue[0].id == invoice.id
        assert overdue[0].status == InvoiceStatus.UEBERFAELLIG


class TestCalculations:
    """Tests für Berechnungslogik"""

    def test_tax_calculation_standard(self, db, sample_customer_model):
        """Test: Standardsteuer (19%)"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        line = service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="STK",
            unit_price=Decimal("1.00"),
            tax_rate=TaxRate.STANDARD,
        )

        # 19% von 100 = 19
        assert line.tax_amount == Decimal("19.00")

    def test_tax_calculation_reduced(self, db, sample_customer_model):
        """Test: Ermäßigte Steuer (7%)"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        line = service.add_line(
            invoice_id=invoice.id,
            description="Lebensmittel",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
            tax_rate=TaxRate.REDUZIERT,
        )

        # 7% von 100 = 7
        assert line.tax_amount == Decimal("7.00")

    def test_tax_calculation_exempt(self, db, sample_customer_model):
        """Test: Steuerfrei (0%)"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        line = service.add_line(
            invoice_id=invoice.id,
            description="Steuerfreie Leistung",
            quantity=Decimal("100"),
            unit="STK",
            unit_price=Decimal("1.00"),
            tax_rate=TaxRate.STEUERFREI,
        )

        assert line.tax_amount == Decimal("0.00")

    def test_discount_calculation(self, db, sample_customer_model):
        """Test: Rabatt auf Position"""
        service = InvoiceService(db)
        invoice = service.create_invoice(customer_id=sample_customer_model.id)
        db.flush()

        line = service.add_line(
            invoice_id=invoice.id,
            description="Test",
            quantity=Decimal("100"),
            unit="G",
            unit_price=Decimal("1.00"),
            discount_percent=Decimal("10"),  # 10% Rabatt
        )

        # 100 * 1.00 * 0.90 = 90
        assert line.line_total == Decimal("90.00")
