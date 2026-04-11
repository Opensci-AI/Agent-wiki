import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select

from app.config import settings
from app.db.session import async_session
from app.models.user import User
from app.core.security import hash_password

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
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
    from app.core.background import recover_orphaned_tasks
    await recover_orphaned_tasks()
    yield

app = FastAPI(title="LLM Wiki API", version="0.1.0", lifespan=lifespan)
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

from app.api.auth import router as auth_router
app.include_router(auth_router)

from app.api.projects import router as projects_router
app.include_router(projects_router)

from app.api.config_routes import router as config_router
app.include_router(config_router)

from app.api.pages import router as pages_router
app.include_router(pages_router)

from app.api.sources import router as sources_router
app.include_router(sources_router)

from app.api.chat import router as chat_router
app.include_router(chat_router)

from app.api.streams import router as streams_router
app.include_router(streams_router)

from app.api.ingest import router as ingest_router
app.include_router(ingest_router)

from app.api.research import router as research_router
app.include_router(research_router)

from app.api.reviews import router as reviews_router
app.include_router(reviews_router)

from app.api.graph import router as graph_router
app.include_router(graph_router)

from app.api.search import router as search_router
app.include_router(search_router)

from app.api.lint import router as lint_router
app.include_router(lint_router)

from app.api.wiki import router as wiki_router
app.include_router(wiki_router)
