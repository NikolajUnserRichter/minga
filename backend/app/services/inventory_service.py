"""
Lager-Service - Business Logic für Lagerverwaltung
Mit vollständiger Rückverfolgbarkeit
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_

from app.models.inventory import (
    InventoryLocation, SeedInventory, FinishedGoodsInventory,
    PackagingInventory, InventoryMovement, InventoryCount, InventoryCountItem,
    LocationType, MovementType, InventoryItemType
)
from app.models.production import GrowBatch, Harvest
from app.models.product import Product
from app.models.seed import Seed
from app.models.order import Order, OrderItem


class InventoryService:
    """Service für Lagerverwaltungs-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================
    # SEED INVENTORY
    # ========================================

    def receive_seed_batch(
        self,
        seed_id: UUID,
        batch_number: str,
        quantity_kg: Decimal,
        received_date: date | None = None,
        best_before_date: date | None = None,
        supplier_name: str | None = None,
        supplier_batch: str | None = None,
        purchase_price_per_kg: Decimal | None = None,
        location_id: UUID | None = None,
        is_organic: bool = False,
        organic_certificate: str | None = None,
        germination_rate: Decimal | None = None,
    ) -> SeedInventory:
        """
        Erfasst einen neuen Saatgut-Wareneingang.
        """
        seed = self.db.get(Seed, seed_id)
        if not seed:
            raise ValueError("Saatgut nicht gefunden")

        inventory = SeedInventory(
            seed_id=seed_id,
            batch_number=batch_number,
            supplier_batch=supplier_batch,
            initial_quantity_kg=quantity_kg,
            current_quantity_kg=quantity_kg,
            received_date=received_date or date.today(),
            best_before_date=best_before_date,
            supplier_name=supplier_name,
            purchase_price_per_kg=purchase_price_per_kg,
            location_id=location_id,
            is_organic=is_organic,
            organic_certificate=organic_certificate,
            germination_rate=germination_rate,
        )

        self.db.add(inventory)
        self.db.flush()

        # Lagerbewegung erfassen
        self._record_movement(
            movement_type=MovementType.EINGANG,
            item_type=InventoryItemType.SAATGUT,
            seed_inventory_id=inventory.id,
            quantity=quantity_kg,
            unit="kg",
            quantity_before=Decimal("0"),
            quantity_after=quantity_kg,
            to_location_id=location_id,
            reference_number=batch_number,
        )

        return inventory

    def consume_seed_for_sowing(
        self,
        seed_inventory_id: UUID,
        quantity_kg: Decimal,
        grow_batch_id: UUID,
        created_by: str | None = None,
    ) -> InventoryMovement:
        """
        Verbucht Saatgut-Verbrauch für eine Aussaat.
        """
        inventory = self.db.get(SeedInventory, seed_inventory_id)
        if not inventory:
            raise ValueError("Saatgut-Bestand nicht gefunden")

        if inventory.is_blocked:
            raise ValueError(f"Saatgut ist gesperrt: {inventory.block_reason}")

        if inventory.current_quantity_kg < quantity_kg:
            raise ValueError(
                f"Nicht genug Saatgut verfügbar. "
                f"Benötigt: {quantity_kg}kg, Verfügbar: {inventory.current_quantity_kg}kg"
            )

        quantity_before = inventory.current_quantity_kg
        inventory.current_quantity_kg -= quantity_kg

        movement = self._record_movement(
            movement_type=MovementType.PRODUKTION,
            item_type=InventoryItemType.SAATGUT,
            seed_inventory_id=seed_inventory_id,
            quantity=-quantity_kg,
            unit="kg",
            quantity_before=quantity_before,
            quantity_after=inventory.current_quantity_kg,
            from_location_id=inventory.location_id,
            grow_batch_id=grow_batch_id,
            created_by=created_by,
        )

        return movement

    # ========================================
    # FINISHED GOODS INVENTORY
    # ========================================

    def receive_harvest(
        self,
        product_id: UUID,
        batch_number: str,
        quantity_g: Decimal,
        harvest_date: date,
        harvest_id: UUID | None = None,
        grow_batch_id: UUID | None = None,
        seed_inventory_id: UUID | None = None,
        shelf_life_days: int = 7,
        quality_grade: int | None = None,
        location_id: UUID | None = None,
        created_by: str | None = None,
    ) -> FinishedGoodsInventory:
        """
        Erfasst geerntete Ware im Lager.
        Stellt Rückverfolgungskette her.
        """
        product = self.db.get(Product, product_id)
        if not product:
            raise ValueError("Produkt nicht gefunden")

        best_before = harvest_date + timedelta(days=shelf_life_days)

        # Rückverfolgung: GrowBatch -> SeedInventory falls nicht angegeben
        if grow_batch_id and not seed_inventory_id:
            grow_batch = self.db.get(GrowBatch, grow_batch_id)
            if grow_batch and grow_batch.seed_batch:
                # Versuche SeedInventory zu finden
                seed_inv = self.db.execute(
                    select(SeedInventory)
                    .where(SeedInventory.seed_id == grow_batch.seed_batch.seed_id)
                    .order_by(SeedInventory.received_date.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if seed_inv:
                    seed_inventory_id = seed_inv.id

        inventory = FinishedGoodsInventory(
            product_id=product_id,
            batch_number=batch_number,
            harvest_id=harvest_id,
            grow_batch_id=grow_batch_id,
            seed_inventory_id=seed_inventory_id,
            initial_quantity_g=quantity_g,
            current_quantity_g=quantity_g,
            quality_grade=quality_grade,
            harvest_date=harvest_date,
            best_before_date=best_before,
            location_id=location_id,
        )

        self.db.add(inventory)
        self.db.flush()

        # Lagerbewegung erfassen
        self._record_movement(
            movement_type=MovementType.ERNTE,
            item_type=InventoryItemType.FERTIGWARE,
            finished_goods_id=inventory.id,
            quantity=quantity_g,
            unit="g",
            quantity_before=Decimal("0"),
            quantity_after=quantity_g,
            to_location_id=location_id,
            harvest_id=harvest_id,
            grow_batch_id=grow_batch_id,
            created_by=created_by,
            reference_number=batch_number,
        )

        return inventory

    def reserve_for_order(
        self,
        finished_goods_id: UUID,
        order_id: UUID,
    ) -> FinishedGoodsInventory:
        """
        Reserviert Fertigware für eine Bestellung.
        """
        inventory = self.db.get(FinishedGoodsInventory, finished_goods_id)
        if not inventory:
            raise ValueError("Fertigwaren-Bestand nicht gefunden")

        if inventory.is_reserved:
            raise ValueError("Ware ist bereits reserviert")

        inventory.is_reserved = True
        inventory.reserved_order_id = order_id

        return inventory

    def ship_goods(
        self,
        finished_goods_id: UUID,
        quantity_g: Decimal,
        order_id: UUID,
        order_item_id: UUID | None = None,
        created_by: str | None = None,
    ) -> InventoryMovement:
        """
        Verbucht Warenausgang für Lieferung.
        """
        inventory = self.db.get(FinishedGoodsInventory, finished_goods_id)
        if not inventory:
            raise ValueError("Fertigwaren-Bestand nicht gefunden")

        if inventory.current_quantity_g < quantity_g:
            raise ValueError(
                f"Nicht genug Ware verfügbar. "
                f"Benötigt: {quantity_g}g, Verfügbar: {inventory.current_quantity_g}g"
            )

        quantity_before = inventory.current_quantity_g
        inventory.current_quantity_g -= quantity_g

        # Reservierung aufheben wenn komplett ausgeliefert
        if inventory.current_quantity_g == 0:
            inventory.is_reserved = False
            inventory.reserved_order_id = None
            inventory.is_active = False

        movement = self._record_movement(
            movement_type=MovementType.AUSGANG,
            item_type=InventoryItemType.FERTIGWARE,
            finished_goods_id=finished_goods_id,
            quantity=-quantity_g,
            unit="g",
            quantity_before=quantity_before,
            quantity_after=inventory.current_quantity_g,
            from_location_id=inventory.location_id,
            order_id=order_id,
            order_item_id=order_item_id,
            created_by=created_by,
        )

        return movement

    def record_loss(
        self,
        finished_goods_id: UUID,
        quantity_g: Decimal,
        reason: str,
        created_by: str | None = None,
    ) -> InventoryMovement:
        """
        Erfasst Verlust/Verderb.
        """
        inventory = self.db.get(FinishedGoodsInventory, finished_goods_id)
        if not inventory:
            raise ValueError("Fertigwaren-Bestand nicht gefunden")

        quantity_before = inventory.current_quantity_g
        inventory.current_quantity_g = max(Decimal("0"), inventory.current_quantity_g - quantity_g)

        if inventory.current_quantity_g == 0:
            inventory.is_active = False

        movement = self._record_movement(
            movement_type=MovementType.VERLUST,
            item_type=InventoryItemType.FERTIGWARE,
            finished_goods_id=finished_goods_id,
            quantity=-quantity_g,
            unit="g",
            quantity_before=quantity_before,
            quantity_after=inventory.current_quantity_g,
            from_location_id=inventory.location_id,
            reason=reason,
            created_by=created_by,
        )

        return movement

    # ========================================
    # PACKAGING INVENTORY
    # ========================================

    def receive_packaging(
        self,
        name: str,
        sku: str,
        quantity: int,
        unit: str = "Stück",
        supplier_name: str | None = None,
        purchase_price: Decimal | None = None,
        location_id: UUID | None = None,
        min_quantity: int = 0,
        reorder_quantity: int | None = None,
    ) -> PackagingInventory:
        """
        Erfasst Verpackungsmaterial-Eingang.
        """
        # Prüfen ob bereits vorhanden
        existing = self.db.execute(
            select(PackagingInventory).where(PackagingInventory.sku == sku)
        ).scalar_one_or_none()

        if existing:
            # Menge aufstocken
            quantity_before = existing.current_quantity
            existing.current_quantity += quantity

            self._record_movement(
                movement_type=MovementType.EINGANG,
                item_type=InventoryItemType.VERPACKUNG,
                packaging_id=existing.id,
                quantity=Decimal(quantity),
                unit=unit,
                quantity_before=Decimal(quantity_before),
                quantity_after=Decimal(existing.current_quantity),
                to_location_id=location_id,
            )

            return existing

        inventory = PackagingInventory(
            name=name,
            sku=sku,
            current_quantity=quantity,
            min_quantity=min_quantity,
            reorder_quantity=reorder_quantity,
            unit=unit,
            supplier_name=supplier_name,
            purchase_price=purchase_price,
            location_id=location_id,
        )

        self.db.add(inventory)
        self.db.flush()

        self._record_movement(
            movement_type=MovementType.EINGANG,
            item_type=InventoryItemType.VERPACKUNG,
            packaging_id=inventory.id,
            quantity=Decimal(quantity),
            unit=unit,
            quantity_before=Decimal("0"),
            quantity_after=Decimal(quantity),
            to_location_id=location_id,
        )

        return inventory

    def consume_packaging(
        self,
        packaging_id: UUID,
        quantity: int,
        order_id: UUID | None = None,
        created_by: str | None = None,
    ) -> InventoryMovement:
        """
        Verbucht Verpackungsverbrauch.
        """
        inventory = self.db.get(PackagingInventory, packaging_id)
        if not inventory:
            raise ValueError("Verpackungsmaterial nicht gefunden")

        if inventory.current_quantity < quantity:
            raise ValueError(
                f"Nicht genug Material verfügbar. "
                f"Benötigt: {quantity}, Verfügbar: {inventory.current_quantity}"
            )

        quantity_before = inventory.current_quantity
        inventory.current_quantity -= quantity

        movement = self._record_movement(
            movement_type=MovementType.PRODUKTION,
            item_type=InventoryItemType.VERPACKUNG,
            packaging_id=packaging_id,
            quantity=Decimal(-quantity),
            unit=inventory.unit,
            quantity_before=Decimal(quantity_before),
            quantity_after=Decimal(inventory.current_quantity),
            from_location_id=inventory.location_id,
            order_id=order_id,
            created_by=created_by,
        )

        return movement

    # ========================================
    # STOCK QUERIES
    # ========================================

    def get_stock_overview(self) -> dict:
        """
        Bestandsübersicht über alle Kategorien.
        """
        # Saatgut
        seed_stock = self.db.execute(
            select(
                func.count(SeedInventory.id).label("batches"),
                func.sum(SeedInventory.current_quantity_kg).label("total_kg")
            )
            .where(SeedInventory.is_active == True, SeedInventory.current_quantity_kg > 0)
        ).first()

        # Fertigware
        finished_stock = self.db.execute(
            select(
                func.count(FinishedGoodsInventory.id).label("batches"),
                func.sum(FinishedGoodsInventory.current_quantity_g).label("total_g")
            )
            .where(FinishedGoodsInventory.is_active == True, FinishedGoodsInventory.current_quantity_g > 0)
        ).first()

        # Verpackung
        packaging_stock = self.db.execute(
            select(
                func.count(PackagingInventory.id).label("items"),
                func.sum(PackagingInventory.current_quantity).label("total")
            )
            .where(PackagingInventory.is_active == True)
        ).first()

        # Ablaufende Ware (< 3 Tage)
        expiring_soon = self.db.execute(
            select(func.count(FinishedGoodsInventory.id))
            .where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.best_before_date <= date.today() + timedelta(days=3)
            )
        ).scalar() or 0

        # Nachbestellbedarf
        low_packaging = self.db.execute(
            select(func.count(PackagingInventory.id))
            .where(
                PackagingInventory.is_active == True,
                PackagingInventory.current_quantity <= PackagingInventory.min_quantity
            )
        ).scalar() or 0

        return {
            "seed": {
                "batches": seed_stock.batches or 0,
                "total_kg": float(seed_stock.total_kg or 0),
            },
            "finished_goods": {
                "batches": finished_stock.batches or 0,
                "total_g": float(finished_stock.total_g or 0),
                "expiring_soon": expiring_soon,
            },
            "packaging": {
                "items": packaging_stock.items or 0,
                "low_stock": low_packaging,
            },
        }

    def get_available_stock_for_product(self, product_id: UUID) -> list[FinishedGoodsInventory]:
        """
        Gibt verfügbaren Bestand für ein Produkt zurück (FIFO).
        """
        return self.db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.product_id == product_id,
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.is_reserved == False,
                FinishedGoodsInventory.current_quantity_g > 0,
                FinishedGoodsInventory.best_before_date > date.today()
            )
            .order_by(FinishedGoodsInventory.best_before_date.asc())  # FIFO nach MHD
        ).scalars().all()

    def get_traceability(self, finished_goods_id: UUID) -> dict:
        """
        Gibt vollständige Rückverfolgungskette zurück.
        """
        inventory = self.db.get(FinishedGoodsInventory, finished_goods_id)
        if not inventory:
            raise ValueError("Fertigwaren-Bestand nicht gefunden")

        result = {
            "finished_goods": {
                "id": str(inventory.id),
                "batch": inventory.batch_number,
                "harvest_date": inventory.harvest_date.isoformat(),
                "best_before": inventory.best_before_date.isoformat(),
            },
            "product": None,
            "harvest": None,
            "grow_batch": None,
            "seed_inventory": None,
            "deliveries": [],
        }

        # Produkt
        if inventory.product:
            result["product"] = {
                "id": str(inventory.product_id),
                "name": inventory.product.name,
                "sku": inventory.product.sku,
            }

        # Ernte
        if inventory.harvest_id:
            harvest = self.db.get(Harvest, inventory.harvest_id)
            if harvest:
                result["harvest"] = {
                    "id": str(harvest.id),
                    "date": harvest.ernte_datum.isoformat(),
                    "quantity_g": float(harvest.menge_gramm),
                    "quality": harvest.qualitaet_note,
                }

        # GrowBatch
        if inventory.grow_batch_id:
            grow_batch = self.db.get(GrowBatch, inventory.grow_batch_id)
            if grow_batch:
                result["grow_batch"] = {
                    "id": str(grow_batch.id),
                    "sow_date": grow_batch.aussaat_datum.isoformat(),
                    "trays": grow_batch.tray_anzahl,
                    "position": grow_batch.regal_position,
                }

        # Saatgut
        if inventory.seed_inventory_id:
            seed_inv = self.db.get(SeedInventory, inventory.seed_inventory_id)
            if seed_inv:
                result["seed_inventory"] = {
                    "id": str(seed_inv.id),
                    "batch": seed_inv.batch_number,
                    "supplier": seed_inv.supplier_name,
                    "supplier_batch": seed_inv.supplier_batch,
                    "received": seed_inv.received_date.isoformat(),
                    "is_organic": seed_inv.is_organic,
                }
                if seed_inv.seed:
                    result["seed_inventory"]["seed_name"] = seed_inv.seed.name

        # Auslieferungen
        deliveries = self.db.execute(
            select(InventoryMovement)
            .where(
                InventoryMovement.finished_goods_id == finished_goods_id,
                InventoryMovement.movement_type == MovementType.AUSGANG
            )
        ).scalars().all()

        for mov in deliveries:
            delivery = {
                "date": mov.movement_date.isoformat(),
                "quantity_g": float(abs(mov.quantity)),
            }
            if mov.order_id:
                order = self.db.get(Order, mov.order_id)
                if order:
                    delivery["order_id"] = str(order.id)
                    delivery["customer"] = order.kunde.name if order.kunde else None
            result["deliveries"].append(delivery)

        return result

    # ========================================
    # INVENTORY COUNT (INVENTUR)
    # ========================================

    def create_inventory_count(
        self,
        count_date: date | None = None,
        location_id: UUID | None = None,
        counted_by: str | None = None,
    ) -> InventoryCount:
        """
        Startet eine neue Inventur.
        """
        # Inventurnummer generieren
        year = date.today().year
        count_num = self.db.execute(
            select(func.count(InventoryCount.id))
            .where(InventoryCount.count_number.like(f"INV-{year}-%"))
        ).scalar() or 0
        count_number = f"INV-{year}-{count_num + 1:04d}"

        count = InventoryCount(
            count_date=count_date or date.today(),
            count_number=count_number,
            status="OFFEN",
            location_id=location_id,
            counted_by=counted_by,
        )

        self.db.add(count)
        self.db.flush()

        # Positionen automatisch anlegen
        self._populate_count_items(count)

        return count

    def _populate_count_items(self, count: InventoryCount):
        """
        Füllt Inventur mit aktuellen Beständen.
        """
        # Saatgut
        seed_items = self.db.execute(
            select(SeedInventory)
            .where(
                SeedInventory.is_active == True,
                or_(
                    count.location_id == None,
                    SeedInventory.location_id == count.location_id
                )
            )
        ).scalars().all()

        for item in seed_items:
            count_item = InventoryCountItem(
                count_id=count.id,
                item_type=InventoryItemType.SAATGUT,
                seed_inventory_id=item.id,
                system_quantity=item.current_quantity_kg,
                unit="kg",
            )
            self.db.add(count_item)

        # Fertigware
        finished_items = self.db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.is_active == True,
                or_(
                    count.location_id == None,
                    FinishedGoodsInventory.location_id == count.location_id
                )
            )
        ).scalars().all()

        for item in finished_items:
            count_item = InventoryCountItem(
                count_id=count.id,
                item_type=InventoryItemType.FERTIGWARE,
                finished_goods_id=item.id,
                system_quantity=item.current_quantity_g,
                unit="g",
            )
            self.db.add(count_item)

        # Verpackung
        packaging_items = self.db.execute(
            select(PackagingInventory)
            .where(
                PackagingInventory.is_active == True,
                or_(
                    count.location_id == None,
                    PackagingInventory.location_id == count.location_id
                )
            )
        ).scalars().all()

        for item in packaging_items:
            count_item = InventoryCountItem(
                count_id=count.id,
                item_type=InventoryItemType.VERPACKUNG,
                packaging_id=item.id,
                system_quantity=Decimal(item.current_quantity),
                unit=item.unit,
            )
            self.db.add(count_item)

    def finalize_inventory_count(
        self,
        count_id: UUID,
        apply_corrections: bool = True
    ) -> InventoryCount:
        """
        Schließt Inventur ab und verbucht Korrekturen.
        """
        count = self.db.get(InventoryCount, count_id)
        if not count:
            raise ValueError("Inventur nicht gefunden")

        if count.status == "ABGESCHLOSSEN":
            raise ValueError("Inventur ist bereits abgeschlossen")

        for item in count.items:
            if item.counted_quantity is None:
                raise ValueError(f"Position {item.id} wurde nicht gezählt")

            item.calculate_difference()

            if apply_corrections and item.difference != 0:
                # Korrektur-Bewegung erstellen
                self._record_movement(
                    movement_type=MovementType.KORREKTUR,
                    item_type=item.item_type,
                    seed_inventory_id=item.seed_inventory_id,
                    finished_goods_id=item.finished_goods_id,
                    packaging_id=item.packaging_id,
                    quantity=item.difference,
                    unit=item.unit,
                    quantity_before=item.system_quantity,
                    quantity_after=item.counted_quantity,
                    reason=f"Inventurkorrektur {count.count_number}",
                )

                # Bestand korrigieren
                if item.seed_inventory_id:
                    inv = self.db.get(SeedInventory, item.seed_inventory_id)
                    inv.current_quantity_kg = item.counted_quantity
                elif item.finished_goods_id:
                    inv = self.db.get(FinishedGoodsInventory, item.finished_goods_id)
                    inv.current_quantity_g = item.counted_quantity
                elif item.packaging_id:
                    inv = self.db.get(PackagingInventory, item.packaging_id)
                    inv.current_quantity = int(item.counted_quantity)

        count.status = "ABGESCHLOSSEN"
        count.completed_at = datetime.utcnow()

        return count

    # ========================================
    # HELPER
    # ========================================

    def _record_movement(
        self,
        movement_type: MovementType,
        item_type: InventoryItemType,
        quantity: Decimal,
        unit: str,
        quantity_before: Decimal,
        quantity_after: Decimal,
        seed_inventory_id: UUID | None = None,
        finished_goods_id: UUID | None = None,
        packaging_id: UUID | None = None,
        from_location_id: UUID | None = None,
        to_location_id: UUID | None = None,
        order_id: UUID | None = None,
        order_item_id: UUID | None = None,
        grow_batch_id: UUID | None = None,
        harvest_id: UUID | None = None,
        created_by: str | None = None,
        reason: str | None = None,
        reference_number: str | None = None,
    ) -> InventoryMovement:
        """
        Erstellt eine Lagerbewegung.
        """
        movement = InventoryMovement(
            movement_type=movement_type,
            item_type=item_type,
            seed_inventory_id=seed_inventory_id,
            finished_goods_id=finished_goods_id,
            packaging_id=packaging_id,
            quantity=quantity,
            unit=unit,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            order_id=order_id,
            order_item_id=order_item_id,
            grow_batch_id=grow_batch_id,
            harvest_id=harvest_id,
            created_by=created_by,
            reason=reason,
            reference_number=reference_number,
            movement_date=datetime.utcnow(),
        )

        self.db.add(movement)
        return movement
