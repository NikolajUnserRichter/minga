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
from app.core.email import email_service, PAYMENT_REMINDER_TEMPLATE

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.invoice_tasks.check_overdue_invoices",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
    time_limit=300,
    soft_time_limit=240,
)
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


@celery_app.task(
    name="app.tasks.invoice_tasks.send_payment_reminders",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
    time_limit=300,
    soft_time_limit=240,
)
def send_payment_reminders():
    """
    Mehrstufiges Mahnwesen (3 Stufen).

    Stufe 1: Freundliche Zahlungserinnerung (nach dunning_level1_days)
    Stufe 2: 2. Mahnung mit Mahngebühr (nach dunning_level2_days)
    Stufe 3: Letzte Mahnung / Inkasso-Androhung (nach dunning_level3_days)
    """
    from app.config import get_settings
    from app.core.email import (
        PAYMENT_REMINDER_TEMPLATE,
        DUNNING_LEVEL2_TEMPLATE,
        DUNNING_LEVEL3_TEMPLATE,
    )

    settings = get_settings()
    logger.info("Starte mehrstufiges Mahnverfahren")

    db = SessionLocal()
    try:
        today = date.today()
        from datetime import datetime as dt_cls
        from datetime import timezone as tz

        # Überfällige Rechnungen die noch gemahnt werden können (< Stufe 3 erreicht)
        reminder_invoices = db.execute(
            select(Invoice)
            .where(
                Invoice.status.in_([InvoiceStatus.UEBERFAELLIG, InvoiceStatus.MAHNVERFAHREN]),
                Invoice.reminder_level < 3,
                # Nächste Mahnung fällig ODER noch nie gemahnt
                (Invoice.next_reminder_date <= today) | (Invoice.next_reminder_date == None),
            )
        ).scalars().all()

        reminders_sent = 0
        for invoice in reminder_invoices:
            days_overdue = (today - invoice.due_date).days
            customer = db.get(Customer, invoice.customer_id)
            if not customer or not customer.email:
                logger.warning(f"Keine E-Mail für Kunde {invoice.customer_id}")
                continue

            open_amount = invoice.total - invoice.paid_amount

            # Bestimme nächste Mahnstufe
            current_level = invoice.reminder_level
            if current_level == 0 and days_overdue >= settings.dunning_level1_days:
                next_level = 1
                template = PAYMENT_REMINDER_TEMPLATE
                subject = f"Zahlungserinnerung — Rechnung {invoice.invoice_number}"
                new_deadline = today + timedelta(days=settings.dunning_level2_days - settings.dunning_level1_days)
                fee = Decimal("0")
            elif current_level == 1 and days_overdue >= settings.dunning_level2_days:
                next_level = 2
                template = DUNNING_LEVEL2_TEMPLATE
                subject = f"2. Mahnung — Rechnung {invoice.invoice_number}"
                new_deadline = today + timedelta(days=settings.dunning_level3_days - settings.dunning_level2_days)
                fee = Decimal(str(settings.dunning_fee_level2))
            elif current_level == 2 and days_overdue >= settings.dunning_level3_days:
                next_level = 3
                template = DUNNING_LEVEL3_TEMPLATE
                subject = f"Letzte Mahnung — Rechnung {invoice.invoice_number}"
                new_deadline = today + timedelta(days=14)
                fee = Decimal(str(settings.dunning_fee_level3))
            else:
                continue  # Noch nicht fällig für nächste Stufe

            success = email_service.send_email(
                email_to=customer.email,
                subject=subject,
                template_str=template,
                template_data={
                    "customer_name": customer.name,
                    "invoice_number": invoice.invoice_number,
                    "invoice_date": invoice.invoice_date.strftime("%d.%m.%Y"),
                    "due_date": invoice.due_date.strftime("%d.%m.%Y"),
                    "amount": f"{open_amount:.2f}",
                    "fee": f"{fee:.2f}",
                    "total_with_fee": f"{open_amount + fee:.2f}",
                    "new_deadline": new_deadline.strftime("%d.%m.%Y"),
                    "reminder_level": next_level,
                }
            )

            if success:
                invoice.reminder_level = next_level
                invoice.last_reminder_sent_at = dt_cls.now(tz.utc)
                invoice.next_reminder_date = new_deadline
                if next_level >= 2:
                    invoice.status = InvoiceStatus.MAHNVERFAHREN
                logger.info(
                    f"Mahnstufe {next_level} an {customer.email} "
                    f"für Rechnung {invoice.invoice_number} versendet"
                )
                reminders_sent += 1
            else:
                logger.error(f"Fehler beim Versenden an {customer.email}")

        db.commit()

        return {
            "status": "success",
            "reminders_sent": reminders_sent
        }

    finally:
        db.close()


@celery_app.task(
    name="app.tasks.invoice_tasks.generate_recurring_invoices",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
    time_limit=300,
    soft_time_limit=240,
)
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
