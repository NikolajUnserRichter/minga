"""Scheduler-Einstieg der Monatsrechnungen (B5).

Läuft je Mandant über scheduler_service._safe_wrap: die ContextVar trägt den
Mandanten, SessionLocal() öffnet dessen Datenbank. Kein Celery-Task — der
Produktionsbetrieb nutzt den In-Process-Scheduler (Root-Dockerfile).
"""
import logging

from app.database import SessionLocal
from app.services.monatsrechnung_service import automatischer_lauf
from app.tenancy import get_current_tenant, is_valid_slug

logger = logging.getLogger(__name__)

#: IDs im Scheduler (scheduler_service.start_scheduler). POST
#: /admin/scheduler/run darf sie nicht auslösen: der Endpunkt ruft die
#: Mandantenschleife auf und wirkte damit in ALLEN Mandanten.
JOB_ID = "monthly-invoice-proposals"
JOB_ID_NACHSTART = "monthly-invoice-proposals-nachstart"
NUR_JE_MANDANT = frozenset({JOB_ID, JOB_ID_NACHSTART})


def monatsrechnungen_vorschlagen() -> dict:
    """Legt am Monatsanfang die Entwürfe für den Vormonat an (Schalter je Mandant)."""
    slug = get_current_tenant() or ""
    # Der Golden-Seed der Demo liegt als demo.seed.db neben den Mandanten und
    # taucht in known_slugs() als "demo.seed" auf — kein Mandant, nie schreiben.
    if not is_valid_slug(slug):
        return {"status": "kein_mandant"}
    db = SessionLocal()
    try:
        return automatischer_lauf(db)
    finally:
        db.close()
