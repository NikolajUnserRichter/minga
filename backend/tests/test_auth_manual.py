import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.api.deps import get_current_user

@pytest.mark.asyncio
async def test_auth_success():
    # Mock Token Payload
    mock_payload = {
        "sub": "user-123",
        "preferred_username": "testuser",
        "email": "test@example.com",
        "realm_access": {
            "roles": ["admin", "staff"]
        }
    }
    
    # Patch verify_token
    with patch("app.api.deps.verify_token", return_value=mock_payload):
        user = await get_current_user(token="valid-token")
        
        assert user["id"] == "user-123"
        assert "admin" in user["roles"]
        assert user["username"] == "testuser"

@pytest.mark.asyncio
async def test_auth_failure():
    # Patch verify_token to raise Exception
    with patch("app.api.deps.verify_token", side_effect=HTTPException(status_code=401, detail="Invalid token")):
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(token="invalid-token")
        
        assert excinfo.value.status_code == 401
