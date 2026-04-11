# Plan 1: Backend Core — Auth, Projects, Config

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI backend with user auth (email/password + OAuth), project CRUD, and config management — the foundation all other plans depend on.

**Architecture:** 3-layer FastAPI app (api routes → services → SQLAlchemy models) with async PostgreSQL, JWT auth (access + refresh tokens), and Alembic migrations. All endpoints return JSON with consistent error format.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, asyncpg, python-jose (JWT), passlib[bcrypt], httpx (OAuth), pytest + httpx (testing), pydantic-settings, slowapi (rate limiting)

**Spec:** `docs/superpowers/specs/2026-04-10-llm-wiki-web-design.md`

**Design decisions (v1):**
- Refresh token revocation: no server-side blocklist in v1. Old refresh tokens remain valid until expiry. Acceptable for self-host single-instance.
- OAuth account linking: if a user registered with email+password, then logs in via OAuth with the same email, the accounts are linked automatically. This is a conscious simplicity trade-off for v1.

---

## File Structure

```
backend/
├── .gitignore                     # venv, __pycache__, .env, *.pyc
├── pyproject.toml                 # pytest-asyncio config
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, CORS, lifespan (admin seed), rate limiting
│   ├── config.py                  # pydantic-settings: env vars → Settings
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py             # async engine + sessionmaker + get_db dependency
│   │   └── base.py                # declarative base for all models
│   │
│   ├── models/
│   │   ├── __init__.py            # re-export all models (for Alembic)
│   │   ├── user.py                # User ORM
│   │   ├── project.py             # Project ORM
│   │   └── config.py              # SystemConfig + UserConfig ORM
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                # Register/Login/Token/UserResponse
│   │   ├── project.py             # ProjectCreate/Update/Response
│   │   └── config.py              # ConfigResponse/ConfigUpdate
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # register, login, oauth, refresh
│   │   ├── project_service.py     # CRUD + scaffold defaults
│   │   └── config_service.py      # merged config resolution
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── security.py            # JWT create/decode, password hash/verify
│   │
│   └── api/
│       ├── __init__.py
│       ├── deps.py                # get_current_user, require_admin, require_project_owner
│       ├── auth.py                # /auth/* routes
│       ├── projects.py            # /projects/* routes
│       └── config_routes.py       # /config, /admin/config routes
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # async test fixtures, test DB, test client
│   ├── test_auth.py
│   ├── test_projects.py
│   └── test_config.py
│
├── alembic/
│   ├── env.py
│   └── versions/                  # auto-generated migrations
│
├── alembic.ini
├── requirements.txt
├── .env.example
└── .env                           # local dev (gitignored)
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.env`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create requirements.txt**

```
# backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
alembic==1.14.0
pydantic[email]==2.9.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.27.0
python-multipart==0.0.12
slowapi==0.1.9
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create .env.example and .env**

```env
# backend/.env.example
DATABASE_URL=postgresql+asyncpg://wiki:wiki@localhost:5432/llm_wiki
JWT_SECRET=change-me-to-a-random-secret
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173
BACKEND_URL=http://localhost:8000
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme
STORAGE_PATH=./data/uploads
DEFAULT_LLM_API_KEY=
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_GITHUB_CLIENT_ID=
OAUTH_GITHUB_CLIENT_SECRET=
```

Add `BACKEND_URL` for OAuth callback redirect.

Copy `.env.example` → `.env` for local dev.

- [ ] **Step 2b: Create .gitignore and pyproject.toml**

```gitignore
# backend/.gitignore
.env
venv/
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
data/
```

```toml
# backend/pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Create config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wiki:wiki@localhost:5432/llm_wiki"
    jwt_secret: str = "change-me"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    cors_origins: str = "http://localhost:5173"
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme"
    backend_url: str = "http://localhost:8000"
    storage_path: str = "./data/uploads"
    default_llm_api_key: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
```

- [ ] **Step 4: Create main.py (minimal)**

```python
# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import settings

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="LLM Wiki API", version="0.1.0")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
```

Note: Individual route rate limits (e.g., `@limiter.limit("5/minute")` on auth endpoints) will be applied in the route files.

- [ ] **Step 5: Create __init__.py files**

Empty `__init__.py` for: `app/`, `app/db/`, `app/models/`, `app/schemas/`, `app/services/`, `app/core/`, `app/api/`, `tests/`

- [ ] **Step 6: Verify server starts**

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Visit http://localhost:8000/api/v1/health → {"status": "ok"}
# Visit http://localhost:8000/docs → Swagger UI
```

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI project with config and health endpoint"
```

---

### Task 2: Database Setup

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: Create declarative base**

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create async session**

```python
# backend/app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 3: Initialize Alembic**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 4: Configure alembic/env.py**

Replace the generated `env.py` with async support:

```python
# backend/alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.config import settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403 — register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 5: Update alembic.ini**

Set `sqlalchemy.url` to empty (we use `settings.database_url` instead):

```ini
# In alembic.ini, change:
sqlalchemy.url =
```

- [ ] **Step 6: Start PostgreSQL and verify connection**

```bash
docker run -d --name llm-wiki-db \
  -e POSTGRES_USER=wiki -e POSTGRES_PASSWORD=wiki -e POSTGRES_DB=llm_wiki \
  -p 5432:5432 postgres:16-alpine

# Verify:
cd backend && python -c "
import asyncio
from app.db.session import engine
async def test():
    async with engine.connect() as conn:
        result = await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        print('DB connected:', result.scalar())
asyncio.run(test())
"
```

Expected: `DB connected: 1`

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/ backend/alembic/ backend/alembic.ini
git commit -m "feat(backend): add async SQLAlchemy + Alembic setup"
```

---

### Task 3: User Model + Migration

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write User model**

```python
# backend/app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register model in __init__.py**

```python
# backend/app/models/__init__.py
from app.models.user import User

__all__ = ["User"]
```

- [ ] **Step 3: Create test fixtures**

```python
# backend/tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://wiki:wiki@localhost:5432/llm_wiki_test"

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="session")
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Note: `pyproject.toml` sets `asyncio_mode = "auto"`, so no `@pytest.mark.asyncio` needed (but keeping them is fine). No deprecated `event_loop` fixture — pytest-asyncio 0.24 handles loop lifecycle.

- [ ] **Step 4: Write model test**

```python
# backend/tests/test_models.py
import pytest
from app.models.user import User

@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(email="test@example.com", display_name="Test User", password_hash="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_admin is False
    assert user.deleted_at is None
```

- [ ] **Step 5: Create test database and run test**

```bash
docker exec llm-wiki-db psql -U wiki -c "CREATE DATABASE llm_wiki_test;"
cd backend && python -m pytest tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 6: Generate Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/ backend/tests/ backend/alembic/
git commit -m "feat(backend): add User model with migration and tests"
```

---

### Task 4: Security Module (JWT + Password Hashing)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_security.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_security.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement security module**

```python
# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
    return jwt.encode({"sub": subject, "type": "access", "exp": expire}, settings.jwt_secret, algorithm="HS256")

def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    return jwt.encode({"sub": subject, "type": "refresh", "exp": expire}, settings.jwt_secret, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_security.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(backend): add JWT and password hashing security module"
```

---

### Task 5: Auth Schemas

**Files:**
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Create auth schemas**

```python
# backend/app/schemas/auth.py
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    oauth_provider: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

Note: `EmailStr` requires `pip install pydantic[email]` — add `pydantic[email]` to requirements.txt.

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/auth.py
git commit -m "feat(backend): add auth Pydantic schemas"
```

---

### Task 6: Auth Service

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "secret123",
        "display_name": "New User"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "secret123", "display_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com", "password": "secret123", "display_name": "Login User"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com", "password": "secret123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com", "password": "secret123", "display_name": "Wrong"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com", "password": "badpass"
    })
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_get_me(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "me@example.com", "password": "secret123", "display_name": "Me"
    })
    token = reg.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"

@pytest.mark.asyncio
async def test_get_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```

Expected: FAIL — routes don't exist yet

- [ ] **Step 3: Implement auth service**

```python
# backend/app/services/auth_service.py
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
```

- [ ] **Step 4: Implement auth dependencies**

```python
# backend/app/api/deps.py
import uuid
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User
from app.services.auth_service import get_user_by_id

async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"detail": "Invalid token type", "code": "INVALID_TOKEN"})
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user
```

- [ ] **Step 5: Implement auth routes**

```python
# backend/app/api/auth.py
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import register_user, login_user
from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, access, refresh = await register_user(db, req.email, req.password, req.display_name)
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, access, refresh = await login_user(db, req.email, req.password)
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
```

- [ ] **Step 6: Register router in main.py**

```python
# In backend/app/main.py, add:
from app.api.auth import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```

Expected: 6 PASSED

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/auth_service.py backend/app/api/deps.py backend/app/api/auth.py backend/app/schemas/auth.py backend/tests/test_auth.py backend/app/main.py
git commit -m "feat(backend): add auth service with register, login, and JWT"
```

---

### Task 7: Token Refresh Endpoint

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_refresh_token(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com", "password": "secret123", "display_name": "Refresh"
    })
    # Refresh token is in httpOnly cookie — extract from response
    refresh_cookie = reg.cookies.get("refresh_token")
    assert refresh_cookie is not None
    resp = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

@pytest.mark.asyncio
async def test_refresh_no_cookie(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
```

- [ ] **Step 2: Implement refresh endpoint**

Add to `backend/app/api/auth.py`:

```python
from fastapi import Cookie

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(None),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail={"detail": "Invalid refresh token", "code": "INVALID_TOKEN"})
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail={"detail": "Invalid token type", "code": "INVALID_TOKEN"})
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    response.set_cookie(
        key="refresh_token", value=new_refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=new_access)
```

Add imports: `from fastapi import Cookie, HTTPException` and `from app.core.security import decode_token, create_access_token, create_refresh_token` and `from app.services.auth_service import get_user_by_id` and `import uuid`

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```

Expected: 8 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add token refresh endpoint with cookie rotation"
```

---

### Task 8: OAuth Routes (Google + GitHub)

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: Write test for OAuth initiation redirect**

```python
@pytest.mark.asyncio
async def test_oauth_redirect_google(client):
    resp = await client.get("/api/v1/auth/oauth/google", follow_redirects=False)
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]

@pytest.mark.asyncio
async def test_oauth_redirect_github(client):
    resp = await client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    assert resp.status_code == 307
    assert "github.com" in resp.headers["location"]

@pytest.mark.asyncio
async def test_oauth_invalid_provider(client):
    resp = await client.get("/api/v1/auth/oauth/twitter", follow_redirects=False)
    assert resp.status_code == 400
```

- [ ] **Step 2: Implement OAuth routes**

Add to `backend/app/api/auth.py`:

```python
from fastapi import Query
from fastapi.responses import RedirectResponse
import httpx

OAUTH_CONFIGS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": "openid email profile",
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": "read:user user:email",
    },
}

def _get_oauth_settings(provider: str):
    if provider == "google":
        return settings.oauth_google_client_id, settings.oauth_google_client_secret
    elif provider == "github":
        return settings.oauth_github_client_id, settings.oauth_github_client_secret
    return "", ""

@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str):
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    cfg = OAUTH_CONFIGS[provider]
    client_id, _ = _get_oauth_settings(provider)
    redirect_uri = f"{settings.backend_url}/api/v1/auth/oauth/{provider}/callback"
    url = f"{cfg['auth_url']}?client_id={client_id}&redirect_uri={redirect_uri}&scope={cfg['scopes']}&response_type=code"
    return RedirectResponse(url=url)

@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    response: Response = ...,
    db: AsyncSession = Depends(get_db),
):
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    cfg = OAUTH_CONFIGS[provider]
    client_id, client_secret = _get_oauth_settings(provider)
    redirect_uri = f"{settings.backend_url}/api/v1/auth/oauth/{provider}/callback"

    async with httpx.AsyncClient() as http:
        # Exchange code for token
        token_resp = await http.post(cfg["token_url"], data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }, headers={"Accept": "application/json"})
        token_data = token_resp.json()
        oauth_token = token_data.get("access_token")
        if not oauth_token:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        # Get user info
        userinfo_resp = await http.get(cfg["userinfo_url"], headers={"Authorization": f"Bearer {oauth_token}"})
        userinfo = userinfo_resp.json()

    if provider == "google":
        email = userinfo.get("email")
        name = userinfo.get("name", email)
        oauth_id = userinfo.get("id")
    elif provider == "github":
        email = userinfo.get("email")
        if not email:
            # GitHub may not return email in profile — fetch from emails endpoint
            async with httpx.AsyncClient() as http:
                emails_resp = await http.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {oauth_token}"})
                emails = emails_resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                email = primary["email"] if primary else None
        name = userinfo.get("name") or userinfo.get("login", "")
        oauth_id = str(userinfo.get("id"))

    if not email:
        raise HTTPException(status_code=400, detail="Could not get email from provider")

    user, access, refresh = await get_or_create_oauth_user(db, email, name, provider, oauth_id)
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)
```

Add import: `from app.services.auth_service import get_or_create_oauth_user`

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```

Expected: 11 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add OAuth redirect and callback for Google + GitHub"
```

---

### Task 9: Project Model + Schemas

**Files:**
- Create: `backend/app/models/project.py`
- Create: `backend/app/schemas/project.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Project model**

```python
# backend/app/models/project.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text, default="")
    schema_text: Mapped[str] = mapped_column("wiki_schema", Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Note: `schema_text` maps to column name `schema` (avoids Python keyword conflict).

- [ ] **Step 2: Create Project schemas**

```python
# backend/app/schemas/project.py
import uuid
from datetime import datetime
from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    # template_id will be added in Plan 2 when page scaffolding is implemented

class ProjectUpdate(BaseModel):
    name: str | None = None
    purpose: str | None = None
    schema_text: str | None = None

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    purpose: str
    schema_text: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ProjectListResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Update models __init__.py**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.project import Project

__all__ = ["User", "Project"]
```

- [ ] **Step 4: Generate migration and run**

```bash
cd backend && alembic revision --autogenerate -m "add projects table"
alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ backend/app/schemas/project.py backend/alembic/
git commit -m "feat(backend): add Project model and schemas"
```

---

### Task 10: Project Service + Routes

**Files:**
- Create: `backend/app/services/project_service.py`
- Create: `backend/app/api/projects.py`
- Create: `backend/tests/test_projects.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_projects.py
import pytest

async def _register(client, email="proj@example.com"):
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "secret123", "display_name": "Proj User"
    })
    return resp.json()["access_token"]

@pytest.mark.asyncio
async def test_create_project(client):
    token = await _register(client)
    resp = await client.post("/api/v1/projects", json={"name": "My Wiki"},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Wiki"
    assert "id" in data

@pytest.mark.asyncio
async def test_list_projects(client):
    token = await _register(client, "list@example.com")
    await client.post("/api/v1/projects", json={"name": "Wiki 1"},
        headers={"Authorization": f"Bearer {token}"})
    await client.post("/api/v1/projects", json={"name": "Wiki 2"},
        headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

@pytest.mark.asyncio
async def test_get_project(client):
    token = await _register(client, "get@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Detail Wiki"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail Wiki"

@pytest.mark.asyncio
async def test_get_project_not_owner(client):
    token1 = await _register(client, "owner1@example.com")
    token2 = await _register(client, "owner2@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Private"},
        headers={"Authorization": f"Bearer {token1}"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_update_project(client):
    token = await _register(client, "update@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Old Name"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.patch(f"/api/v1/projects/{pid}", json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

@pytest.mark.asyncio
async def test_delete_project(client):
    token = await _register(client, "delete@example.com")
    create = await client.post("/api/v1/projects", json={"name": "To Delete"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    # Should not appear in list
    list_resp = await client.get("/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()) == 0
    # Verify GET by ID also returns 404 for deleted project
    get_resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_projects.py -v
```

Expected: FAIL

- [ ] **Step 3: Add require_project_owner dependency**

Add to `backend/app/api/deps.py`:

```python
from app.models.project import Project
from sqlalchemy import select

async def require_project_owner(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

- [ ] **Step 4: Implement project service**

```python
# backend/app/services/project_service.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project

async def create_project(db: AsyncSession, owner_id: uuid.UUID, name: str, purpose: str = "", schema_text: str = "") -> Project:
    project = Project(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=name,
        purpose=purpose,
        schema_text=schema_text,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project

async def list_projects(db: AsyncSession, owner_id: uuid.UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.owner_id == owner_id, Project.deleted_at.is_(None)).order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())

async def update_project(db: AsyncSession, project: Project, name: str | None, purpose: str | None, schema_text: str | None) -> Project:
    if name is not None:
        project.name = name
    if purpose is not None:
        project.purpose = purpose
    if schema_text is not None:
        project.schema_text = schema_text
    await db.commit()
    await db.refresh(project)
    return project

async def soft_delete_project(db: AsyncSession, project: Project) -> None:
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
```

- [ ] **Step 5: Implement project routes**

```python
# backend/app/api/projects.py
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.services.project_service import create_project, list_projects, update_project, soft_delete_project
from app.api.deps import get_current_user, require_project_owner

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse, status_code=201)
async def create(req: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await create_project(db, user.id, req.name)
    return project

@router.get("", response_model=list[ProjectListResponse])
async def list_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_projects(db, user.id)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get(project: Project = Depends(require_project_owner)):
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update(req: ProjectUpdate, project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    return await update_project(db, project, req.name, req.purpose, req.schema_text)

@router.delete("/{project_id}", status_code=204)
async def delete(project: Project = Depends(require_project_owner), db: AsyncSession = Depends(get_db)):
    await soft_delete_project(db, project)
```

- [ ] **Step 6: Register router in main.py**

```python
from app.api.projects import router as projects_router
app.include_router(projects_router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_projects.py -v
```

Expected: 6 PASSED

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/project_service.py backend/app/api/projects.py backend/app/api/deps.py backend/tests/test_projects.py backend/app/main.py
git commit -m "feat(backend): add project CRUD with ownership guard"
```

---

### Task 11: Config Models + Service

**Files:**
- Create: `backend/app/models/config.py`
- Create: `backend/app/schemas/config.py`
- Create: `backend/app/services/config_service.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Config models**

```python
# backend/app/models/config.py
import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)

class UserConfig(Base):
    __tablename__ = "user_config"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
```

- [ ] **Step 2: Create Config schemas**

```python
# backend/app/schemas/config.py
from pydantic import BaseModel
from typing import Any

class ConfigResponse(BaseModel):
    llm_config: dict[str, Any] | None = None
    search_config: dict[str, Any] | None = None
    language: str | None = None

class ConfigUpdate(BaseModel):
    llm_config: dict[str, Any] | None = None
    search_config: dict[str, Any] | None = None
    language: str | None = None
```

- [ ] **Step 3: Implement config service**

```python
# backend/app/services/config_service.py
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import SystemConfig, UserConfig

VALID_KEYS = {"llm_config", "search_config", "language"}

async def get_system_config(db: AsyncSession) -> dict:
    result = await db.execute(select(SystemConfig))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}

async def set_system_config(db: AsyncSession, key: str, value: dict) -> None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(SystemConfig(key=key, value=value))
    await db.commit()

async def get_user_config(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(UserConfig).where(UserConfig.user_id == user_id))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}

async def set_user_config(db: AsyncSession, user_id: uuid.UUID, key: str, value: dict) -> None:
    result = await db.execute(select(UserConfig).where(UserConfig.user_id == user_id, UserConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(UserConfig(user_id=user_id, key=key, value=value))
    await db.commit()

async def get_effective_config(db: AsyncSession, user_id: uuid.UUID) -> dict:
    system = await get_system_config(db)
    user = await get_user_config(db, user_id)
    merged = {}
    for key in VALID_KEYS:
        sys_val = system.get(key)
        usr_val = user.get(key)
        if key == "language":
            # language is stored as {"value": "en"} in JSONB, unwrap to string
            val = usr_val or sys_val
            if val and isinstance(val, dict):
                merged[key] = val.get("value")
            elif val:
                merged[key] = val
        else:
            if usr_val is not None:
                if isinstance(sys_val, dict) and isinstance(usr_val, dict):
                    merged[key] = {**sys_val, **usr_val}
                else:
                    merged[key] = usr_val
            elif sys_val is not None:
                merged[key] = sys_val
    return merged
```

- [ ] **Step 4: Update models __init__.py**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.project import Project
from app.models.config import SystemConfig, UserConfig

__all__ = ["User", "Project", "SystemConfig", "UserConfig"]
```

- [ ] **Step 5: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "add config tables"
alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/ backend/app/schemas/config.py backend/app/services/config_service.py backend/alembic/
git commit -m "feat(backend): add config models and service with merged resolution"
```

---

### Task 12: Config Routes + Tests

**Files:**
- Create: `backend/app/api/config_routes.py`
- Create: `backend/tests/test_config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_config.py
import pytest

async def _register(client, email="cfg@example.com", is_admin=False):
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "secret123", "display_name": "Cfg User"
    })
    return resp.json()["access_token"]

@pytest.mark.asyncio
async def test_get_config_empty(client):
    token = await _register(client)
    resp = await client.get("/api/v1/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_put_user_config(client):
    token = await _register(client, "put@example.com")
    resp = await client.put("/api/v1/config", json={
        "llm_config": {"provider": "openrouter", "model": "claude-sonnet-4"}
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    # Verify it's persisted
    get_resp = await client.get("/api/v1/config", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.json()["llm_config"]["provider"] == "openrouter"

@pytest.mark.asyncio
async def test_admin_config_requires_admin(client):
    token = await _register(client, "nonadmin@example.com")
    resp = await client.get("/api/v1/admin/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Implement config routes**

```python
# backend/app/api/config_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.config import ConfigResponse, ConfigUpdate
from app.services.config_service import get_effective_config, set_user_config, get_system_config, set_system_config
from app.api.deps import get_current_user, require_admin

router = APIRouter(tags=["config"])

@router.get("/api/v1/config", response_model=ConfigResponse)
async def get_config(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    merged = await get_effective_config(db, user.id)
    return ConfigResponse(**merged)

@router.put("/api/v1/config", response_model=ConfigResponse)
async def update_config(req: ConfigUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if req.llm_config is not None:
        await set_user_config(db, user.id, "llm_config", req.llm_config)
    if req.search_config is not None:
        await set_user_config(db, user.id, "search_config", req.search_config)
    if req.language is not None:
        await set_user_config(db, user.id, "language", {"value": req.language})
    merged = await get_effective_config(db, user.id)
    return ConfigResponse(**merged)

@router.get("/api/v1/admin/config", response_model=ConfigResponse)
async def get_admin_config(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    system = await get_system_config(db)
    return ConfigResponse(**system)

@router.put("/api/v1/admin/config", response_model=ConfigResponse)
async def update_admin_config(req: ConfigUpdate, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if req.llm_config is not None:
        await set_system_config(db, "llm_config", req.llm_config)
    if req.search_config is not None:
        await set_system_config(db, "search_config", req.search_config)
    if req.language is not None:
        await set_system_config(db, "language", {"value": req.language})
    system = await get_system_config(db)
    return ConfigResponse(**system)
```

- [ ] **Step 3: Register router in main.py**

```python
from app.api.config_routes import router as config_router
app.include_router(config_router)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_config.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/config_routes.py backend/tests/test_config.py backend/app/main.py
git commit -m "feat(backend): add config routes with admin/user merge"
```

---

### Task 13: Admin Seed on Startup

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add lifespan with admin seed**

```python
# Update backend/app/main.py
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.core.security import hash_password
import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed admin user on first run
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == settings.admin_email))
        if not result.scalar_one_or_none():
            admin = User(
                id=uuid.uuid4(),
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                display_name="Admin",
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
    yield

# Update app creation:
app = FastAPI(title="LLM Wiki API", version="0.1.0", lifespan=lifespan)
```

- [ ] **Step 2: Test admin login**

```bash
cd backend && python -c "
import asyncio, httpx
async def test():
    async with httpx.AsyncClient(base_url='http://localhost:8000') as c:
        r = await c.post('/api/v1/auth/login', json={'email': 'admin@example.com', 'password': 'changeme'})
        print(r.status_code, r.json())
        token = r.json()['access_token']
        me = await c.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
        print('is_admin:', me.json()['is_admin'])
asyncio.run(test())
"
```

Expected: `200` and `is_admin: True`

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): seed admin user on startup via lifespan"
```

---

### Task 14: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS (auth: 11, projects: 6, config: 3, models: 1, security: 5 = 26 tests)

- [ ] **Step 2: Verify API docs**

```bash
# Start server
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000/docs
# Verify all endpoints listed: health, auth/*, projects/*, config, admin/config
```

- [ ] **Step 3: Final commit**

```bash
git add -A backend/
git commit -m "feat(backend): complete Plan 1 — auth, projects, config"
```

---

## Plan Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Project scaffolding | Manual health check |
| 2 | Database setup | Manual connection check |
| 3 | User model + migration | 1 test |
| 4 | Security module | 5 tests |
| 5 | Auth schemas | N/A (Pydantic) |
| 6 | Auth service + routes | 6 tests |
| 7 | Token refresh | 2 tests |
| 8 | OAuth routes | 3 tests |
| 9 | Project model + schemas | N/A (migration) |
| 10 | Project service + routes | 6 tests |
| 11 | Config models + service | N/A (migration) |
| 12 | Config routes | 3 tests |
| 13 | Admin seed | Manual verification |
| 14 | Full test suite | All 26 tests |

**After this plan:** Backend has auth, project CRUD, config management. Ready for Plan 2 (Pages, Sources, File Upload).
