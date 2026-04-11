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
            # language stored as {"value": "en"} in JSONB, unwrap to string
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
