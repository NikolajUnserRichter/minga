#!/usr/bin/env python3
"""
Seed Data Script für Minga-Greens ERP
Erstellt realistische Beispieldaten für Microgreens-Produktion.

Verwendung:
    python scripts/seed_data.py
    # oder via Docker:
    docker compose exec backend python scripts/seed_data.py
"""
import sys
import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

# Pfad für Imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.seed import Seed, SeedBatch
from app.models.production import GrowBatch, GrowBatchStatus, Harvest
from app.models.customer import Customer, CustomerType, Subscription, SubscriptionInterval, CustomerAddress, AddressType, PaymentTerms
from app.models.order import Order, OrderItem, OrderStatus
from app.models.capacity import Capacity, ResourceType
from app.models.unit import UnitOfMeasure, UnitCategory, UnitConversion
from app.models.product import Product, ProductGroup, GrowPlan, PriceList, PriceListItem, ProductCategory
from app.models.invoice import Invoice, InvoiceLine, Payment, InvoiceStatus, InvoiceType, TaxRate, PaymentMethod
from app.models.inventory import InventoryLocation, SeedInventory, FinishedGoodsInventory, PackagingInventory, LocationType, ArticleType


# ============== SEED DATA ==============

SEEDS_DATA = [
    {
        "name": "Sonnenblume",
        "sorte": "Black Oil",
        "lieferant": "BioSaat GmbH",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9,
        "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14,
        "ertrag_gramm_pro_tray": 350,
        "verlustquote_prozent": Decimal("5.0"),
    },
    {
        "name": "Erbse",
        "sorte": "Afila",
        "lieferant": "BioSaat GmbH",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 10,
        "erntefenster_min_tage": 11,
        "erntefenster_optimal_tage": 13,
        "erntefenster_max_tage": 16,
        "ertrag_gramm_pro_tray": 400,
        "verlustquote_prozent": Decimal("3.0"),
    },
    {
        "name": "Radieschen",
        "sorte": "Daikon",
        "lieferant": "SaatPur",
        "keimdauer_tage": 1,
        "wachstumsdauer_tage": 6,
        "erntefenster_min_tage": 6,
        "erntefenster_optimal_tage": 8,
        "erntefenster_max_tage": 10,
        "ertrag_gramm_pro_tray": 250,
        "verlustquote_prozent": Decimal("8.0"),
    },
    {
        "name": "Brokkoli",
        "sorte": "Calabrese",
        "lieferant": "SaatPur",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 7,
        "erntefenster_min_tage": 8,
        "erntefenster_optimal_tage": 10,
        "erntefenster_max_tage": 12,
        "ertrag_gramm_pro_tray": 200,
        "verlustquote_prozent": Decimal("10.0"),
    },
    {
        "name": "Senf",
        "sorte": "Gelber Senf",
        "lieferant": "BioSaat GmbH",
        "keimdauer_tage": 1,
        "wachstumsdauer_tage": 5,
        "erntefenster_min_tage": 5,
        "erntefenster_optimal_tage": 7,
        "erntefenster_max_tage": 9,
        "ertrag_gramm_pro_tray": 180,
        "verlustquote_prozent": Decimal("5.0"),
    },
    {
        "name": "Kresse",
        "sorte": "Gartenkresse",
        "lieferant": "SaatPur",
        "keimdauer_tage": 1,
        "wachstumsdauer_tage": 5,
        "erntefenster_min_tage": 5,
        "erntefenster_optimal_tage": 6,
        "erntefenster_max_tage": 8,
        "ertrag_gramm_pro_tray": 150,
        "verlustquote_prozent": Decimal("5.0"),
    },
    {
        "name": "Rucola",
        "sorte": "Wilde Rauke",
        "lieferant": "BioSaat GmbH",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9,
        "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14,
        "ertrag_gramm_pro_tray": 180,
        "verlustquote_prozent": Decimal("7.0"),
    },
    {
        "name": "Rotkohl",
        "sorte": "Red Acre",
        "lieferant": "SaatPur",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9,
        "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 13,
        "ertrag_gramm_pro_tray": 200,
        "verlustquote_prozent": Decimal("8.0"),
    },
]

CUSTOMERS_DATA = [
    {
        "name": "Restaurant Schumann",
        "typ": CustomerType.GASTRO,
        "email": "bestellung@schumann-muenchen.de",
        "telefon": "089 12345678",
        "adresse": "Maximilianstraße 15, 80539 München",
        "liefertage": [1, 3, 5],  # Di, Do, Sa
    },
    {
        "name": "BioMarkt Haidhausen",
        "typ": CustomerType.HANDEL,
        "email": "einkauf@biomarkt-haidhausen.de",
        "telefon": "089 23456789",
        "adresse": "Rosenheimer Straße 45, 81667 München",
        "liefertage": [0, 2, 4],  # Mo, Mi, Fr
    },
    {
        "name": "Hotel Bayerischer Hof",
        "typ": CustomerType.GASTRO,
        "email": "kueche@bayerischerhof.de",
        "telefon": "089 21200",
        "adresse": "Promenadeplatz 2-6, 80333 München",
        "liefertage": [1, 4],  # Di, Fr
    },
    {
        "name": "Café Frischlinge",
        "typ": CustomerType.GASTRO,
        "email": "info@cafe-frischlinge.de",
        "telefon": "089 34567890",
        "adresse": "Gärtnerplatz 6, 80469 München",
        "liefertage": [2, 5],  # Mi, Sa
    },
    {
        "name": "EDEKA Schwabing",
        "typ": CustomerType.HANDEL,
        "email": "frische@edeka-schwabing.de",
        "telefon": "089 45678901",
        "adresse": "Leopoldstraße 77, 80802 München",
        "liefertage": [0, 1, 2, 3, 4],  # Mo-Fr
    },
    {
        "name": "Kantine TechHub",
        "typ": CustomerType.GASTRO,
        "email": "catering@techhub-muc.de",
        "telefon": "089 56789012",
        "adresse": "Parkring 4, 85748 Garching",
        "liefertage": [0, 2, 4],  # Mo, Mi, Fr
    },
]

CAPACITIES_DATA = [
    {
        "ressource_typ": ResourceType.REGAL,
        "name": "Hauptregal",
        "max_kapazitaet": 50,
        "aktuell_belegt": 0,
    },
    {
        "ressource_typ": ResourceType.TRAY,
        "name": "Tray-Bestand",
        "max_kapazitaet": 200,
        "aktuell_belegt": 0,
    },
]


# ============== ERP SEED DATA ==============

UNITS_DATA = [
    {"code": "G", "name": "Gramm", "symbol": "g", "category": UnitCategory.WEIGHT, "base_factor": Decimal("1")},
    {"code": "KG", "name": "Kilogramm", "symbol": "kg", "category": UnitCategory.WEIGHT, "base_factor": Decimal("1000")},
    {"code": "STK", "name": "Stück", "symbol": "Stk", "category": UnitCategory.COUNT, "base_factor": Decimal("1")},
    {"code": "TRAY", "name": "Tray", "symbol": "Tray", "category": UnitCategory.CONTAINER, "base_factor": Decimal("1")},
    {"code": "SCHALE125", "name": "Schale 125g", "symbol": "Schale", "category": UnitCategory.CONTAINER, "base_factor": Decimal("1")},
    {"code": "SCHALE250", "name": "Schale 250g", "symbol": "Schale", "category": UnitCategory.CONTAINER, "base_factor": Decimal("1")},
    {"code": "BUND", "name": "Bund", "symbol": "Bd", "category": UnitCategory.COUNT, "base_factor": Decimal("1")},
]

PRODUCT_GROUPS_DATA = [
    {"code": "MG", "name": "Microgreens", "description": "Alle Microgreen-Produkte"},
    {"code": "SAATGUT", "name": "Saatgut", "description": "Saatgut für Verkauf"},
    {"code": "VERPACK", "name": "Verpackung", "description": "Verpackungsmaterial"},
]

GROW_PLANS_DATA = [
    {
        "code": "GP-SONNENBLUME",
        "name": "Sonnenblume Standard",
        "germination_days": 2,
        "growth_days": 8,
        "harvest_window_start_days": 9,
        "harvest_window_optimal_days": 11,
        "harvest_window_end_days": 14,
        "expected_yield_grams_per_tray": Decimal("350"),
        "soak_hours": 8,
        "blackout_days": 3,
        "seed_density_grams_per_tray": Decimal("120"),
        "optimal_temp_celsius": Decimal("21"),
        "optimal_humidity_percent": 65,
        "light_hours_per_day": 12,
    },
    {
        "code": "GP-ERBSE",
        "name": "Erbse Afila",
        "germination_days": 2,
        "growth_days": 10,
        "harvest_window_start_days": 11,
        "harvest_window_optimal_days": 13,
        "harvest_window_end_days": 16,
        "expected_yield_grams_per_tray": Decimal("400"),
        "soak_hours": 12,
        "blackout_days": 3,
        "seed_density_grams_per_tray": Decimal("180"),
        "optimal_temp_celsius": Decimal("18"),
        "optimal_humidity_percent": 60,
        "light_hours_per_day": 12,
    },
    {
        "code": "GP-RADIESCHEN",
        "name": "Radieschen Daikon",
        "germination_days": 1,
        "growth_days": 6,
        "harvest_window_start_days": 6,
        "harvest_window_optimal_days": 8,
        "harvest_window_end_days": 10,
        "expected_yield_grams_per_tray": Decimal("250"),
        "soak_hours": 4,
        "blackout_days": 2,
        "seed_density_grams_per_tray": Decimal("30"),
        "optimal_temp_celsius": Decimal("20"),
        "optimal_humidity_percent": 60,
        "light_hours_per_day": 10,
    },
    {
        "code": "GP-BROKKOLI",
        "name": "Brokkoli Calabrese",
        "germination_days": 2,
        "growth_days": 7,
        "harvest_window_start_days": 8,
        "harvest_window_optimal_days": 10,
        "harvest_window_end_days": 12,
        "expected_yield_grams_per_tray": Decimal("200"),
        "soak_hours": 4,
        "blackout_days": 2,
        "seed_density_grams_per_tray": Decimal("20"),
        "optimal_temp_celsius": Decimal("20"),
        "optimal_humidity_percent": 65,
        "light_hours_per_day": 12,
    },
    {
        "code": "GP-SENF",
        "name": "Gelber Senf",
        "germination_days": 1,
        "growth_days": 5,
        "harvest_window_start_days": 5,
        "harvest_window_optimal_days": 7,
        "harvest_window_end_days": 9,
        "expected_yield_grams_per_tray": Decimal("180"),
        "soak_hours": 0,
        "blackout_days": 2,
        "seed_density_grams_per_tray": Decimal("25"),
        "optimal_temp_celsius": Decimal("20"),
        "optimal_humidity_percent": 60,
        "light_hours_per_day": 10,
    },
]

LOCATIONS_DATA = [
    {"code": "LAGER-HAUPT", "name": "Hauptlager", "location_type": LocationType.LAGER, "description": "Trockenlager für Saatgut und Verpackung"},
    {"code": "KUEHL-1", "name": "Kühlraum 1", "location_type": LocationType.KUEHLRAUM, "description": "Kühlraum für Fertigware", "temperature_min": Decimal("2"), "temperature_max": Decimal("6")},
    {"code": "REGAL-A", "name": "Regalbereich A", "location_type": LocationType.REGAL, "description": "Wachstumsbereich A"},
    {"code": "REGAL-B", "name": "Regalbereich B", "location_type": LocationType.REGAL, "description": "Wachstumsbereich B"},
    {"code": "KEIM-1", "name": "Keimraum 1", "location_type": LocationType.KEIMRAUM, "description": "Dunkelphase"},
    {"code": "VERSAND", "name": "Versandbereich", "location_type": LocationType.VERSAND, "description": "Kommissionierung und Versand"},
]

PACKAGING_DATA = [
    {"article_number": "VP-SCHALE-125", "name": "Schale 125g mit Deckel", "min_quantity": Decimal("500"), "reorder_quantity": Decimal("2000")},
    {"article_number": "VP-SCHALE-250", "name": "Schale 250g mit Deckel", "min_quantity": Decimal("300"), "reorder_quantity": Decimal("1000")},
    {"article_number": "VP-KARTON-6", "name": "Versandkarton 6er", "min_quantity": Decimal("100"), "reorder_quantity": Decimal("500")},
    {"article_number": "VP-ETIKETTEN", "name": "Etiketten Rolle (1000 Stk)", "min_quantity": Decimal("5"), "reorder_quantity": Decimal("20")},
]


def create_seed_data(db: Session):
    """Erstellt Saatgut-Sorten und Chargen"""
    print("Erstelle Saatgut-Sorten...")

    seeds = []
    for seed_data in SEEDS_DATA:
        seed = Seed(**seed_data)
        db.add(seed)
        seeds.append(seed)

    db.flush()

    # Saatgut-Chargen erstellen
    print("Erstelle Saatgut-Chargen...")
    today = date.today()

    for i, seed in enumerate(seeds):
        batch = SeedBatch(
            seed_id=seed.id,
            charge_nummer=f"SB-2026-{i+1:03d}",
            menge_gramm=Decimal("5000"),
            verbleibend_gramm=Decimal("4500"),
            mhd=today + timedelta(days=365),
            lieferdatum=today - timedelta(days=30),
        )
        db.add(batch)

    return seeds


def create_customers(db: Session):
    """Erstellt Kunden"""
    print("Erstelle Kunden...")

    customers = []
    for customer_data in CUSTOMERS_DATA:
        customer = Customer(**customer_data)
        db.add(customer)
        customers.append(customer)

    return customers


def create_subscriptions(db: Session, seeds: list, customers: list):
    """Erstellt Abonnements für Stammkunden"""
    print("Erstelle Abonnements...")

    today = date.today()

    # Restaurant Schumann - Sonnenblume & Erbse
    db.add(Subscription(
        kunde_id=customers[0].id,
        seed_id=seeds[0].id,  # Sonnenblume
        menge=Decimal("500"),
        einheit="GRAMM",
        intervall=SubscriptionInterval.WOECHENTLICH,
        liefertage=[1, 3, 5],
        gueltig_von=today - timedelta(days=90),
    ))
    db.add(Subscription(
        kunde_id=customers[0].id,
        seed_id=seeds[1].id,  # Erbse
        menge=Decimal("300"),
        einheit="GRAMM",
        intervall=SubscriptionInterval.WOECHENTLICH,
        liefertage=[1, 5],
        gueltig_von=today - timedelta(days=60),
    ))

    # BioMarkt - Verschiedene Sorten
    for seed in seeds[:4]:
        db.add(Subscription(
            kunde_id=customers[1].id,
            seed_id=seed.id,
            menge=Decimal("400"),
            einheit="GRAMM",
            intervall=SubscriptionInterval.WOECHENTLICH,
            liefertage=[0, 2, 4],
            gueltig_von=today - timedelta(days=120),
        ))

    # Hotel Bayerischer Hof - Premium Sorten
    db.add(Subscription(
        kunde_id=customers[2].id,
        seed_id=seeds[0].id,  # Sonnenblume
        menge=Decimal("800"),
        einheit="GRAMM",
        intervall=SubscriptionInterval.WOECHENTLICH,
        liefertage=[1, 4],
        gueltig_von=today - timedelta(days=180),
    ))
    db.add(Subscription(
        kunde_id=customers[2].id,
        seed_id=seeds[3].id,  # Brokkoli
        menge=Decimal("400"),
        einheit="GRAMM",
        intervall=SubscriptionInterval.WOECHENTLICH,
        liefertage=[1, 4],
        gueltig_von=today - timedelta(days=180),
    ))


def create_grow_batches(db: Session, seeds: list):
    """Erstellt Wachstumschargen in verschiedenen Phasen"""
    print("Erstelle Wachstumschargen...")

    today = date.today()
    batches = []

    # Seed Batches holen
    seed_batches = {sb.seed_id: sb for sb in db.query(SeedBatch).all()}

    for seed in seeds[:5]:  # Erste 5 Sorten
        seed_batch = seed_batches.get(seed.id)
        if not seed_batch:
            continue

        # Charge in Keimung (heute ausgesät)
        batch1 = GrowBatch(
            seed_batch_id=seed_batch.id,
            tray_anzahl=8,
            aussaat_datum=today,
            erwartete_ernte_min=today + timedelta(days=seed.erntefenster_min_tage),
            erwartete_ernte_optimal=today + timedelta(days=seed.erntefenster_optimal_tage),
            erwartete_ernte_max=today + timedelta(days=seed.erntefenster_max_tage),
            status=GrowBatchStatus.KEIMUNG,
            regal_position=f"R1-{seeds.index(seed)+1}",
        )
        db.add(batch1)
        batches.append(batch1)

        # Charge in Wachstum (vor 5 Tagen ausgesät)
        batch2 = GrowBatch(
            seed_batch_id=seed_batch.id,
            tray_anzahl=10,
            aussaat_datum=today - timedelta(days=5),
            erwartete_ernte_min=today - timedelta(days=5) + timedelta(days=seed.erntefenster_min_tage),
            erwartete_ernte_optimal=today - timedelta(days=5) + timedelta(days=seed.erntefenster_optimal_tage),
            erwartete_ernte_max=today - timedelta(days=5) + timedelta(days=seed.erntefenster_max_tage),
            status=GrowBatchStatus.WACHSTUM,
            regal_position=f"R2-{seeds.index(seed)+1}",
        )
        db.add(batch2)
        batches.append(batch2)

        # Charge erntereif (optimal Erntefenster)
        days_back = seed.erntefenster_optimal_tage
        batch3 = GrowBatch(
            seed_batch_id=seed_batch.id,
            tray_anzahl=12,
            aussaat_datum=today - timedelta(days=days_back),
            erwartete_ernte_min=today - timedelta(days=days_back) + timedelta(days=seed.erntefenster_min_tage),
            erwartete_ernte_optimal=today - timedelta(days=days_back) + timedelta(days=seed.erntefenster_optimal_tage),
            erwartete_ernte_max=today - timedelta(days=days_back) + timedelta(days=seed.erntefenster_max_tage),
            status=GrowBatchStatus.ERNTEREIF,
            regal_position=f"R3-{seeds.index(seed)+1}",
        )
        db.add(batch3)
        batches.append(batch3)

    return batches


def create_orders(db: Session, seeds: list, customers: list):
    """Erstellt Beispiel-Bestellungen"""
    print("Erstelle Bestellungen...")

    today = date.today()

    # Offene Bestellung für morgen
    order1 = Order(
        kunde_id=customers[0].id,
        liefer_datum=today + timedelta(days=1),
        status=OrderStatus.OFFEN,
        notizen="Bitte früh liefern",
    )
    db.add(order1)
    db.flush()

    db.add(OrderItem(
        order_id=order1.id,
        seed_id=seeds[0].id,
        menge=Decimal("500"),
        einheit="GRAMM",
        preis_pro_einheit=Decimal("0.08"),
    ))
    db.add(OrderItem(
        order_id=order1.id,
        seed_id=seeds[1].id,
        menge=Decimal("300"),
        einheit="GRAMM",
        preis_pro_einheit=Decimal("0.10"),
    ))

    # Bestätigte Bestellung für übermorgen
    order2 = Order(
        kunde_id=customers[1].id,
        liefer_datum=today + timedelta(days=2),
        status=OrderStatus.BESTAETIGT,
    )
    db.add(order2)
    db.flush()

    for seed in seeds[:4]:
        db.add(OrderItem(
            order_id=order2.id,
            seed_id=seed.id,
            menge=Decimal("400"),
            einheit="GRAMM",
            preis_pro_einheit=Decimal("0.09"),
        ))

    # Historische Bestellungen (letzte 2 Wochen)
    for days_back in range(1, 15):
        order_date = today - timedelta(days=days_back)
        customer = customers[days_back % len(customers)]

        order = Order(
            kunde_id=customer.id,
            liefer_datum=order_date,
            status=OrderStatus.GELIEFERT,
            bestell_datum=order_date - timedelta(days=2),
        )
        db.add(order)
        db.flush()

        # 2-4 Positionen pro Bestellung
        for seed in seeds[:((days_back % 3) + 2)]:
            db.add(OrderItem(
                order_id=order.id,
                seed_id=seed.id,
                menge=Decimal(str(200 + (days_back * 50))),
                einheit="GRAMM",
                preis_pro_einheit=Decimal("0.08"),
            ))


def create_harvests(db: Session):
    """Erstellt historische Ernten"""
    print("Erstelle Ernten...")

    today = date.today()

    # Geerntete Chargen finden
    geerntete_batches = db.query(GrowBatch).filter(
        GrowBatch.status == GrowBatchStatus.ERNTEREIF
    ).all()

    for batch in geerntete_batches[:3]:
        # Eine Ernte pro Charge
        harvest = Harvest(
            grow_batch_id=batch.id,
            ernte_datum=today - timedelta(days=1),
            menge_gramm=Decimal(str(batch.tray_anzahl * 300)),
            verlust_gramm=Decimal(str(batch.tray_anzahl * 15)),
            qualitaet_note=4,
        )
        db.add(harvest)


def create_capacities(db: Session):
    """Erstellt Kapazitäts-Einträge"""
    print("Erstelle Kapazitäten...")

    for cap_data in CAPACITIES_DATA:
        capacity = Capacity(**cap_data)
        db.add(capacity)


# ============== ERP DATA CREATION ==============

def create_units(db: Session):
    """Erstellt Maßeinheiten"""
    print("Erstelle Maßeinheiten...")

    units = {}
    for unit_data in UNITS_DATA:
        unit = UnitOfMeasure(**unit_data)
        db.add(unit)
        units[unit_data["code"]] = unit

    return units


def create_product_groups(db: Session):
    """Erstellt Produktgruppen"""
    print("Erstelle Produktgruppen...")

    groups = {}
    for group_data in PRODUCT_GROUPS_DATA:
        group = ProductGroup(**group_data)
        db.add(group)
        groups[group_data["code"]] = group

    return groups


def create_grow_plans(db: Session):
    """Erstellt Wachstumspläne"""
    print("Erstelle Wachstumspläne...")

    plans = {}
    for plan_data in GROW_PLANS_DATA:
        plan = GrowPlan(**plan_data)
        db.add(plan)
        plans[plan_data["code"]] = plan

    return plans


def create_products(db: Session, seeds: list, units: dict, groups: dict, grow_plans: dict):
    """Erstellt Produkte aus Saatgut"""
    print("Erstelle Produkte...")

    products = []
    gram_unit = units.get("G")
    mg_group = groups.get("MG")

    plan_mapping = {
        "Sonnenblume": "GP-SONNENBLUME",
        "Erbse": "GP-ERBSE",
        "Radieschen": "GP-RADIESCHEN",
        "Brokkoli": "GP-BROKKOLI",
        "Senf": "GP-SENF",
    }

    for i, seed in enumerate(seeds):
        plan_code = plan_mapping.get(seed.name)
        grow_plan = grow_plans.get(plan_code) if plan_code else None

        product = Product(
            sku=f"MG-{i+1:04d}",
            name=f"{seed.name} Microgreens",
            category=ProductCategory.MICROGREEN,
            description=f"Frische {seed.name} Microgreens aus eigener Produktion",
            product_group_id=mg_group.id if mg_group else None,
            base_unit_id=gram_unit.id if gram_unit else None,
            base_price=Decimal("0.08"),  # 8 Cent pro Gramm
            tax_rate=TaxRate.REDUZIERT,
            seed_id=seed.id,
            grow_plan_id=grow_plan.id if grow_plan else None,
            seed_variety=seed.sorte,
            shelf_life_days=7,
            storage_temp_min=Decimal("2"),
            storage_temp_max=Decimal("6"),
            is_sellable=True,
        )
        db.add(product)
        products.append(product)

    return products


def create_price_lists(db: Session, products: list):
    """Erstellt Preislisten"""
    print("Erstelle Preislisten...")

    today = date.today()

    # Standard-Preisliste
    standard_list = PriceList(
        code="PL-STANDARD",
        name="Standardpreise 2026",
        description="Allgemeine Preisliste",
        currency="EUR",
        valid_from=today.replace(month=1, day=1),
        is_default=True,
    )
    db.add(standard_list)

    # Gastro-Preisliste (5% Rabatt)
    gastro_list = PriceList(
        code="PL-GASTRO",
        name="Gastronomie-Preise",
        description="Preisliste für Gastronomie-Kunden",
        currency="EUR",
        valid_from=today.replace(month=1, day=1),
    )
    db.add(gastro_list)

    # Großhandel-Preisliste (10% Rabatt)
    handel_list = PriceList(
        code="PL-HANDEL",
        name="Handel-Preise",
        description="Preisliste für Handelskunden",
        currency="EUR",
        valid_from=today.replace(month=1, day=1),
    )
    db.add(handel_list)

    db.flush()

    # Preise hinzufügen
    for product in products:
        base_price = product.base_price or Decimal("0.08")

        # Standard
        db.add(PriceListItem(
            price_list_id=standard_list.id,
            product_id=product.id,
            price=base_price,
            min_quantity=Decimal("1"),
        ))

        # Staffelpreis ab 500g
        db.add(PriceListItem(
            price_list_id=standard_list.id,
            product_id=product.id,
            price=base_price * Decimal("0.95"),  # 5% Rabatt
            min_quantity=Decimal("500"),
        ))

        # Gastro
        db.add(PriceListItem(
            price_list_id=gastro_list.id,
            product_id=product.id,
            price=base_price * Decimal("0.95"),
            min_quantity=Decimal("1"),
        ))

        # Handel
        db.add(PriceListItem(
            price_list_id=handel_list.id,
            product_id=product.id,
            price=base_price * Decimal("0.90"),
            min_quantity=Decimal("1"),
        ))

    return {"standard": standard_list, "gastro": gastro_list, "handel": handel_list}


def create_locations(db: Session):
    """Erstellt Lagerorte"""
    print("Erstelle Lagerorte...")

    locations = {}
    for loc_data in LOCATIONS_DATA:
        location = InventoryLocation(**loc_data)
        db.add(location)
        locations[loc_data["code"]] = location

    return locations


def create_packaging_inventory(db: Session, locations: dict):
    """Erstellt Verpackungsmaterial-Bestand"""
    print("Erstelle Verpackungsmaterial...")

    lager = locations.get("LAGER-HAUPT")

    for pack_data in PACKAGING_DATA:
        inventory = PackagingInventory(
            article_number=pack_data["article_number"],
            name=pack_data["name"],
            location_id=lager.id if lager else None,
            current_quantity=pack_data["min_quantity"] * Decimal("2"),  # Doppelter Mindestbestand
            unit="STK",
            min_quantity=pack_data["min_quantity"],
            reorder_quantity=pack_data["reorder_quantity"],
        )
        db.add(inventory)


def create_seed_inventory(db: Session, seeds: list, locations: dict):
    """Erstellt Saatgut-Bestand"""
    print("Erstelle Saatgut-Bestand im Lager...")

    lager = locations.get("LAGER-HAUPT")
    today = date.today()

    for i, seed in enumerate(seeds):
        inventory = SeedInventory(
            seed_id=seed.id,
            batch_number=f"SB-2026-{i+1:03d}",
            location_id=lager.id if lager else None,
            initial_quantity=Decimal("5000"),
            current_quantity=Decimal("4500"),
            unit="G",
            mhd=today + timedelta(days=365),
            supplier="BioSaat GmbH" if i % 2 == 0 else "SaatPur",
            purchase_price=Decimal("0.02"),  # 2 Cent pro Gramm
            is_organic=True,
            organic_certification="DE-ÖKO-006",
            min_quantity=Decimal("1000"),
        )
        db.add(inventory)


def update_customer_addresses(db: Session, customers: list, price_lists: dict):
    """Erweitert Kunden mit ERP-Daten"""
    print("Aktualisiere Kundendaten...")

    today = date.today()

    for i, customer in enumerate(customers):
        # Kundennummer generieren
        customer.customer_number = f"K-{2026}-{i+1:04d}"

        # Payment Terms setzen
        if customer.typ == CustomerType.GASTRO:
            customer.payment_terms = PaymentTerms.NET_14
            customer.price_list_id = price_lists["gastro"].id
        elif customer.typ == CustomerType.HANDEL:
            customer.payment_terms = PaymentTerms.NET_30
            customer.price_list_id = price_lists["handel"].id
        else:
            customer.payment_terms = PaymentTerms.PREPAID
            customer.price_list_id = price_lists["standard"].id

        # DATEV-Konto
        customer.datev_account = f"1{i+1:04d}"

        # Adresse aus String extrahieren und als CustomerAddress speichern
        if customer.adresse:
            parts = customer.adresse.split(", ")
            if len(parts) >= 2:
                strasse_teil = parts[0].rsplit(" ", 1)
                plz_ort = parts[1].split(" ", 1)

                address = CustomerAddress(
                    customer_id=customer.id,
                    address_type=AddressType.BOTH,
                    name=customer.name,
                    strasse=strasse_teil[0] if len(strasse_teil) > 0 else "",
                    hausnummer=strasse_teil[1] if len(strasse_teil) > 1 else "",
                    plz=plz_ort[0] if len(plz_ort) > 0 else "",
                    ort=plz_ort[1] if len(plz_ort) > 1 else "",
                    land="DE",
                )
                db.add(address)


def create_sample_invoices(db: Session, customers: list, products: list):
    """Erstellt Beispiel-Rechnungen"""
    print("Erstelle Beispiel-Rechnungen...")

    today = date.today()

    # Bezahlte Rechnung von letzter Woche
    invoice1 = Invoice(
        invoice_number=f"RE-2026-00001",
        invoice_type=InvoiceType.RECHNUNG,
        customer_id=customers[0].id,
        invoice_date=today - timedelta(days=7),
        delivery_date=today - timedelta(days=8),
        due_date=today - timedelta(days=7) + timedelta(days=14),
        status=InvoiceStatus.BEZAHLT,
        subtotal=Decimal("80.00"),
        tax_amount=Decimal("5.60"),
        total=Decimal("85.60"),
        paid_amount=Decimal("85.60"),
    )
    db.add(invoice1)
    db.flush()

    db.add(InvoiceLine(
        invoice_id=invoice1.id,
        position=1,
        product_id=products[0].id if products else None,
        description="Sonnenblume Microgreens",
        sku="MG-0001",
        quantity=Decimal("500"),
        unit="G",
        unit_price=Decimal("0.08"),
        tax_rate=TaxRate.REDUZIERT,
        line_total=Decimal("40.00"),
        tax_amount=Decimal("2.80"),
    ))
    db.add(InvoiceLine(
        invoice_id=invoice1.id,
        position=2,
        product_id=products[1].id if len(products) > 1 else None,
        description="Erbse Microgreens",
        sku="MG-0002",
        quantity=Decimal("500"),
        unit="G",
        unit_price=Decimal("0.08"),
        tax_rate=TaxRate.REDUZIERT,
        line_total=Decimal("40.00"),
        tax_amount=Decimal("2.80"),
    ))

    # Zahlung
    db.add(Payment(
        invoice_id=invoice1.id,
        payment_date=today - timedelta(days=3),
        amount=Decimal("85.60"),
        payment_method=PaymentMethod.UEBERWEISUNG,
        reference="RE-2026-00001",
    ))

    # Offene Rechnung
    invoice2 = Invoice(
        invoice_number=f"RE-2026-00002",
        invoice_type=InvoiceType.RECHNUNG,
        customer_id=customers[1].id,
        invoice_date=today - timedelta(days=2),
        delivery_date=today - timedelta(days=3),
        due_date=today + timedelta(days=28),
        status=InvoiceStatus.OFFEN,
        subtotal=Decimal("144.00"),
        tax_amount=Decimal("10.08"),
        total=Decimal("154.08"),
        paid_amount=Decimal("0"),
    )
    db.add(invoice2)
    db.flush()

    for i, product in enumerate(products[:4]):
        db.add(InvoiceLine(
            invoice_id=invoice2.id,
            position=i + 1,
            product_id=product.id,
            description=product.name,
            sku=product.sku,
            quantity=Decimal("450"),
            unit="G",
            unit_price=Decimal("0.08"),
            tax_rate=TaxRate.REDUZIERT,
            line_total=Decimal("36.00"),
            tax_amount=Decimal("2.52"),
        ))

    # Entwurf-Rechnung
    invoice3 = Invoice(
        invoice_number=f"RE-2026-00003",
        invoice_type=InvoiceType.RECHNUNG,
        customer_id=customers[2].id,
        invoice_date=today,
        due_date=today + timedelta(days=14),
        status=InvoiceStatus.ENTWURF,
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("0"),
    )
    db.add(invoice3)


def main():
    """Hauptfunktion - erstellt alle Seed-Daten"""
    print("=" * 50)
    print("Minga-Greens ERP - Seed Data")
    print("=" * 50)

    # Tabellen erstellen falls nicht vorhanden
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Prüfen ob bereits Daten existieren
        existing_seeds = db.query(Seed).count()
        if existing_seeds > 0:
            print(f"\nWarnung: Datenbank enthält bereits {existing_seeds} Saatgut-Sorten.")
            response = input("Fortfahren und Daten hinzufügen? (j/n): ")
            if response.lower() != "j":
                print("Abgebrochen.")
                return

        # Basis-Daten erstellen
        seeds = create_seed_data(db)
        db.flush()

        customers = create_customers(db)
        db.flush()

        create_subscriptions(db, seeds, customers)
        create_grow_batches(db, seeds)
        create_orders(db, seeds, customers)
        create_harvests(db)
        create_capacities(db)
        db.flush()

        # ERP-Daten erstellen
        print("\n--- ERP-Module ---")
        units = create_units(db)
        db.flush()

        groups = create_product_groups(db)
        db.flush()

        grow_plans = create_grow_plans(db)
        db.flush()

        products = create_products(db, seeds, units, groups, grow_plans)
        db.flush()

        price_lists = create_price_lists(db, products)
        db.flush()

        locations = create_locations(db)
        db.flush()

        create_packaging_inventory(db, locations)
        create_seed_inventory(db, seeds, locations)
        db.flush()

        update_customer_addresses(db, customers, price_lists)
        db.flush()

        create_sample_invoices(db, customers, products)

        # Commit
        db.commit()

        print("\n" + "=" * 50)
        print("Seed-Daten erfolgreich erstellt!")
        print("=" * 50)
        print(f"  - {len(seeds)} Saatgut-Sorten")
        print(f"  - {len(customers)} Kunden")
        print(f"  - {len(products)} Produkte")
        print(f"  - {len(units)} Maßeinheiten")
        print(f"  - {len(grow_plans)} Wachstumspläne")
        print(f"  - {len(price_lists)} Preislisten")
        print(f"  - {len(locations)} Lagerorte")
        print(f"  - Abonnements, Chargen, Bestellungen, Rechnungen...")
        print("\nSystem bereit für Tests!")

    except Exception as e:
        db.rollback()
        print(f"\nFehler: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
