# Stock Dashboard Backend

FastAPI backend for serving cached OHLCV stock data to EquiCharts.

## Features
- Async FastAPI endpoints
- PostgreSQL-backed cache with 1-hour TTL (configurable)
- yfinance integration with retry logic
- OHLCV JSON payload for charting
- Docker + docker-compose setup

## API
- `GET /api/v1/health`
- `GET /api/v1/stock/{symbol}?interval=1d&period=1mo`
- `GET /api/v1/stats`

## Run locally
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --reload
```

## Run with Docker
```bash
cd backend
cp .env.example .env
docker compose up --build
```
