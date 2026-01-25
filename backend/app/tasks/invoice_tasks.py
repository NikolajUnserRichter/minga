"""
Celery Tasks für Rechnungswesen
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.customer import Customer

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.invoice_tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Prüft offene Rechnungen auf Überfälligkeit.
    Wird täglich um 8:00 ausgeführt.
    """
    logger.info("Prüfe überfällige Rechnungen")

    db = SessionLocal()
    try:
        today = date.today()

        # Offene und teilbezahlte Rechnungen die überfällig sind
        overdue_invoices = db.execute(
            select(Invoice)
            .where(
                Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT]),
                Invoice.due_date < today
            )
        ).scalars().all()

        updated_count = 0
        for invoice in overdue_invoices:
            invoice.status = InvoiceStatus.UEBERFAELLIG
            updated_count += 1
            logger.info(f"Rechnung {invoice.invoice_number} als überfällig markiert")

        db.commit()

        # Zusammenfassung erstellen
        total_overdue = db.execute(
            select(func.sum(Invoice.total - Invoice.paid_amount))
            .where(Invoice.status == InvoiceStatus.UEBERFAELLIG)
        ).scalar() or Decimal("0")

        return {
            "status": "success",
            "newly_overdue": updated_count,
            "total_overdue_amount": float(total_overdue)
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.invoice_tasks.send_payment_reminders")
def send_payment_reminders():
    """
    Sendet Zahlungserinnerungen für überfällige Rechnungen.
    """
    logger.info("Sende Zahlungserinnerungen")

    db = SessionLocal()
    try:
        today = date.today()

        # Rechnungen die seit 3 Tagen überfällig sind
        reminder_invoices = db.execute(
            select(Invoice)
            .where(
                Invoice.status == InvoiceStatus.UEBERFAELLIG,
                Invoice.due_date <= today - timedelta(days=3)
            )
        ).scalars().all()

        reminders_sent = 0
        for invoice in reminder_invoices:
            # TODO: E-Mail versenden
            # Hier würde die E-Mail-Integration kommen
            logger.info(f"Zahlungserinnerung für {invoice.invoice_number} vorbereitet")
            reminders_sent += 1

        return {
            "status": "success",
            "reminders_prepared": reminders_sent
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.invoice_tasks.generate_recurring_invoices")
def generate_recurring_invoices():
    """
    Generiert Rechnungen aus Abonnements.
    Wird täglich ausgeführt.
    """
    logger.info("Generiere wiederkehrende Rechnungen aus Abonnements")

    db = SessionLocal()
    try:
        from app.models.customer import Subscription, SubscriptionInterval
        from app.services.invoice_service import InvoiceService

        today = date.today()
        weekday = today.weekday()

        # Aktive Abonnements für heute
        subscriptions = db.execute(
            select(Subscription)
            .where(
                Subscription.aktiv == True,
                Subscription.liefertage.contains([weekday]),
                Subscription.gueltig_von <= today,
                (Subscription.gueltig_bis == None) | (Subscription.gueltig_bis >= today)
            )
        ).scalars().all()

        invoices_created = 0
        service = InvoiceService(db)

        # Gruppiere nach Kunde
        customer_subscriptions = {}
        for sub in subscriptions:
            if sub.kunde_id not in customer_subscriptions:
                customer_subscriptions[sub.kunde_id] = []
            customer_subscriptions[sub.kunde_id].append(sub)

        for customer_id, subs in customer_subscriptions.items():
            try:
                # Prüfen ob heute schon eine Rechnung existiert
                existing = db.execute(
                    select(Invoice)
                    .where(
                        Invoice.customer_id == customer_id,
                        Invoice.invoice_date == today
                    )
                ).scalar_one_or_none()

                if existing:
                    logger.info(f"Rechnung für Kunde {customer_id} existiert bereits")
                    continue

                # Neue Rechnung erstellen
                invoice = service.create_invoice(
                    customer_id=customer_id,
                    invoice_date=today,
                    delivery_date=today
                )

                # Positionen aus Abonnements
                for sub in subs:
                    service.add_line(
                        invoice_id=invoice.id,
                        description=f"Abo-Lieferung: {sub.seed.name}" if sub.seed else "Abo-Lieferung",
                        quantity=sub.menge,
                        unit=sub.einheit,
                        unit_price=Decimal("0.08"),  # Standardpreis, sollte aus Preisliste kommen
                    )

                invoices_created += 1

            except Exception as e:
                logger.error(f"Fehler bei Abo-Rechnung für Kunde {customer_id}: {e}")

        db.commit()

        return {
            "status": "success",
            "subscriptions_processed": len(subscriptions),
            "invoices_created": invoices_created
        }

    except Exception as e:
        logger.error(f"Fehler bei Abo-Rechnungen: {e}")
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(name="app.tasks.invoice_tasks.calculate_revenue_stats")
def calculate_revenue_stats(monat: int = None, jahr: int = None):
    """
    Berechnet Umsatzstatistiken für einen Monat.
    """
    db = SessionLocal()
    try:
        today = date.today()
        monat = monat or today.month
        jahr = jahr or today.year

        # Monatsgrenzen
        if monat == 12:
            naechster_monat = date(jahr + 1, 1, 1)
        else:
            naechster_monat = date(jahr, monat + 1, 1)

        start = date(jahr, monat, 1)
        end = naechster_monat - timedelta(days=1)

        # Bezahlte Rechnungen
        paid_stats = db.execute(
            select(
                func.count(Invoice.id).label("anzahl"),
                func.sum(Invoice.total).label("brutto"),
                func.sum(Invoice.subtotal).label("netto"),
                func.sum(Invoice.tax_amount).label("steuer")
            )
            .where(
                Invoice.invoice_date.between(start, end),
                Invoice.status == InvoiceStatus.BEZAHLT
            )
        ).first()

        # Offene Forderungen
        open_amount = db.execute(
            select(func.sum(Invoice.total - Invoice.paid_amount))
            .where(
                Invoice.status.in_([
                    InvoiceStatus.OFFEN,
                    InvoiceStatus.TEILBEZAHLT,
                    InvoiceStatus.UEBERFAELLIG
                ])
            )
        ).scalar() or Decimal("0")

        stats = {
            "zeitraum": {
                "monat": monat,
                "jahr": jahr,
                "von": start.isoformat(),
                "bis": end.isoformat()
            },
            "bezahlt": {
                "anzahl": paid_stats.anzahl or 0,
                "brutto": float(paid_stats.brutto or 0),
                "netto": float(paid_stats.netto or 0),
                "steuer": float(paid_stats.steuer or 0)
            },
            "offene_forderungen": float(open_amount)
        }

        logger.info(
            f"Umsatzstatistik {monat}/{jahr}: "
            f"{stats['bezahlt']['brutto']:.2f}€ Umsatz, "
            f"{stats['offene_forderungen']:.2f}€ offen"
        )

        return {
            "status": "success",
            "stats": stats
        }

    finally:
        db.close()
