"""
API Dependencies - Gemeinsame Abhängigkeiten für Endpoints
"""
from typing import Annotated, Generator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings

from fastapi.security import OAuth2PasswordBearer
from app.core.security import verify_token


def _tenant_db(request: Request) -> Generator[Session, None, None]:
    """Wrappt get_db() und reicht den Request für Tenant-Routing durch."""
    yield from get_db(request)


# Type Alias für DB Session Dependency — pro Request automatisch tenant-scoped.
DBSession = Annotated[Session, Depends(_tenant_db)]

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False) # URL is just for Swagger UI hint

async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
):
    """
    Dependency für authentifizierten Benutzer.

    Reihenfolge:
      1. AUTH_DISABLED → Sentinel-Admin (Dev-Modus)
      2. Basic-Auth-User aus Request-State (gesetzt von basic_auth_middleware) → akzeptieren
      3. Bearer-JWT aus Keycloak → validieren + tenant_slug-Cross-Check vs Subdomain
    """
    if settings.auth_disabled:
        dev_user_id = "00000000-0000-0000-0000-000000000001"
        return {
            "id": dev_user_id,
            "username": "admin",
            "email": "admin@minga-greens.de",
            "roles": ["admin", "sales", "production_planner", "production_staff", "accounting"],
            "raw": {"sub": dev_user_id},
        }

    # Falls Basic-Auth-Middleware bereits einen User gesetzt hat → übernehmen
    basic_user = getattr(request.state, "basic_auth_user", None)
    if basic_user is not None:
        return {
            "id": "basic-auth:" + basic_user["username"],
            "username": basic_user["username"],
            "email": basic_user["username"],
            "roles": ["admin"] if basic_user["role"] == "FULL" else ["readonly"],
            "raw": {"basic_auth": True, "role": basic_user["role"]},
        }

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)

    # === Multi-Tenant Cross-Check ===
    # JWT-Claim 'tenant_slug' muss zur Subdomain des aktuellen Requests passen.
    # Verhindert dass ein User mit Token für Tenant A bei Tenant B reinkommt.
    from app.tenancy import get_request_tenant
    request_tenant = get_request_tenant(request)
    token_tenant = payload.get("tenant_slug")

    # Wenn beide leer → ok (z.B. Dev-Localhost-Default-Tenant)
    if request_tenant and token_tenant and request_tenant != token_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token gehört zu Tenant '{token_tenant}', Request ist für Tenant '{request_tenant}'.",
        )
    if request_tenant and not token_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token enthält keinen tenant_slug-Claim — User ist keinem Workspace zugeordnet.",
        )

    roles: list[str] = []
    if "realm_access" in payload and "roles" in payload["realm_access"]:
        roles.extend(payload["realm_access"]["roles"])

    return {
        "id": payload.get("sub"),
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "tenant_slug": token_tenant,
        "roles": roles,
        "raw": payload,
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_role(required_roles: list[str]):
    """
    Dependency Factory für Rollenprüfung.

    Verwendung:
        @router.get("/admin", dependencies=[Depends(require_role(["admin"]))])
    """
    async def check_role(user: CurrentUser):
        user_roles = user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Keine Berechtigung für diese Aktion"
            )
        return user
    return check_role


# Pagination Parameter
class PaginationParams:
    """Standard Pagination Parameter"""
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
        max_page_size: int = 100
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), max_page_size)
        self.offset = (self.page - 1) * self.page_size


Pagination = Annotated[PaginationParams, Depends()]
