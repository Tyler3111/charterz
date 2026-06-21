"""Stock data fetching service with Alpha Vantage and yfinance fallback."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp
import pandas as pd
import yfinance as yf
from src.core.config import get_settings  # <-- Import settings


logger = logging.getLogger(__name__)

VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}

# Get your free API key from https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY_HERE"  # <-- PUT YOUR KEY HERE


class StockNotFoundError(Exception):
    """Raised when a symbol has no retrievable history."""


class StockFetchError(Exception):
    """Raised when stock history cannot be fetched due to upstream issues."""


class StockValidationError(Exception):
    """Raised when request parameters are invalid."""


async def fetch_stock_data(symbol: str, interval: str, period: str) -> list[dict[str, Any]]:
    """Fetch stock data with Alpha Vantage as primary, yfinance as fallback."""
    ticker_symbol = symbol.upper()
    if interval not in VALID_INTERVALS:
        raise StockValidationError(f"Unsupported interval '{interval}'.")

    # Get settings to access API key
    settings = get_settings()
    
    # Try Alpha Vantage first (more reliable)
    if settings.alpha_vantage_api_key:
        try:
            logger.info("Attempting Alpha Vantage", extra={"symbol": ticker_symbol})
            data = await fetch_from_alpha_vantage(
                ticker_symbol, 
                interval, 
                period, 
                settings.alpha_vantage_api_key  # <-- Pass the key
            )
            if data:
                return data
        except Exception as e:
            logger.warning(f"Alpha Vantage failed: {e}, trying yfinance")
    else:
        logger.warning("Alpha Vantage API key not configured, skipping")

    # Fallback to yfinance
    try:
        logger.info("Attempting yfinance fallback", extra={"symbol": ticker_symbol})
        history = await asyncio.to_thread(_fetch_yfinance_history, ticker_symbol, interval, period)
        data = _transform_yfinance_data(history)
        if data:
            return data
    except Exception as e:
        logger.warning(f"yfinance fallback failed: {e}")

    raise StockNotFoundError(f"No data found for symbol '{ticker_symbol}'.")


async def fetch_from_alpha_vantage(
    symbol: str, 
    interval: str, 
    period: str, 
    api_key: str  # <-- Receive API key as parameter
) -> list[dict[str, Any]]:
    """Fetch stock data from Alpha Vantage API."""
    if not api_key:
        raise StockFetchError("Alpha Vantage API key not configured")

    # Map interval to Alpha Vantage format
    av_interval_map = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "60min",
        "1d": "daily",
        "1wk": "weekly",
        "1mo": "monthly"
    }
    
    av_interval = av_interval_map.get(interval, "daily")
    
    # Determine which function to use
    if interval in ["1m", "5m", "15m", "30m", "1h"]:
        function = "TIME_SERIES_INTRADAY"
        params = {
            "function": function,
            "symbol": symbol,
            "interval": av_interval,
            "apikey": api_key,  # <-- Use the passed key
            "outputsize": "compact"
        }
        time_series_key = f"Time Series ({av_interval})"
    else:
        function = "TIME_SERIES_DAILY"
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": api_key,  # <-- Use the passed key
            "outputsize": "compact"
        }
        time_series_key = "Time Series (Daily)"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Respect Alpha Vantage's rate limit (5 calls/min for free tier)
            await asyncio.sleep(0.5)
            
            async with session.get("https://www.alphavantage.co/query", params=params) as response:
                if response.status != 200:
                    raise StockFetchError(f"Alpha Vantage returned {response.status}")
                
                data = await response.json()
                
                # Check for errors
                if "Error Message" in data:
                    raise StockFetchError(f"Alpha Vantage error: {data['Error Message']}")
                
                if "Note" in data:
                    raise StockFetchError(f"Alpha Vantage rate limit: {data['Note']}")
                
                if time_series_key not in data:
                    raise StockNotFoundError(f"No data found for {symbol}")
                
                # Transform to OHLCV format
                result = []
                time_series = data[time_series_key]
                
                # Sort by date (oldest to newest)
                sorted_dates = sorted(time_series.keys())
                
                for date_str in sorted_dates:
                    # Parse date
                    try:
                        dt = datetime.fromisoformat(date_str)
                    except ValueError:
                        # Handle different date formats
                        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    
                    timestamp_ms = int(dt.timestamp() * 1000)
                    values = time_series[date_str]
                    
                    result.append({
                        "time": timestamp_ms,
                        "open": float(values.get("1. open", 0)),
                        "high": float(values.get("2. high", 0)),
                        "low": float(values.get("3. low", 0)),
                        "close": float(values.get("4. close", 0)),
                        "volume": int(values.get("5. volume", 0)),
                    })
                
                if not result:
                    raise StockNotFoundError(f"No data found for {symbol}")
                
                logger.info(f"Alpha Vantage: {len(result)} rows for {symbol}")
                return result
                
    except aiohttp.ClientError as e:
        raise StockFetchError(f"Alpha Vantage connection error: {e}")
    except StockNotFoundError:
        raise
    except Exception as e:
        raise StockFetchError(f"Alpha Vantage error: {e}")


def _fetch_yfinance_history(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """Fetch raw historical dataframe from yfinance."""
    ticker = yf.Ticker(symbol)
    return ticker.history(interval=interval, period=period, auto_adjust=False)


def _transform_yfinance_data(history: pd.DataFrame) -> list[dict[str, Any]]:
    """Transform yfinance dataframe into OHLCV list."""
    if history.empty:
        return []

    rows: list[dict[str, Any]] = []
    for row in history.itertuples(index=True):
        timestamp = row.Index.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp_ms = int(timestamp.timestamp() * 1000)
        rows.append(
            {
                "time": timestamp_ms,
                "open": float(getattr(row, "Open", 0.0)),
                "high": float(getattr(row, "High", 0.0)),
                "low": float(getattr(row, "Low", 0.0)),
                "close": float(getattr(row, "Close", 0.0)),
                "volume": int(getattr(row, "Volume", 0)),
            }
        )
    return rows