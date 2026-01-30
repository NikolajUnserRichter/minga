from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from keycloak import KeycloakOpenID
from jose import JWTError, jwt
from app.config import get_settings

settings = get_settings()

# Initialize Keycloak Client
# Note: We don't necessarily need client_secret for public client token validation
# if we just verify the signature using the realm's public key.
keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_url,
    client_id=settings.keycloak_client_id,
    realm_name=settings.keycloak_realm,
    verify=True
)

def get_public_key() -> str:
    """
    Fetches the public key from Keycloak.
    In a real app, you should cache this key.
    python-keycloak might cache it internally or we can use lru_cache.
    """
    # Simply wrapping public_key call.
    # Format needs to be PEM. keycloak_openid.public_key() returns just the base64 string.
    key_pem = "-----BEGIN PUBLIC KEY-----\n" + keycloak_openid.public_key() + "\n-----END PUBLIC KEY-----"
    return key_pem

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifies the JWT token locally using Keycloak's public key.
    Returns the decoded token claims if valid.
    Raises HTTPException if invalid.
    """
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
