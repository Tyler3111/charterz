"""Unit tests for route-level cache flow."""

import unittest
from unittest.mock import AsyncMock, patch

from src.api.routes import get_stock
from src.core.config import Settings


class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    """Validate stock endpoint behavior."""

    async def test_get_stock_uses_cached_payload(self) -> None:
        """Stock endpoint should return cached data when available."""
        cached_payload = [
            {
                "time": 1704067200000,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000,
            }
        ]

        settings = Settings(database_url="postgresql+asyncpg://localhost/stock_dashboard")
        session = object()

        with patch("src.api.routes.CacheService") as cache_service_cls:
            service_instance = cache_service_cls.return_value
            service_instance.get_cached = AsyncMock(return_value=cached_payload)

            response = await get_stock(
                symbol="aapl",
                interval="1d",
                period="1mo",
                session=session,  # type: ignore[arg-type]
                settings=settings,
            )

            self.assertTrue(response.cached)
            self.assertEqual(response.symbol, "AAPL")
            self.assertEqual(len(response.data), 1)


if __name__ == "__main__":
    unittest.main()
