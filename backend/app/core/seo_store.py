"""Speicher für SEO- und GEO-Messdaten.

Eigene Datei ``seo.db`` im persistenten ``./data``-Volume, getrennt von
Redaktion (``ratgeber.db``) und Reichweitenzählung (``webstats.db``):
Messdaten wachsen täglich und dürfen die anderen Speicher nicht aufblähen.
Der Ablageort folgt ``app/core/webstats.py``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.config import get_settings

ART_DISCOVERY = "discovery"
ART_MARKE = "marke"


def db_path() -> Path:
    """Ablageort der Messdatenbank; ``SEO_DB_PATH`` übersteuert für Tests."""
    override = os.environ.get("SEO_DB_PATH", "").strip()
    if override:
        pfad = Path(override)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        return pfad
    base = Path(get_settings().tenants_dir).parent  # persistentes ./data
    base.mkdir(parents=True, exist_ok=True)
    return base / "seo.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path()), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS gsc_daily ("
        "day TEXT NOT NULL, page TEXT NOT NULL, query TEXT NOT NULL,"
        "clicks INTEGER NOT NULL DEFAULT 0,"
        "impressions INTEGER NOT NULL DEFAULT 0,"
        "position REAL NOT NULL DEFAULT 0,"
        "PRIMARY KEY (day, page, query))"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS geo_runs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "day TEXT NOT NULL, prompt_id TEXT NOT NULL, art TEXT NOT NULL,"
        "zitiert INTEGER NOT NULL DEFAULT 0,"
        "domains TEXT NOT NULL DEFAULT '[]')"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_geo_runs_day ON geo_runs(day)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS grounding_usage ("
        "day TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS ai_referrals ("
        "day TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0,"
        "domains TEXT NOT NULL DEFAULT '[]')"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS changelog ("
        "ts TEXT NOT NULL, quelle TEXT NOT NULL, nachricht TEXT NOT NULL)"
    )
    return c


def _seit(days: int, heute: Optional[date]) -> str:
    return ((heute or date.today()) - timedelta(days=days)).isoformat()


def record_gsc_rows(day: str, rows: list[dict]) -> int:
    """Tageszeilen aus der Search Console ablegen — je Tag idempotent."""
    c = _conn()
    try:
        for r in rows:
            c.execute(
                "INSERT INTO gsc_daily (day, page, query, clicks, impressions, position)"
                " VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(day, page, query) DO UPDATE SET"
                " clicks=excluded.clicks, impressions=excluded.impressions,"
                " position=excluded.position",
                (day, r.get("page", ""), r.get("query", ""),
                 int(r.get("clicks", 0)), int(r.get("impressions", 0)),
                 float(r.get("position", 0.0))),
            )
        c.commit()
    finally:
        c.close()
    return len(rows)


def gsc_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """Klicks und Impressionen der letzten ``days`` Tage."""
    seit = _seit(days, heute)
    c = _conn()
    try:
        per_day = c.execute(
            "SELECT day, SUM(clicks) k, SUM(impressions) i FROM gsc_daily"
            " WHERE day >= ? GROUP BY day ORDER BY day", (seit,)
        ).fetchall()
        tot = c.execute(
            "SELECT COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0)"
            " FROM gsc_daily WHERE day >= ?", (seit,)
        ).fetchone()
    finally:
        c.close()
    return {
        "seit": seit,
        "totals": {"clicks": tot[0], "impressions": tot[1]},
        "per_day": [{"day": d, "clicks": k, "impressions": i} for d, k, i in per_day],
    }


def gsc_top_queries(days: int = 28, limit: int = 20,
                    heute: Optional[date] = None) -> list[dict]:
    """Suchanfragen nach Impressionen, über Seiten aggregiert."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT query, SUM(clicks) k, SUM(impressions) i, AVG(position) p"
            " FROM gsc_daily WHERE day >= ? GROUP BY query"
            " ORDER BY i DESC LIMIT ?", (_seit(days, heute), limit)
        ).fetchall()
    finally:
        c.close()
    return [{"query": q, "clicks": k, "impressions": i, "position": round(p, 1)}
            for q, k, i, p in rows]


def log_change(quelle: str, nachricht: str) -> None:
    """Einen Eintrag ins Änderungsprotokoll schreiben."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO changelog (ts, quelle, nachricht) VALUES (?,?,?)",
            (datetime.utcnow().isoformat(timespec="seconds"), quelle, nachricht),
        )
        c.commit()
    finally:
        c.close()


def changelog_entries(limit: int = 50) -> list[dict]:
    """Jüngste Protokolleinträge, neueste zuerst."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT ts, quelle, nachricht FROM changelog"
            " ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        c.close()
    return [{"ts": t, "quelle": q, "nachricht": n} for t, q, n in rows]


def record_geo_run(day: str, prompt_id: str, art: str,
                   zitiert: bool, domains: list[str]) -> None:
    """Eine GEO-Messung festhalten (ein Prompt, eine Engine-Antwort)."""
    if art not in (ART_DISCOVERY, ART_MARKE):
        raise ValueError(f"Unbekannte Prompt-Art: '{art}'")
    c = _conn()
    try:
        c.execute(
            "INSERT INTO geo_runs (day, prompt_id, art, zitiert, domains)"
            " VALUES (?,?,?,?,?)",
            (day, prompt_id, art, 1 if zitiert else 0,
             json.dumps(domains, ensure_ascii=False)),
        )
        c.commit()
    finally:
        c.close()


def geo_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """Zitatquoten, strikt getrennt nach Discovery und Marke."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT art, COUNT(*), COALESCE(SUM(zitiert),0) FROM geo_runs"
            " WHERE day >= ? GROUP BY art", (_seit(days, heute),)
        ).fetchall()
    finally:
        c.close()
    leer = {"laeufe": 0, "zitiert": 0, "quote": 0.0}
    out = {ART_DISCOVERY: dict(leer), ART_MARKE: dict(leer)}
    for art, n, z in rows:
        if art in out:
            out[art] = {"laeufe": n, "zitiert": z, "quote": round(z / n, 3)}
    return out


def grounding_increment(day: str, n: int = 1) -> None:
    """Verbrauch des Grounding-Kontingents hochzählen."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO grounding_usage (day, count) VALUES (?, ?)"
            " ON CONFLICT(day) DO UPDATE SET count = count + excluded.count",
            (day, n),
        )
        c.commit()
    finally:
        c.close()


def grounding_spent(day: str) -> tuple[int, int]:
    """Verbrauch (Tag, laufender Monat) — Grundlage des Kostenriegels."""
    monat = day[:7]
    c = _conn()
    try:
        tag = c.execute(
            "SELECT COALESCE(count,0) FROM grounding_usage WHERE day = ?", (day,)
        ).fetchone()
        mon = c.execute(
            "SELECT COALESCE(SUM(count),0) FROM grounding_usage WHERE day LIKE ?",
            (f"{monat}-%",),
        ).fetchone()
    finally:
        c.close()
    return (tag[0] if tag else 0, mon[0])


def record_ai_referrals(day: str, count: int, domains: list[str]) -> None:
    """Besuche über KI-Verweise für einen Tag festhalten (überschreibend)."""
    c = _conn()
    try:
        c.execute(
            "INSERT INTO ai_referrals (day, count, domains) VALUES (?,?,?)"
            " ON CONFLICT(day) DO UPDATE SET"
            " count=excluded.count, domains=excluded.domains",
            (day, int(count), json.dumps(domains, ensure_ascii=False)),
        )
        c.commit()
    finally:
        c.close()


def ai_referrals_summary(days: int = 28, heute: Optional[date] = None) -> dict:
    """KI-Verweis-Besuche der letzten ``days`` Tage."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT day, count FROM ai_referrals WHERE day >= ? ORDER BY day",
            (_seit(days, heute),),
        ).fetchall()
    finally:
        c.close()
    return {
        "gesamt": sum(n for _, n in rows),
        "per_day": [{"day": d, "count": n} for d, n in rows],
    }
