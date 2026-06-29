from typing import Optional, Dict, Any
import time
import threading
from fastapi import HTTPException, status
from keycloak import KeycloakOpenID
from jose import JWTError, jwt
from app.config import get_settings

settings = get_settings()

# Initialize Keycloak Client
keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_url,
    client_id=settings.keycloak_client_id,
    realm_name=settings.keycloak_realm,
    verify=True
)

# Cached public key with TTL (5 minutes)
_public_key_cache: Dict[str, Any] = {"key": None, "expires_at": 0.0}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 300  # 5 minutes


def get_public_key() -> str:
    """
    Fetches the public key from Keycloak with a 5-minute TTL cache.
    Thread-safe.
    """
    now = time.monotonic()
    if _public_key_cache["key"] and now < _public_key_cache["expires_at"]:
        return _public_key_cache["key"]

    with _cache_lock:
        # Double-check after acquiring lock
        now = time.monotonic()
        if _public_key_cache["key"] and now < _public_key_cache["expires_at"]:
            return _public_key_cache["key"]

        raw_key = keycloak_openid.public_key()
        key_pem = "-----BEGIN PUBLIC KEY-----\n" + raw_key + "\n-----END PUBLIC KEY-----"
        _public_key_cache["key"] = key_pem
        _public_key_cache["expires_at"] = now + _CACHE_TTL_SECONDS
        return key_pem

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifies the JWT token locally using Keycloak's public key.
    Returns the decoded token claims if valid.
    Raises HTTPException if invalid.
    """
    if settings.auth_disabled:
        return {
            "sub": "dev-user",
            "preferred_username": "admin",
            "email": "admin@minga-greens.de",
            "realm_access": {
                "roles": ["admin", "sales", "production_planner", "production_staff", "accounting"]
            },
        }

    try:
        public_key = get_public_key()

        # Manuelle Verifizierung mit python-jose — verify_aud=False, weil Keycloaks
        # Default-Audience "account" nicht zwingend dem Client-ID entspricht.
        # Audience-Mapper im Realm kann zusätzlich client_id in aud aufnehmen, aber
        # die Tokens sind ohnehin signaturgesichert (RS256) + Issuer-gebunden.
        expected_iss = f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"
        token_info = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_exp": True,
                "verify_iss": True,
            },
            issuer=expected_iss,
        )
        return token_info

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token-Verifizierung fehlgeschlagen: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
