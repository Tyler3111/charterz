"""Stock data fetching and transformation service."""

import asyncio
import logging
from datetime import UTC
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}


class StockNotFoundError(Exception):
    """Raised when a symbol has no retrievable history."""


class StockFetchError(Exception):
    """Raised when stock history cannot be fetched due to upstream issues."""


class StockValidationError(Exception):
    """Raised when request parameters are invalid."""


async def fetch_stock_data(symbol: str, interval: str, period: str, retries: int = 3) -> list[dict[str, Any]]:
    """Fetch stock data from yfinance and transform it to OHLCV payload."""
    ticker_symbol = symbol.upper()
    if interval not in VALID_INTERVALS:
        raise StockValidationError(f"Unsupported interval '{interval}'.")

    logger.info("Fetching stock data", extra={"symbol": ticker_symbol, "interval": interval, "period": period})
    last_exception: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            history = await asyncio.to_thread(_fetch_history, ticker_symbol, interval, period)
            payload = _transform_history(history)
            if not payload:
                raise StockNotFoundError(f"No data found for symbol '{ticker_symbol}'.")
            return payload
        except StockNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive boundary
            last_exception = exc
            logger.warning(
                "Stock fetch attempt failed",
                extra={"symbol": ticker_symbol, "attempt": attempt, "retries": retries, "error": str(exc)},
            )
            if attempt < retries:
                await asyncio.sleep(0.5 * attempt)

    raise StockFetchError(f"Failed to fetch data for '{ticker_symbol}'.") from last_exception


def _fetch_history(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """Fetch raw historical dataframe from yfinance."""
    ticker = yf.Ticker(symbol)
    return ticker.history(interval=interval, period=period, auto_adjust=False)


def _transform_history(history: pd.DataFrame) -> list[dict[str, Any]]:
    """Transform yfinance dataframe into OHLCV list."""
    if history.empty:
        return []

    rows: list[dict[str, Any]] = []
    for index, row in history.iterrows():
        timestamp = index.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp_ms = int(timestamp.timestamp() * 1000)
        rows.append(
            {
                "time": timestamp_ms,
                "open": float(row.get("Open", 0.0)),
                "high": float(row.get("High", 0.0)),
                "low": float(row.get("Low", 0.0)),
                "close": float(row.get("Close", 0.0)),
                "volume": int(row.get("Volume", 0)),
            }
        )
    return rows
