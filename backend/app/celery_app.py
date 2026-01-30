"""
Celery Konfiguration für Background Tasks
"""
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "minga-greens",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.forecast_tasks",
        "app.tasks.report_tasks",
        "app.tasks.invoice_tasks",
        "app.tasks.inventory_tasks",
        "app.tasks.subscription_tasks",
    ]
)

# Celery Konfiguration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Berlin",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 Minuten max
    worker_prefetch_multiplier=1,
)

# Scheduled Tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    # Täglicher Forecast um 6:00 Uhr
    "daily-forecast-generation": {
        "task": "app.tasks.forecast_tasks.generate_daily_forecasts",
        "schedule": crontab(hour=6, minute=0),
    },
    # Stündliche Chargen-Status Prüfung
    "hourly-batch-status-check": {
        "task": "app.tasks.forecast_tasks.check_batch_status",
        "schedule": crontab(minute=0),
    },
    # Wöchentlicher Accuracy Report (Montag 7:00)
    "weekly-accuracy-report": {
        "task": "app.tasks.report_tasks.generate_weekly_accuracy_report",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },
    # Tägliche Forecast Accuracy Berechnung (23:00)
    "daily-accuracy-calculation": {
        "task": "app.tasks.forecast_tasks.calculate_forecast_accuracy",
        "schedule": crontab(hour=23, minute=0),
    },
    # ========== RECHNUNGEN ==========
    # Tägliche Prüfung überfälliger Rechnungen (8:00)
    "daily-overdue-invoice-check": {
        "task": "app.tasks.invoice_tasks.check_overdue_invoices",
        "schedule": crontab(hour=8, minute=0),
    },
    # Zahlungserinnerungen (9:00)
    "daily-payment-reminders": {
        "task": "app.tasks.invoice_tasks.send_payment_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    # Abo-Bestellungen generieren (5:00)
    "daily-recurring-orders": {
        "task": "app.tasks.subscription_tasks.process_daily_subscriptions",
        "schedule": crontab(hour=5, minute=0),
    },
    # Monatliche Umsatzstatistik (1. des Monats, 2:00)
    "monthly-revenue-stats": {
        "task": "app.tasks.invoice_tasks.calculate_revenue_stats",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },
    # ========== LAGER ==========
    # Tägliche Bestandsprüfung (7:00)
    "daily-low-stock-check": {
        "task": "app.tasks.inventory_tasks.check_low_stock",
        "schedule": crontab(hour=7, minute=0),
    },
    # MHD-Prüfung (7:30)
    "daily-expiry-check": {
        "task": "app.tasks.inventory_tasks.check_expiring_goods",
        "schedule": crontab(hour=7, minute=30),
    },
    # Täglicher Bestandsbericht (22:00)
    "daily-inventory-report": {
        "task": "app.tasks.inventory_tasks.generate_inventory_report",
        "schedule": crontab(hour=22, minute=0),
    },
    # Bereinigung abgelaufener Ware (3:00)
    "daily-expired-cleanup": {
        "task": "app.tasks.inventory_tasks.cleanup_expired_goods",
        "schedule": crontab(hour=3, minute=0),
    },
}
