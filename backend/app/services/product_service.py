from typing import Optional
"""
Produkt-Service - Business Logic für Produkte, GrowPlans und Preislisten
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from app.models.product import (
    Product, ProductGroup, GrowPlan, PriceList, PriceListItem,
    ProductCategory
)
from app.models.unit import UnitOfMeasure
from app.models.seed import Seed
from app.models.customer import Customer
from app.models.enums import TaxRate


class ProductService:
    """Service für Produkt-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================
    # PRODUCTS
    # ========================================

    def create_product(
        self,
        sku: str,
        name: str,
        category: ProductCategory,
        description: Optional[str] = None,
        product_group_id: Optional[UUID] = None,
        base_unit_id: Optional[UUID] = None,
        base_price: Optional[Decimal] = None,
        tax_rate: TaxRate = TaxRate.REDUZIERT,
        seed_id: Optional[UUID] = None,
        grow_plan_id: Optional[UUID] = None,
        seed_variety: Optional[str] = None,
        shelf_life_days: Optional[int] = None,
        storage_temp_min: Optional[Decimal] = None,
        storage_temp_max: Optional[Decimal] = None,
        min_stock_quantity: Optional[Decimal] = None,
        is_bundle: bool = False,
        bundle_components: Optional[list[dict]] = None,
    ) -> Product:
        """
        Erstellt ein neues Produkt.
        """
        # SKU-Eindeutigkeit prüfen
        existing = self.db.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"SKU '{sku}' existiert bereits")

        product = Product(
            sku=sku,
            name=name,
            category=category,
            description=description,
            product_group_id=product_group_id,
            base_unit_id=base_unit_id,
            base_price=base_price,
            tax_rate=tax_rate,
            seed_id=seed_id,
            grow_plan_id=grow_plan_id,
            seed_variety=seed_variety,
            shelf_life_days=shelf_life_days,
            storage_temp_min=storage_temp_min,
            storage_temp_max=storage_temp_max,
            min_stock_level=min_stock_quantity,
            is_bundle=is_bundle,
            bundle_components=bundle_components,
        )

        self.db.add(product)
        return product

    def create_microgreen_product(
        self,
        seed_id: UUID,
        grow_plan_id: UUID,
        base_price: Decimal,
        sku_prefix: str = "MG",
    ) -> Product:
        """
        Erstellt ein Microgreen-Produkt aus Seed und GrowPlan.
        """
        seed = self.db.get(Seed, seed_id)
        if not seed:
            raise ValueError("Saatgut nicht gefunden")

        grow_plan = self.db.get(GrowPlan, grow_plan_id)
        if not grow_plan:
            raise ValueError("Wachstumsplan nicht gefunden")

        # SKU generieren
        count = self.db.execute(
            select(func.count(Product.id))
            .where(Product.sku.like(f"{sku_prefix}-%"))
        ).scalar() or 0
        sku = f"{sku_prefix}-{count + 1:04d}"

        # Basis-Einheit (Gramm) finden
        gram_unit = self.db.execute(
            select(UnitOfMeasure).where(UnitOfMeasure.code == "G")
        ).scalar_one_or_none()

        return self.create_product(
            sku=sku,
            name=f"{seed.name} Microgreens",
            category=ProductCategory.MICROGREEN,
            seed_id=seed_id,
            grow_plan_id=grow_plan_id,
            seed_variety=seed.sorte,
            base_unit_id=gram_unit.id if gram_unit else None,
            base_price=base_price,
            tax_rate=TaxRate.REDUZIERT,  # Lebensmittel 7%
            shelf_life_days=7,
            storage_temp_min=Decimal("2"),
            storage_temp_max=Decimal("6"),
        )

    def create_bundle(
        self,
        sku: str,
        name: str,
        components: list[dict],  # [{"product_id": ..., "quantity": ...}, ...]
        base_price: Optional[Decimal] = None,
    ) -> Product:
        """
        Erstellt ein Bundle-Produkt aus mehreren Komponenten.
        """
        # Komponenten validieren
        for comp in components:
            product = self.db.get(Product, comp["product_id"])
            if not product:
                raise ValueError(f"Produkt {comp['product_id']} nicht gefunden")

        # Preis berechnen wenn nicht angegeben
        if base_price is None:
            total = Decimal("0")
            for comp in components:
                product = self.db.get(Product, comp["product_id"])
                if product.base_price:
                    total += product.base_price * Decimal(str(comp["quantity"]))
            base_price = total * Decimal("0.9")  # 10% Bundle-Rabatt

        return self.create_product(
            sku=sku,
            name=name,
            category=ProductCategory.BUNDLE,
            base_price=base_price,
            is_bundle=True,
            bundle_components=components,
        )

    def get_product_price(
        self,
        product_id: UUID,
        customer_id: Optional[UUID] = None,
        quantity: Decimal = Decimal("1"),
        price_date: Optional[date] = None,
    ) -> Decimal:
        """
        Ermittelt den Preis für ein Produkt.
        Berücksichtigt Kundenpreisliste und Staffelpreise.
        """
        product = self.db.get(Product, product_id)
        if not product:
            raise ValueError("Produkt nicht gefunden")

        check_date = price_date or date.today()
        price = product.base_price or Decimal("0")

        # Kundenspezifische Preisliste prüfen
        if customer_id:
            customer = self.db.get(Customer, customer_id)
            if customer and customer.price_list_id:
                # Preis aus Preisliste holen
                price_item = self.db.execute(
                    select(PriceListItem)
                    .where(
                        PriceListItem.price_list_id == customer.price_list_id,
                        PriceListItem.product_id == product_id,
                        PriceListItem.is_active == True,
                        PriceListItem.min_quantity <= quantity,
                        (PriceListItem.valid_from == None) | (PriceListItem.valid_from <= check_date),
                        (PriceListItem.valid_until == None) | (PriceListItem.valid_until >= check_date),
                    )
                    .order_by(PriceListItem.min_quantity.desc())
                    .limit(1)
                ).scalar_one_or_none()

                if price_item:
                    price = price_item.price

                # Kundenrabatt anwenden
                if customer.discount_percent > 0:
                    discount = price * customer.discount_percent / 100
                    price -= discount

        return price

    # ========================================
    # GROW PLANS
    # ========================================

    def create_grow_plan(
        self,
        code: str,
        name: str,
        germination_days: int,
        growth_days: int,
        harvest_window_start_days: int,
        harvest_window_optimal_days: int,
        harvest_window_end_days: int,
        expected_yield_grams_per_tray: Decimal,
        soak_hours: int = 0,
        blackout_days: int = 0,
        expected_loss_percent: Decimal = Decimal("5"),
        description: Optional[str] = None,
        optimal_temp_celsius: Optional[Decimal] = None,
        optimal_humidity_percent: Optional[int] = None,
        light_hours_per_day: Optional[int] = None,
        seed_density_grams_per_tray: Optional[Decimal] = None,
    ) -> GrowPlan:
        """
        Erstellt einen neuen Wachstumsplan.
        """
        # Code-Eindeutigkeit prüfen
        existing = self.db.execute(
            select(GrowPlan).where(GrowPlan.code == code)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"GrowPlan-Code '{code}' existiert bereits")

        # Validierung Erntefenster
        if not (harvest_window_start_days <= harvest_window_optimal_days <= harvest_window_end_days):
            raise ValueError("Erntefenster-Tage müssen aufsteigend sein")

        grow_plan = GrowPlan(
            code=code,
            name=name,
            description=description,
            soak_hours=soak_hours,
            blackout_days=blackout_days,
            germination_days=germination_days,
            growth_days=growth_days,
            harvest_window_start_days=harvest_window_start_days,
            harvest_window_optimal_days=harvest_window_optimal_days,
            harvest_window_end_days=harvest_window_end_days,
            expected_yield_grams_per_tray=expected_yield_grams_per_tray,
            expected_loss_percent=expected_loss_percent,
            temp_growth_celsius=optimal_temp_celsius,
            humidity_percent=optimal_humidity_percent,
            light_hours_per_day=light_hours_per_day,
            seed_density_grams_per_tray=seed_density_grams_per_tray,
        )

        self.db.add(grow_plan)
        return grow_plan

    def calculate_sow_date(
        self,
        grow_plan_id: UUID,
        target_harvest_date: date,
    ) -> date:
        """
        Berechnet das Aussaat-Datum für ein gewünschtes Erntedatum.
        """
        grow_plan = self.db.get(GrowPlan, grow_plan_id)
        if not grow_plan:
            raise ValueError("Wachstumsplan nicht gefunden")

        return grow_plan.calculate_sow_date(target_harvest_date)

    def calculate_harvest_window(
        self,
        grow_plan_id: UUID,
        sow_date: date,
    ) -> tuple[date, date, date]:
        """
        Berechnet das Erntefenster für ein Aussaat-Datum.
        Gibt (start, optimal, end) zurück.
        """
        grow_plan = self.db.get(GrowPlan, grow_plan_id)
        if not grow_plan:
            raise ValueError("Wachstumsplan nicht gefunden")

        return grow_plan.calculate_harvest_window(sow_date)

    # ========================================
    # PRICE LISTS
    # ========================================

    def create_price_list(
        self,
        code: str,
        name: str,
        description: Optional[str] = None,
        currency: str = "EUR",
        valid_from: Optional[date] = None,
        valid_until: Optional[date] = None,
        is_default: bool = False,
    ) -> PriceList:
        """
        Erstellt eine neue Preisliste.
        """
        # Code-Eindeutigkeit prüfen
        existing = self.db.execute(
            select(PriceList).where(PriceList.code == code)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Preislisten-Code '{code}' existiert bereits")

        # Wenn default, andere auf non-default setzen
        if is_default:
            self.db.execute(
                select(PriceList)
                .where(PriceList.is_default == True)
            )
            for pl in self.db.execute(select(PriceList).where(PriceList.is_default == True)).scalars():
                pl.is_default = False

        price_list = PriceList(
            code=code,
            name=name,
            description=description,
            currency=currency,
            valid_from=valid_from,
            valid_until=valid_until,
            is_default=is_default,
        )

        self.db.add(price_list)
        return price_list

    def add_price_list_item(
        self,
        price_list_id: UUID,
        product_id: UUID,
        price: Decimal,
        unit_id: Optional[UUID] = None,
        min_quantity: Decimal = Decimal("1"),
        valid_from: Optional[date] = None,
        valid_until: Optional[date] = None,
    ) -> PriceListItem:
        """
        Fügt einen Preis zur Preisliste hinzu.
        """
        price_list = self.db.get(PriceList, price_list_id)
        if not price_list:
            raise ValueError("Preisliste nicht gefunden")

        product = self.db.get(Product, product_id)
        if not product:
            raise ValueError("Produkt nicht gefunden")

        if unit_id is None:
            unit_id = product.base_unit_id

        item = PriceListItem(
            price_list_id=price_list_id,
            product_id=product_id,
            unit_id=unit_id,
            price=price,
            min_quantity=min_quantity,
            valid_from=valid_from,
            valid_until=valid_until,
        )

        self.db.add(item)
        return item

    def copy_price_list(
        self,
        source_id: UUID,
        new_code: str,
        new_name: str,
        price_adjustment_percent: Decimal = Decimal("0"),
    ) -> PriceList:
        """
        Kopiert eine Preisliste mit optionaler Preisanpassung.
        """
        source = self.db.get(PriceList, source_id)
        if not source:
            raise ValueError("Quell-Preisliste nicht gefunden")

        new_list = self.create_price_list(
            code=new_code,
            name=new_name,
            description=f"Kopie von {source.name}",
            currency=source.currency,
        )

        self.db.flush()

        # Preise kopieren
        for item in source.items:
            new_price = item.price
            if price_adjustment_percent != 0:
                new_price = item.price * (1 + price_adjustment_percent / 100)

            self.add_price_list_item(
                price_list_id=new_list.id,
                product_id=item.product_id,
                price=new_price,
                unit_id=item.unit_id,
                min_quantity=item.min_quantity,
            )

        return new_list

    # ========================================
    # PRODUCT GROUPS
    # ========================================

    def create_product_group(
        self,
        code: str,
        name: str,
        parent_id: Optional[UUID] = None,
        description: Optional[str] = None,
    ) -> ProductGroup:
        """
        Erstellt eine neue Produktgruppe.
        """
        existing = self.db.execute(
            select(ProductGroup).where(ProductGroup.code == code)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Produktgruppen-Code '{code}' existiert bereits")

        group = ProductGroup(
            code=code,
            name=name,
            parent_id=parent_id,
            description=description,
        )

        self.db.add(group)
        return group

    # ========================================
    # STATISTICS
    # ========================================

    def get_product_statistics(self) -> dict:
        """
        Gibt Produktstatistiken zurück.
        """
        total = self.db.execute(
            select(func.count(Product.id)).where(Product.is_active == True)
        ).scalar() or 0

        by_category = self.db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.is_active == True)
            .group_by(Product.category)
        ).all()

        sellable = self.db.execute(
            select(func.count(Product.id))
            .where(Product.is_active == True, Product.is_sellable == True)
        ).scalar() or 0

        with_grow_plan = self.db.execute(
            select(func.count(Product.id))
            .where(Product.is_active == True, Product.grow_plan_id != None)
        ).scalar() or 0

        return {
            "total_products": total,
            "sellable_products": sellable,
            "with_grow_plan": with_grow_plan,
            "by_category": {cat.value: count for cat, count in by_category},
        }
