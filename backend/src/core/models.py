"""Database models for cache persistence."""

from datetime import datetime
from typing import TypedDict

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class OHLCVPoint(TypedDict):
    """Typed structure for cached OHLCV points."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockCache(Base):
    """Cached stock payload keyed by symbol, interval, and period."""

    __tablename__ = "stock_cache"
    __table_args__ = (UniqueConstraint("symbol", "interval", "period", name="uq_stock_cache_lookup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    data: Mapped[list[OHLCVPoint]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
