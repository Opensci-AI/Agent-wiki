import os
import aiofiles
from abc import ABC, abstractmethod
from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes) -> str: ...
    @abstractmethod
    async def read(self, path: str) -> bytes: ...
    @abstractmethod
    async def delete(self, path: str) -> None: ...
    @abstractmethod
    async def exists(self, path: str) -> bool: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    async def save(self, path: str, data: bytes) -> str:
        full = self._full_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        async with aiofiles.open(full, "wb") as f:
            await f.write(data)
        return path

    async def read(self, path: str) -> bytes:
        async with aiofiles.open(self._full_path(path), "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        full = self._full_path(path)
        if os.path.exists(full):
            os.remove(full)

    async def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))


def get_storage() -> StorageBackend:
    return LocalStorage(settings.storage_path)
