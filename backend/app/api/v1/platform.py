"""Platform-Admin-API: Tenant-Provisioning + Tenant-Übersicht.

Diese Endpoints sind NICHT per-Tenant — sie verwalten die Plattform selbst.
Geschützt durch einen separaten Header ``X-Platform-Admin-Key``, der nur
dem Plattform-Betreiber (= dir) bekannt ist. Setze ``PLATFORM_ADMIN_KEY`` in
der Env.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.tenancy import (
    DEFAULT_TENANT_SLUG, RESERVED_SUBDOMAINS, ROOT_DOMAIN,
    is_valid_slug, provision_tenant, registry,
)

router = APIRouter(prefix="/platform", tags=["Platform-Admin"])


def _require_admin(x_platform_admin_key: Optional[str] = Header(default=None)) -> None:
    expected = os.environ.get("PLATFORM_ADMIN_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="PLATFORM_ADMIN_KEY ist nicht konfiguriert — Platform-Admin deaktiviert.",
        )
    # Constant-time-Vergleich gegen Timing-Attack
    if not x_platform_admin_key or not secrets.compare_digest(x_platform_admin_key, expected):
        raise HTTPException(status_code=401, detail="Ungültiger Platform-Admin-Key")


def _validated_slug(slug: str) -> str:
    """Pfad-Traversal-Schutz: jede Slug-Quelle (URL-Param) muss durch is_valid_slug."""
    slug = slug.lower().strip()
    if not is_valid_slug(slug):
        raise HTTPException(status_code=400, detail=f"Ungültiger Tenant-Slug: '{slug}'")
    return slug


@router.get("/tenants")
def list_tenants(_: None = Depends(_require_admin)):
    """Übersicht aller Tenants + Pfad + Größe + URL."""
    tenants = []
    for slug in registry.known_slugs():
        path = registry.path_for(slug)
        size_bytes = path.stat().st_size if path.exists() else 0
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
        tenants.append({
            "slug": slug,
            "db_path": str(path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "last_modified": mtime,
            "url": f"https://{slug}.{ROOT_DOMAIN}",
        })
    return {"tenants": tenants, "root_domain": ROOT_DOMAIN, "default": DEFAULT_TENANT_SLUG}


@router.post("/tenants", status_code=201)
def create_tenant(
    slug: str,
    seed_defaults: bool = True,
    _: None = Depends(_require_admin),
):
    """Provisioniert einen neuen Tenant: legt SQLite-Datei an, läuft create_all
    + auto-migrate, seedet Einheiten (optional)."""
    slug = _validated_slug(slug)
    if registry.exists(slug):
        raise HTTPException(status_code=409, detail=f"Tenant '{slug}' existiert bereits")

    path = provision_tenant(slug, seed_defaults=seed_defaults)
    return {
        "slug": slug,
        "db_path": str(path),
        "url": f"https://{slug}.{ROOT_DOMAIN}",
        "status": "created",
    }


@router.get("/tenants/{slug}")
def get_tenant(slug: str, _: None = Depends(_require_admin)):
    slug = _validated_slug(slug)
    if not registry.exists(slug):
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' nicht gefunden")
    path = registry.path_for(slug)
    return {
        "slug": slug,
        "db_path": str(path),
        "size_bytes": path.stat().st_size,
        "url": f"https://{slug}.{ROOT_DOMAIN}",
        "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
    }


@router.delete("/tenants/{slug}", status_code=204)
def delete_tenant(slug: str, _: None = Depends(_require_admin)):
    """DSGVO-konform: löscht die Tenant-DB-Datei vollständig."""
    slug = _validated_slug(slug)
    if slug == DEFAULT_TENANT_SLUG:
        raise HTTPException(status_code=400, detail="Default-Tenant kann nicht gelöscht werden")
    if not registry.exists(slug):
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' nicht gefunden")
    path = registry.path_for(slug)
    # Engine schließen damit SQLite-File-Lock weg ist
    try:
        eng = registry._engines.pop(slug, None)  # type: ignore[attr-defined]
        if eng:
            eng.dispose()
        registry._sessions.pop(slug, None)  # type: ignore[attr-defined]
    except Exception:
        pass
    path.unlink(missing_ok=True)
    # WAL-Sidecar-Files mit aufräumen
    for suffix in ("-shm", "-wal"):
        sidecar = path.with_name(path.name + suffix)
        sidecar.unlink(missing_ok=True)


@router.get("/info")
def platform_info(_: None = Depends(_require_admin)):
    """Plattform-Übersicht — für Monitoring/Dashboard."""
    slugs = registry.known_slugs()
    total_size = sum(registry.path_for(s).stat().st_size for s in slugs if registry.path_for(s).exists())
    return {
        "root_domain": ROOT_DOMAIN,
        "default_tenant": DEFAULT_TENANT_SLUG,
        "tenants_count": len(slugs),
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "tenants_dir": str(registry.path_for("").parent),
    }
