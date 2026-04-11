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
