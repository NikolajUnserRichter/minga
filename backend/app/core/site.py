"""Auslieferungs-Rollen der Marketing-Site.

Ein einziger Prozess bedient drei Rollen, unterschieden allein am
Host-Header:

  * ``novaerp.de`` und ``www.novaerp.de`` → öffentliche Marketing-Seite
  * ``admin.novaerp.de``                  → Platform-Admin-UI
  * ``<tenant>.novaerp.de``               → React-SPA (ERP)

Die Erkennung liegt hier statt in ``main.py``, weil sowohl der Catch-All
als auch die SEO-Routen sie brauchen und ein Import aus ``main.py``
zirkulär wäre.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request


def root_domain() -> str:
    """Basisdomain der Plattform, per Env überschreibbar."""
    return os.environ.get("SPROUDDESK_ROOT_DOMAIN", "novaerp.de").lower()


def hostname(request: Request) -> str:
    """Host-Header ohne Port, kleingeschrieben. Leerer String, wenn keiner da ist."""
    return (request.headers.get("host") or "").split(":")[0].lower()


def is_apex_host(host: str) -> bool:
    """Apex einschließlich www.

    www zählt bewusst als Apex, damit es nicht auf die ERP-SPA durchfällt.
    Umgeleitet wird es an anderer Stelle.
    """
    root = root_domain()
    return host == root or host == f"www.{root}"


def is_www_host(host: str) -> bool:
    return host == f"www.{root_domain()}"


def is_admin_host(host: str) -> bool:
    return host == f"admin.{root_domain()}"


def canonical_origin() -> str:
    """Origin, auf den alle kanonischen URLs und Schema-IDs zeigen."""
    return f"https://{root_domain()}"


def marketing_dir() -> Path:
    """Docroot der Marketing-Seite — im Container gebacken, lokal im Repo."""
    packaged = Path("/app/static_marketing")
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2] / "static_marketing"
