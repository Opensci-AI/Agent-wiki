import pytest
from app.models.user import User

async def test_create_user(db_session):
    user = User(email="test@example.com", display_name="Test User", password_hash="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_admin is False
    assert user.deleted_at is None
