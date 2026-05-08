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
        # Get public key (should be cached in production)
        public_key = get_public_key()
        
        # Decode and verify
        # python-keycloak decode_token is a wrapper around python-jose/jwt
        # options = {"verify_signature": True, "verify_aud": True, "exp": True}
        # But verify_aud works differently depending on library versions.
        # Let's use python-jose directly for maximum control if needed, 
        # or use the wrapper. Wrapper is easier.
        
        options = {
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True
        }
        
        token_info = keycloak_openid.decode_token(
            token,
            key=public_key,
            options=options
        )
        
        return token_info
        
    except Exception as e:
        # Log error in production
        # print(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
