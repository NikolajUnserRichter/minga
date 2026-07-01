"""
Integrationen — Self-Service-Anbindung externer Dienste.

Aktuell: Lexware Office (lexoffice). Jeder Tenant hinterlegt seinen eigenen
API-Key; der Key wird als Secret gespeichert und nie im Klartext zurückgegeben.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DBSession
from app.services.lexoffice_service import (
    LexofficeConnector,
    LexofficeError,
    sync_invoice,
)
from app.services.shopify_service import ShopifyConnector, ShopifyError
from app.services.settings_service import get_setting, set_setting

router = APIRouter(prefix="/integrations", tags=["Integrationen"])


class LexofficeStatus(BaseModel):
    enabled: bool
    configured: bool  # API-Key hinterlegt?


class LexofficeConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    api_key: Optional[str] = None  # None/"" = unverändert, "***" = unverändert


class LexofficeTestResult(BaseModel):
    ok: bool
    company_name: Optional[str] = None
    organization_id: Optional[str] = None
    error: Optional[str] = None


def _get_key(db) -> Optional[str]:
    return get_setting(db, "LEXOFFICE_API_KEY", env_fallback=False)


@router.get("/lexoffice", response_model=LexofficeStatus)
async def lexoffice_status(db: DBSession):
    key = _get_key(db)
    enabled = (get_setting(db, "LEXOFFICE_ENABLED", env_fallback=False) or "").lower() in ("1", "true", "yes")
    return LexofficeStatus(enabled=enabled, configured=bool(key))


@router.put("/lexoffice", response_model=LexofficeStatus)
async def lexoffice_configure(data: LexofficeConfigUpdate, db: DBSession):
    """API-Key hinterlegen / Integration aktivieren. Leerer Key löscht ihn,
    "***" lässt den bestehenden Key unverändert."""
    if data.api_key is not None and data.api_key != "***":
        if data.api_key.strip() == "":
            from app.models.app_setting import AppSetting
            existing = db.get(AppSetting, "LEXOFFICE_API_KEY")
            if existing:
                db.delete(existing)
        else:
            set_setting(db, "LEXOFFICE_API_KEY", data.api_key.strip(), is_secret=True)
    if data.enabled is not None:
        set_setting(db, "LEXOFFICE_ENABLED", "true" if data.enabled else "false", is_secret=False)
    db.commit()

    key = _get_key(db)
    enabled = (get_setting(db, "LEXOFFICE_ENABLED", env_fallback=False) or "").lower() in ("1", "true", "yes")
    return LexofficeStatus(enabled=enabled, configured=bool(key))


@router.post("/lexoffice/test", response_model=LexofficeTestResult)
async def lexoffice_test(db: DBSession):
    """Verbindung mit dem hinterlegten Key prüfen (GET /v1/profile)."""
    key = _get_key(db)
    if not key:
        raise HTTPException(status_code=400, detail="Kein lexoffice-API-Key hinterlegt")
    try:
        result = LexofficeConnector(key).test_connection()
        return LexofficeTestResult(**result)
    except LexofficeError as e:
        return LexofficeTestResult(ok=False, error=str(e))


@router.post("/lexoffice/invoices/{invoice_id}", response_model=dict)
async def lexoffice_push_invoice(invoice_id: UUID, db: DBSession, force: bool = False):
    """Eine Rechnung in das lexoffice-Konto des Kunden übertragen (Entwurf).

    Idempotent: bereits übertragene Rechnungen werden ohne erneuten API-Call
    übersprungen; ``?force=true`` erzwingt eine erneute Übertragung."""
    key = _get_key(db)
    if not key:
        raise HTTPException(status_code=400, detail="Kein lexoffice-API-Key hinterlegt")

    from app.models.invoice import Invoice
    from app.models.customer import Customer

    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    customer = db.get(Customer, invoice.customer_id) if invoice.customer_id else None
    customer_name = customer.name if customer else "Kunde"

    try:
        return sync_invoice(db, invoice, LexofficeConnector(key), customer_name=customer_name, force=force)
    except LexofficeError as e:
        raise HTTPException(status_code=502, detail=f"lexoffice: {e}")


# ---------- Shopify ----------

class ShopifyStatus(BaseModel):
    enabled: bool
    configured: bool
    shop_domain: Optional[str] = None


class ShopifyConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    shop_domain: Optional[str] = None
    access_token: Optional[str] = None  # None/"" = unverändert, "***" = unverändert


class ShopifyTestResult(BaseModel):
    ok: bool
    shop_name: Optional[str] = None
    currency: Optional[str] = None
    error: Optional[str] = None


def _shopify_creds(db) -> tuple[Optional[str], Optional[str]]:
    return (
        get_setting(db, "SHOPIFY_SHOP_DOMAIN", env_fallback=False),
        get_setting(db, "SHOPIFY_ACCESS_TOKEN", env_fallback=False),
    )


@router.get("/shopify", response_model=ShopifyStatus)
async def shopify_status(db: DBSession):
    domain, token = _shopify_creds(db)
    enabled = (get_setting(db, "SHOPIFY_ENABLED", env_fallback=False) or "").lower() in ("1", "true", "yes")
    return ShopifyStatus(enabled=enabled, configured=bool(domain and token), shop_domain=domain)


@router.put("/shopify", response_model=ShopifyStatus)
async def shopify_configure(data: ShopifyConfigUpdate, db: DBSession):
    if data.shop_domain is not None:
        set_setting(db, "SHOPIFY_SHOP_DOMAIN", data.shop_domain.strip() or None, is_secret=False)
    if data.access_token is not None and data.access_token != "***":
        if data.access_token.strip() == "":
            from app.models.app_setting import AppSetting
            existing = db.get(AppSetting, "SHOPIFY_ACCESS_TOKEN")
            if existing:
                db.delete(existing)
        else:
            set_setting(db, "SHOPIFY_ACCESS_TOKEN", data.access_token.strip(), is_secret=True)
    if data.enabled is not None:
        set_setting(db, "SHOPIFY_ENABLED", "true" if data.enabled else "false", is_secret=False)
    db.commit()

    domain, token = _shopify_creds(db)
    enabled = (get_setting(db, "SHOPIFY_ENABLED", env_fallback=False) or "").lower() in ("1", "true", "yes")
    return ShopifyStatus(enabled=enabled, configured=bool(domain and token), shop_domain=domain)


@router.post("/shopify/test", response_model=ShopifyTestResult)
async def shopify_test(db: DBSession):
    domain, token = _shopify_creds(db)
    if not (domain and token):
        raise HTTPException(status_code=400, detail="Shop-Domain und Access-Token erforderlich")
    try:
        result = ShopifyConnector(domain, token).test_connection()
        return ShopifyTestResult(ok=True, shop_name=result.get("shop_name"), currency=result.get("currency"))
    except ShopifyError as e:
        return ShopifyTestResult(ok=False, error=str(e))


@router.get("/shopify/orders", response_model=list[dict])
async def shopify_orders(db: DBSession, limit: int = 20):
    """Jüngste Shopify-Bestellungen als Vorschau (read-only)."""
    domain, token = _shopify_creds(db)
    if not (domain and token):
        raise HTTPException(status_code=400, detail="Shopify nicht konfiguriert")
    try:
        return ShopifyConnector(domain, token).list_recent_orders(limit=limit)
    except ShopifyError as e:
        raise HTTPException(status_code=502, detail=f"Shopify: {e}")
