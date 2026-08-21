"""Speicher für die Ratgeber-Beiträge.

Die Beiträge liegen in SQLite im persistenten ``./data``-Volume, nicht im
Docroot: ``backend/static_marketing/`` wird ins Docker-Image gebacken und
verliert beim nächsten Deploy alles, was zur Laufzeit dorthin geschrieben
wurde. Der Ablageort folgt ``app/core/webstats.py``.

Der Preis dieser Entscheidung: die Inhalte liegen nicht im Git und brauchen
ein eigenes Backup des Volumes.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

STATUS_ENTWURF = "entwurf"
STATUS_WARTESCHLANGE = "warteschlange"
STATUS_LIVE = "live"
ERLAUBTE_STATUS = (STATUS_ENTWURF, STATUS_WARTESCHLANGE, STATUS_LIVE)

# Der Slug wird Teil einer URL. Streng halten: Kleinbuchstaben, Ziffern,
# einzelne Bindestriche.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLUG_MAXLEN = 80


class SlugFehler(ValueError):
    """Ein Slug verletzt das erlaubte Muster."""


@dataclass
class Article:
    """Ein Ratgeber-Beitrag."""

    slug: str
    title: str
    cluster: str = ""
    description: str = ""
    author: str = ""
    reading_minutes: int = 0
    summary: str = ""
    body: str = ""
    faq: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    teaser_slug: str = ""
    status: str = STATUS_ENTWURF
    queue_position: int = 0
    published_at: Optional[str] = None
    updated_at: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "cluster": self.cluster,
            "description": self.description,
            "author": self.author,
            "reading_minutes": self.reading_minutes,
            "summary": self.summary,
            "body": self.body,
            "faq": self.faq,
            "sources": self.sources,
            "teaser_slug": self.teaser_slug,
            "status": self.status,
            "queue_position": self.queue_position,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
        }


def pruefe_slug(slug: str) -> str:
    """Slug prüfen, ohne ihn zu reparieren.

    Bewusst kein ``.lower()``: würde Großschreibung still normalisiert,
    lieferte ``/ratgeber/ERP-Einfuehrung`` dieselbe Seite wie
    ``/ratgeber/erp-einfuehrung`` — eine Seite unter zwei URLs, also genau
    das, wogegen die Kanonisierung des Fundaments arbeitet.
    """
    slug = (slug or "").strip()
    if not slug or len(slug) > _SLUG_MAXLEN or not _SLUG_RE.match(slug):
        raise SlugFehler(f"Ungültiger Slug: '{slug}'")
    return slug


def db_path() -> Path:
    """Ablageort der Beitragsdatenbank.

    ``RATGEBER_DB_PATH`` übersteuert den Standard — Tests brauchen eine
    eigene Datei, sonst schreiben sie in das echte Volume.
    """
    override = os.environ.get("RATGEBER_DB_PATH", "").strip()
    if override:
        pfad = Path(override)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        return pfad
    base = Path(get_settings().tenants_dir).parent  # persistentes ./data
    base.mkdir(parents=True, exist_ok=True)
    return base / "ratgeber.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path()), timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS articles ("
        "slug TEXT PRIMARY KEY,"
        "title TEXT NOT NULL,"
        "cluster TEXT NOT NULL DEFAULT '',"
        "description TEXT NOT NULL DEFAULT '',"
        "author TEXT NOT NULL DEFAULT '',"
        "reading_minutes INTEGER NOT NULL DEFAULT 0,"
        "summary TEXT NOT NULL DEFAULT '',"
        "body TEXT NOT NULL DEFAULT '',"
        "faq TEXT NOT NULL DEFAULT '[]',"
        "sources TEXT NOT NULL DEFAULT '[]',"
        "teaser_slug TEXT NOT NULL DEFAULT '',"
        "status TEXT NOT NULL DEFAULT 'entwurf',"
        "queue_position INTEGER NOT NULL DEFAULT 0,"
        "published_at TEXT,"
        "updated_at TEXT NOT NULL DEFAULT ''"
        ")"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)")
    return c


def _liste(rohtext: str) -> list[dict]:
    """JSON-Spalte lesen und dabei Müll nicht nach oben durchreichen."""
    try:
        wert = json.loads(rohtext or "[]")
    except json.JSONDecodeError:
        return []
    return [x for x in wert if isinstance(x, dict)] if isinstance(wert, list) else []


def _aus_zeile(row: sqlite3.Row) -> Article:
    return Article(
        slug=row["slug"],
        title=row["title"],
        cluster=row["cluster"],
        description=row["description"],
        author=row["author"],
        reading_minutes=row["reading_minutes"],
        summary=row["summary"],
        body=row["body"],
        faq=_liste(row["faq"]),
        sources=_liste(row["sources"]),
        teaser_slug=row["teaser_slug"],
        status=row["status"],
        queue_position=row["queue_position"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
    )


def save(article: Article) -> Article:
    """Beitrag anlegen oder aktualisieren.

    ``published_at`` wird hier nie gesetzt — das macht ausschließlich
    ``publish()``, damit das Datum bei einer Korrektur nicht wandert.
    """
    slug = pruefe_slug(article.slug)
    if article.status not in ERLAUBTE_STATUS:
        raise ValueError(f"Unbekannter Status: '{article.status}'")
    if article.teaser_slug:
        pruefe_slug(article.teaser_slug)

    jetzt = datetime.utcnow().isoformat(timespec="seconds")
    c = _conn()
    try:
        c.execute(
            "INSERT INTO articles ("
            "slug, title, cluster, description, author, reading_minutes,"
            "summary, body, faq, sources, teaser_slug, status,"
            "queue_position, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(slug) DO UPDATE SET"
            " title=excluded.title, cluster=excluded.cluster,"
            " description=excluded.description, author=excluded.author,"
            " reading_minutes=excluded.reading_minutes,"
            " summary=excluded.summary, body=excluded.body,"
            " faq=excluded.faq, sources=excluded.sources,"
            " teaser_slug=excluded.teaser_slug, status=excluded.status,"
            " queue_position=excluded.queue_position,"
            " updated_at=excluded.updated_at",
            (
                slug, article.title, article.cluster, article.description,
                article.author, int(article.reading_minutes or 0),
                article.summary, article.body,
                json.dumps(article.faq or [], ensure_ascii=False),
                json.dumps(article.sources or [], ensure_ascii=False),
                article.teaser_slug, article.status,
                int(article.queue_position or 0), jetzt,
            ),
        )
        c.commit()
    finally:
        c.close()
    geladen = get(slug)
    assert geladen is not None  # gerade geschrieben
    return geladen


def get(slug: str) -> Optional[Article]:
    try:
        slug = pruefe_slug(slug)
    except SlugFehler:
        return None
    c = _conn()
    try:
        row = c.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
    finally:
        c.close()
    return _aus_zeile(row) if row else None


def list_all(status: Optional[str] = None) -> list[Article]:
    """Alle Beiträge, optional nach Status gefiltert."""
    c = _conn()
    try:
        if status:
            rows = c.execute(
                "SELECT * FROM articles WHERE status = ?"
                " ORDER BY queue_position, updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM articles ORDER BY queue_position, updated_at DESC"
            ).fetchall()
    finally:
        c.close()
    return [_aus_zeile(r) for r in rows]


def delete(slug: str) -> bool:
    try:
        slug = pruefe_slug(slug)
    except SlugFehler:
        return False
    c = _conn()
    try:
        cur = c.execute("DELETE FROM articles WHERE slug = ?", (slug,))
        c.commit()
        return cur.rowcount > 0
    finally:
        c.close()


def _status_setzen(slug: str, status: str, published_at: Optional[str]) -> Article:
    c = _conn()
    try:
        cur = c.execute(
            "UPDATE articles SET status = ?, published_at = ?, updated_at = ?"
            " WHERE slug = ?",
            (status, published_at,
             datetime.utcnow().isoformat(timespec="seconds"), slug),
        )
        c.commit()
        if cur.rowcount == 0:
            raise KeyError(slug)
    finally:
        c.close()
    geladen = get(slug)
    assert geladen is not None
    return geladen


def publish(slug: str, heute: Optional[date] = None) -> Article:
    """Beitrag live stellen.

    Das Datum wird nur beim ersten Mal gesetzt. Eine spätere Korrektur am
    Text darf das Veröffentlichungsdatum nicht nach vorn schieben — sonst
    sieht jede Kleinigkeit aus wie ein neuer Beitrag.
    """
    slug = pruefe_slug(slug)
    vorhanden = get(slug)
    if vorhanden is None:
        raise KeyError(slug)
    datum = vorhanden.published_at or (heute or date.today()).isoformat()
    return _status_setzen(slug, STATUS_LIVE, datum)


def unpublish(slug: str) -> Article:
    """Beitrag aus der Öffentlichkeit nehmen, Datum behalten.

    Wer denselben Beitrag später erneut live stellt, soll nicht plötzlich
    als Erstveröffentlichung dastehen.
    """
    slug = pruefe_slug(slug)
    vorhanden = get(slug)
    if vorhanden is None:
        raise KeyError(slug)
    return _status_setzen(slug, STATUS_ENTWURF, vorhanden.published_at)


def set_queue(slugs: list[str]) -> None:
    """Reihenfolge der Warteschlange festschreiben."""
    geprueft = [pruefe_slug(s) for s in slugs]
    jetzt = datetime.utcnow().isoformat(timespec="seconds")
    c = _conn()
    try:
        for position, slug in enumerate(geprueft):
            c.execute(
                "UPDATE articles SET queue_position = ?, updated_at = ? WHERE slug = ?",
                (position, jetzt, slug),
            )
        c.commit()
    finally:
        c.close()


def published() -> list[Article]:
    """Live-Beiträge, neueste Veröffentlichung zuerst."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT * FROM articles WHERE status = ?"
            " ORDER BY published_at DESC, updated_at DESC",
            (STATUS_LIVE,),
        ).fetchall()
    finally:
        c.close()
    return [_aus_zeile(r) for r in rows]
