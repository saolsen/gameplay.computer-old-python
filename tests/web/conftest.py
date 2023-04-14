import os

import databases
import pytest
from httpx import AsyncClient

from gameplay.web.app import Listener, build_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database_url():
    TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
    assert TEST_DATABASE_URL is not None
    return TEST_DATABASE_URL


# NOTE: Migrations are not run as part of the tests, assumes the test database
# exists and is up to date.
@pytest.fixture
async def database(anyio_backend, database_url):
    database = databases.Database(database_url, force_rollback=True)
    await database.connect()
    assert database.is_connected
    yield database
    await database.disconnect()
    assert not database.is_connected
    return


@pytest.fixture
async def listener(anyio_backend, database_url):
    listener = Listener(database_url)
    return listener


@pytest.fixture
async def api(anyio_backend, database, listener):
    app = build_app(database, listener)
    async with AsyncClient(app=app, base_url="http://test") as api:
        yield api
    return
