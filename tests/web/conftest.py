import os
import pytest

import databases
from httpx import AsyncClient

from gameplay.web.app import build_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# NOTE: Migrations are not run as part of the tests, assumes the test database
# exists and is up to date.
@pytest.fixture
async def _database(anyio_backend):
    TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
    assert TEST_DATABASE_URL is not None
    database = databases.Database(TEST_DATABASE_URL, force_rollback=True)
    yield database
    return


@pytest.fixture
async def database(anyio_backend, _database):
    await _database.connect()
    assert _database.is_connected
    yield _database
    await _database.disconnect()
    assert not _database.is_connected


@pytest.fixture
async def api(anyio_backend, _database):
    app = build_app(_database)
    async with AsyncClient(app=app, base_url="http://test") as api:
        yield api
    return