"""
API Dependencies - Gemeinsame Abhängigkeiten für Endpoints
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

# Type Alias für DB Session Dependency
DBSession = Annotated[Session, Depends(get_db)]


async def get_current_user():
    """
    Dependency für authentifizierten Benutzer.
    TODO: Keycloak Integration implementieren
    """
    # Placeholder für Keycloak-Integration
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "username": "admin",
        "roles": ["admin", "production_planner"]
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
