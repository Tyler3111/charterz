"""API request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class StockDataPoint(BaseModel):
    """Single OHLCV datapoint for chart rendering."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockResponse(BaseModel):
    """Stock response payload for frontend consumption."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    interval: str
    period: str
    cached: bool = Field(default=False)
    data: list[StockDataPoint]


class ErrorResponse(BaseModel):
    """Error payload schema."""

    detail: str
