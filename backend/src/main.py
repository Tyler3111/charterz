"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.config import get_settings
from src.core.database import engine
from src.core.models import Base
from src.utils.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and dispose app resources."""
    configure_logging(settings.debug)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Stock Dashboard Backend", debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_v1_prefix)
