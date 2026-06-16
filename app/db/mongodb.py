from __future__ import annotations

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models import ALL_DOCUMENT_MODELS

_client: AsyncIOMotorClient | None = None


async def init_mongodb() -> None:
    """Connect to MongoDB and initialise Beanie document models."""
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    database = _client[settings.mongodb_db]
    await init_beanie(database=database, document_models=ALL_DOCUMENT_MODELS)


async def close_mongodb() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
