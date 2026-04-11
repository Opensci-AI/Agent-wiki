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
