import os
from typing import AsyncIterator, Callable, Iterator
from unittest import mock

import databases
import pytest
from httpx import AsyncClient

from gameplay_computer.users.repo import ClerkEmailAddress, ClerkUser
from gameplay_computer.web.app import Auth, Listener, build_app


@pytest.fixture(autouse=True)
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def mock_users() -> Iterator[list[ClerkUser]]:
    """
    Mocks the users repo so we don't call the Clerk API during tests.
    """
    with mock.patch(
        "gameplay_computer.users.repo._list_clerk_users"
    ) as mock_list_clerk_users:
        _mock_users: list[ClerkUser] = []
        mock_list_clerk_users.return_value = _mock_users
        yield _mock_users


@pytest.fixture
def mock_user(mock_users: list[ClerkUser]) -> Callable[[ClerkUser], str]:
    def _mock_user(user: ClerkUser) -> str:
        mock_users.append(user)
        return user.id

    return _mock_user


@pytest.fixture
def user_steve(mock_user: Callable[[ClerkUser], str]) -> str:
    steve = ClerkUser(
        id="u_steve",
        username="steve",
        first_name="Steve",
        last_name="Olsen",
        profile_image_url="https://example.com/steve.jpg",
        email_addresses=[
            ClerkEmailAddress(id="email_1", email_address="steve@steve.computer")
        ],
        primary_email_address_id="email_1",
    )
    return mock_user(steve)


@pytest.fixture
def database_url() -> str:
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    assert test_database_url is not None
    return test_database_url


# NOTE: Migrations are not run as part of the tests, assumes the test database
# exists and is up-to-date.
@pytest.fixture
async def database(database_url: str) -> AsyncIterator[databases.Database]:
    database = databases.Database(database_url, force_rollback=True)
    await database.connect()
    assert database.is_connected
    yield database
    await database.disconnect()
    assert not database.is_connected
    return


@pytest.fixture
def listener(database_url: str) -> Listener:
    listener = Listener(database_url)
    return listener


@pytest.fixture
async def api(
    database: databases.Database, listener: Listener
) -> AsyncIterator[AsyncClient]:
    auth = Auth(None)

    app = build_app(database, listener, auth)
    async with AsyncClient(app=app, base_url="http://test") as api:
        yield api
    return