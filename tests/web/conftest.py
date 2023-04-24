import os
from typing import AsyncIterator

import databases
import pytest
from httpx import AsyncClient

from gameplay.web.app import Listener, build_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def database_url() -> str:
    TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
    assert TEST_DATABASE_URL is not None
    return TEST_DATABASE_URL


# NOTE: Migrations are not run as part of the tests, assumes the test database
# exists and is up-to-date.
@pytest.fixture
async def database(
    anyio_backend: str, database_url: str
) -> AsyncIterator[databases.Database]:
    database = databases.Database(database_url, force_rollback=True)
    await database.connect()
    assert database.is_connected
    yield database
    await database.disconnect()
    assert not database.is_connected
    return


@pytest.fixture
def listener(anyio_backend: str, database_url: str) -> Listener:
    listener = Listener(database_url)
    return listener


@pytest.fixture
async def api(
    anyio_backend: str, database: databases.Database, listener: Listener
) -> AsyncIterator[AsyncClient]:
    app = build_app(database, listener)
    async with AsyncClient(app=app, base_url="http://test") as api:
        yield api
    return
