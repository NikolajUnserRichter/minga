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

async def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)]):
    """
    Dependency für authentifizierten Benutzer.
    Verifiziert das JWT Token gegen Keycloak.
    """
    if settings.auth_disabled:
        # Sentinel UUID so callers that wrap user["id"] in UUID(...) don't crash.
        # Order/Invoice.created_by has no FK constraint, so any valid UUID is fine.
        dev_user_id = "00000000-0000-0000-0000-000000000001"
        return {
            "id": dev_user_id,
            "username": "admin",
            "email": "admin@minga-greens.de",
            "roles": ["admin", "sales", "production_planner", "production_staff", "accounting"],
            "raw": {"sub": dev_user_id},
        }

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    
    # Extrahiere Rollen aus Keycloak Token
    # Struktur: realm_access: { roles: [...] } oder resource_access: { client: { roles: [...] } }
    roles = []
    
    # Realm Roles
    if "realm_access" in payload and "roles" in payload["realm_access"]:
        roles.extend(payload["realm_access"]["roles"])
        
    # Resource (Client) Roles - optional, falls wir client-spezifische Rollen nutzen
    # Für Einfachheit nehmen wir erstmal Realm Roles
    
    return {
        "id": payload.get("sub"), # Keycloak User ID
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "roles": roles,
        "raw": payload
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
