"""
API Dependencies - Gemeinsame Abhängigkeiten für Endpoints
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from fastapi.security import OAuth2PasswordBearer
from app.core.security import verify_token
# Type Alias für DB Session Dependency
DBSession = Annotated[Session, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # URL is just for Swagger UI hint

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Dependency für authentifizierten Benutzer.
    Verifiziert das JWT Token gegen Keycloak.
    """
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
