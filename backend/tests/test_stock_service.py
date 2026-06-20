"""Unit tests for stock service transformations."""

import unittest

import pandas as pd

from src.services.stock_service import StockValidationError, _transform_history, fetch_stock_data


class StockServiceTests(unittest.IsolatedAsyncioTestCase):
    """Validate stock service behavior."""

    def test_transform_history_returns_ohlcv(self) -> None:
        """Transform should map dataframe rows into OHLCV dicts."""
        index = pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True)
        frame = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [110.0, 111.0],
                "Low": [90.0, 91.0],
                "Close": [105.0, 106.0],
                "Volume": [1000, 2000],
            },
            index=index,
        )

        payload = _transform_history(frame)

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["open"], 100.0)
        self.assertEqual(payload[0]["high"], 110.0)
        self.assertEqual(payload[0]["low"], 90.0)
        self.assertEqual(payload[0]["close"], 105.0)
        self.assertEqual(payload[0]["volume"], 1000)
        self.assertIn("time", payload[0])

    def test_transform_history_empty_returns_empty(self) -> None:
        """Transform should return empty payload for empty dataframe."""
        payload = _transform_history(pd.DataFrame())
        self.assertEqual(payload, [])

    async def test_invalid_interval_raises_validation_error(self) -> None:
        """Fetcher should reject unsupported intervals."""
        with self.assertRaises(StockValidationError):
            await fetch_stock_data("AAPL", interval="2h", period="1mo")


if __name__ == "__main__":
    unittest.main()
