"""In-Process Job-Scheduler (APScheduler).

Ersetzt Celery+Redis im Demo-Deploy. Spawnt einen BackgroundScheduler im
FastAPI-Prozess, der dieselben Funktionen aufruft, die sonst als Celery-Tasks
laufen würden. Vorteile:
  * Kein Redis-Service notwendig
  * Kein separater Worker-Container
  * Eine Replica reicht (Hobby-Plan)
Limitationen:
  * Bei mehreren App-Instanzen würden Jobs mehrfach feuern → coalesce.
  * Aufgaben sollten kurz/idempotent sein — kein Job-Result-Tracking.

Aktivierung über `SCHEDULER_ENABLED=true` (default: true). Während Tests via
`SCHEDULER_ENABLED=false` deaktivierbar.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _safe_wrap(name: str, fn):
    """Wrapped Job — iteriert über alle Tenants und führt fn() je Tenant aus.

    Pro Tenant wird der ContextVar gesetzt, sodass `SessionLocal()`-Aufrufe in
    den Tasks automatisch die richtige Tenant-DB nutzen. Einzelne Tenant-Fehler
    killen nicht den ganzen Job.
    """
    def runner():
        from app.tenancy import registry, set_current_tenant
        slugs = registry.known_slugs()
        if not slugs:
            logger.info(f"[scheduler] Job '{name}': keine Tenants vorhanden, skip")
            return
        results = {}
        for slug in slugs:
            try:
                set_current_tenant(slug)
                logger.info(f"[scheduler] Job '{name}' [tenant={slug}] starte")
                res = fn()
                results[slug] = "ok" if not isinstance(res, dict) else res.get("status", "ok")
                logger.info(f"[scheduler] Job '{name}' [tenant={slug}] OK")
            except Exception as e:
                results[slug] = f"error: {e}"
                logger.exception(f"[scheduler] Job '{name}' [tenant={slug}] failed")
            finally:
                set_current_tenant(None)
        logger.info(f"[scheduler] Job '{name}' abgeschlossen: {results}")
    return runner


def start_scheduler() -> Optional[BackgroundScheduler]:
    """Initialisiert + startet den Scheduler. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    if os.getenv("SCHEDULER_ENABLED", "true").lower() not in ("1", "true", "yes"):
        logger.info("[scheduler] deaktiviert via SCHEDULER_ENABLED")
        return None

    # Imports erst hier — keine Belastung bei Test-Boot.
    from app.tasks.inventory_tasks import (
        check_low_stock, check_expiring_goods,
        generate_inventory_report, cleanup_expired_goods,
    )
    from app.tasks.forecast_tasks import (
        generate_daily_forecasts, check_batch_status, calculate_forecast_accuracy,
    )
    from app.tasks.invoice_tasks import (
        check_overdue_invoices, send_payment_reminders, calculate_revenue_stats,
    )
    from app.tasks.subscription_tasks import process_daily_subscriptions
    from app.tasks.report_tasks import generate_weekly_accuracy_report

    sched = BackgroundScheduler(timezone="Europe/Berlin")

    # Spiegelt das Celery-Beat-Schedule aus celery_app.py
    jobs = [
        # === Lager ===
        ("low-stock-check",       check_low_stock,             CronTrigger(hour=7,  minute=0)),
        ("expiry-check",          check_expiring_goods,        CronTrigger(hour=7,  minute=30)),
        ("inventory-report",      generate_inventory_report,   CronTrigger(hour=22, minute=0)),
        ("expired-cleanup",       cleanup_expired_goods,       CronTrigger(hour=3,  minute=0)),
        # === Forecast ===
        ("daily-forecasts",       generate_daily_forecasts,    CronTrigger(hour=6,  minute=0)),
        ("batch-status",          check_batch_status,          CronTrigger(minute=0)),  # stündlich
        ("forecast-accuracy",     calculate_forecast_accuracy, CronTrigger(hour=23, minute=0)),
        # === Rechnungen ===
        ("overdue-invoices",      check_overdue_invoices,      CronTrigger(hour=8,  minute=0)),
        ("payment-reminders",     send_payment_reminders,      CronTrigger(hour=9,  minute=0)),
        ("monthly-revenue-stats", calculate_revenue_stats,     CronTrigger(day=1, hour=2, minute=0)),
        # === Abos ===
        ("daily-subscriptions",   process_daily_subscriptions, CronTrigger(hour=5,  minute=0)),
        # === Reports ===
        ("weekly-accuracy",       generate_weekly_accuracy_report, CronTrigger(day_of_week="mon", hour=7, minute=0)),
    ]

    for name, fn, trigger in jobs:
        sched.add_job(
            _safe_wrap(name, fn),
            trigger=trigger,
            id=name,
            name=name,
            coalesce=True,       # verpasste Runs werden zusammengefasst
            max_instances=1,     # niemals parallel
            replace_existing=True,
        )

    sched.start()
    _scheduler = sched
    job_names = [j.id for j in sched.get_jobs()]
    logger.info(f"[scheduler] {len(job_names)} Jobs aktiv: {job_names}")
    return sched


def shutdown_scheduler() -> None:
    """Stoppt den Scheduler sauber."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] gestoppt")
    except Exception as e:
        logger.warning(f"[scheduler] shutdown fehlgeschlagen: {e}")
    _scheduler = None


def get_jobs() -> list[dict]:
    """Für Debug-Endpoint: Liste aller geplanten Jobs + nächste Fire-Time."""
    if _scheduler is None:
        return []
    return [
        {
            "id": j.id,
            "name": j.name,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in _scheduler.get_jobs()
    ]
