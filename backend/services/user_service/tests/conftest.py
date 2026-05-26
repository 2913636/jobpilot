"""Test fixtures for user-service.

Requires a running PostgreSQL instance.  Set TEST_DATABASE_URL to override.

Run with:
    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/testdb pytest tests/ -v
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.db import Base, get_db

TEST_DB_URL = "postgresql+asyncpg://jobpilot:jobpilot_secret@localhost:5432/jobpilot_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    url = os.getenv("TEST_DATABASE_URL", TEST_DB_URL)
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """httpx AsyncClient wired to the FastAPI app with a test DB session."""
    from services.user_service import main as app_module

    app = app_module.app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
