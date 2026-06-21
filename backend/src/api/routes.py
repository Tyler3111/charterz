"""API routes for stock dashboard backend."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_app_settings, get_db_session
from src.api.schemas import ErrorResponse, StockResponse
from src.core.config import Settings
from src.services.cache_service import CacheService
from src.services.stock_service import (
    StockFetchError,
    StockNotFoundError,
    StockValidationError,
    fetch_stock_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stocks"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@router.get(
    "/stock/{symbol}",
    response_model=StockResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_stock(
    symbol: str,
    interval: str = Query(default="1d"),
    period: str = Query(default="1mo"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> StockResponse:
    """Return OHLCV stock data from cache or upstream source."""
    cache_service = CacheService(session=session, settings=settings)
    print("entere dthe fun")


    cached_data = await cache_service.get_cached(symbol=symbol, interval=interval, period=period)
    if cached_data is not None:
        logger.info("Cache hit", extra={"symbol": symbol.upper(), "interval": interval, "period": period})
        return StockResponse(symbol=symbol.upper(), interval=interval, period=period, cached=True, data=cached_data)

    logger.info("Cache miss", extra={"symbol": symbol.upper(), "interval": interval, "period": period})
    try:
        fresh_data = await fetch_stock_data(symbol=symbol, interval=interval, period=period)
    except StockValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StockNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StockFetchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.exception("Unhandled error while fetching stock")
        raise HTTPException(status_code=500, detail="Unexpected stock fetch error") from exc

    await cache_service.set_cached(symbol=symbol, interval=interval, period=period, data=fresh_data)
    return StockResponse(symbol=symbol.upper(), interval=interval, period=period, cached=False, data=fresh_data)


@router.get("/stats")
async def cache_stats(
    session: AsyncSession = Depends(get_db_session), settings: Settings = Depends(get_app_settings)
) -> dict[str, int]:
    """Return basic cache statistics."""
    cache_service = CacheService(session=session, settings=settings)
    return await cache_service.get_stats()
