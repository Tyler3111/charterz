"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.database import get_db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide database session dependency."""
    async for session in get_db():
        yield session


def get_app_settings() -> Settings:
    """Provide app settings dependency."""
    return get_settings()
