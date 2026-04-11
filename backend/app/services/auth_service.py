import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token

async def register_user(db: AsyncSession, email: str, password: str, display_name: str) -> tuple[User, str, str]:
    existing = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return user, access, refresh

async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return user, access, refresh

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    return result.scalar_one_or_none()

async def get_or_create_oauth_user(db: AsyncSession, email: str, display_name: str, provider: str, oauth_id: str) -> tuple[User, str, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            await db.commit()
    else:
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=display_name,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return user, access, refresh
