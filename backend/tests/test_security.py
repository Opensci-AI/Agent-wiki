import pytest
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

def test_password_hash_and_verify():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False

def test_create_and_decode_access_token():
    token = create_access_token(subject="user-id-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["type"] == "access"

def test_create_and_decode_refresh_token():
    token = create_refresh_token(subject="user-id-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["type"] == "refresh"

def test_decode_invalid_token():
    with pytest.raises(Exception):
        decode_token("invalid.token.here")

def test_expired_token():
    from datetime import timedelta, datetime, timezone
    from jose import jwt
    from app.config import settings
    expired = jwt.encode(
        {"sub": "user-id", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        settings.jwt_secret, algorithm="HS256"
    )
    with pytest.raises(ValueError):
        decode_token(expired)
