"""Cache service for stock data."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.models import StockCache


class CacheService:
    """Manage cache reads/writes for stock OHLCV payloads."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def get_cached(self, symbol: str, interval: str, period: str) -> list[dict] | None:
        """Return cached payload if not expired."""
        now = datetime.now(UTC)
        statement = select(StockCache.data).where(
            StockCache.symbol == symbol.upper(),
            StockCache.interval == interval,
            StockCache.period == period,
            StockCache.expires_at > now,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def set_cached(self, symbol: str, interval: str, period: str, data: list[dict]) -> None:
        """Upsert cache payload with configured TTL."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=self.settings.cache_ttl_hours)
        statement = insert(StockCache).values(
            symbol=symbol.upper(),
            interval=interval,
            period=period,
            data=data,
            created_at=now,
            expires_at=expires_at,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_stock_cache_lookup",
            set_={"data": data, "created_at": now, "expires_at": expires_at},
        )
        await self.session.execute(statement)
        await self.session.commit()

    async def invalidate(self, symbol: str, interval: str, period: str) -> None:
        """Delete a specific cache entry."""
        statement = delete(StockCache).where(
            StockCache.symbol == symbol.upper(),
            StockCache.interval == interval,
            StockCache.period == period,
        )
        await self.session.execute(statement)
        await self.session.commit()

    async def get_stats(self) -> dict[str, int]:
        """Return simple cache statistics."""
        now = datetime.now(UTC)
        total = await self.session.scalar(select(func.count()).select_from(StockCache))
        active = await self.session.scalar(
            select(func.count()).select_from(StockCache).where(StockCache.expires_at > now)
        )
        expired = (total or 0) - (active or 0)
        return {"total": total or 0, "active": active or 0, "expired": expired}
