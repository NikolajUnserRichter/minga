"""
Selbstgehostete, cookielose Reichweitenmessung für die Marketing-Seite.

DSGVO-freundlich nach Plausible-Vorbild: keine Cookies, keine Speicherung der
IP-Adresse. Ein Besuch wird über einen täglich wechselnden Hash aus
(Tag + IP + User-Agent + Secret) unterschieden — nach Tageswechsel ist keine
Zuordnung mehr möglich, es entstehen keine personenbezogenen Profile.
"""
import os
import sqlite3
import hashlib
import datetime
from pathlib import Path

from app.config import get_settings

_settings = get_settings()

_BOTS = ("bot", "spider", "crawl", "slurp", "bingpreview", "facebookexternalhit",
         "headless", "monitor", "pingdom", "lighthouse", "preview")


def _db_path() -> Path:
    base = Path(_settings.tenants_dir).parent  # persistentes ./data-Volume
    base.mkdir(parents=True, exist_ok=True)
    return base / "webstats.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_db_path()), timeout=5)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        "ts TEXT, day TEXT, path TEXT, ref TEXT, visitor TEXT)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_day ON events(day)")
    return c


def _salt() -> str:
    return (os.environ.get("PLATFORM_ADMIN_KEY", "")
            or os.environ.get("SECRET_KEY", "")
            or "novaerp-webstats")


def _visitor_hash(day: str, ip: str, ua: str) -> str:
    raw = f"{day}|{ip}|{ua}|{_salt()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def record(path: str, ref: str, ip: str, ua: str) -> None:
    """Einen Seitenaufruf festhalten. Bots werden ignoriert."""
    ua_l = (ua or "").lower()
    if not ua_l or any(b in ua_l for b in _BOTS):
        return
    now = datetime.datetime.utcnow()
    day = now.strftime("%Y-%m-%d")
    path = (path or "/")[:200]
    ref = (ref or "")[:200]
    vis = _visitor_hash(day, ip or "", ua or "")
    c = _conn()
    try:
        c.execute(
            "INSERT INTO events(ts, day, path, ref, visitor) VALUES (?,?,?,?,?)",
            (now.isoformat(timespec="seconds"), day, path, ref, vis),
        )
        c.commit()
    finally:
        c.close()


def stats(days: int = 30) -> dict:
    """Aggregierte Kennzahlen der letzten ``days`` Tage."""
    since = (datetime.datetime.utcnow().date()
             - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    c = _conn()
    try:
        per_day = c.execute(
            "SELECT day, COUNT(*), COUNT(DISTINCT visitor) "
            "FROM events WHERE day >= ? GROUP BY day ORDER BY day", (since,)
        ).fetchall()
        top_paths = c.execute(
            "SELECT path, COUNT(*) v FROM events WHERE day >= ? "
            "GROUP BY path ORDER BY v DESC LIMIT 12", (since,)
        ).fetchall()
        top_refs = c.execute(
            "SELECT ref, COUNT(*) v FROM events WHERE day >= ? AND ref <> '' "
            "GROUP BY ref ORDER BY v DESC LIMIT 12", (since,)
        ).fetchall()
        tot = c.execute(
            "SELECT COUNT(*), COUNT(DISTINCT visitor) FROM events WHERE day >= ?",
            (since,),
        ).fetchone()
    finally:
        c.close()
    return {
        "since": since,
        "totals": {"views": tot[0] or 0, "visitors": tot[1] or 0},
        "per_day": [{"day": d, "views": v, "visitors": u} for d, v, u in per_day],
        "top_paths": [{"path": p, "views": v} for p, v in top_paths],
        "top_referrers": [{"ref": r, "views": v} for r, v in top_refs],
    }
