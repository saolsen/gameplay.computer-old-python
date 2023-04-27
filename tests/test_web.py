import databases
from httpx import AsyncClient


async def test_database(anyio_backend: str, database: databases.Database) -> None:
    result = await database.fetch_val(query="SELECT 1")
    assert result == 1


async def test_api(api: AsyncClient, user_steve: str) -> None:
    response = await api.get("/")
    assert 200 == response.status_code
    assert response.headers["content-type"] == "text/html; charset=utf-8"

    response = await api.get("/", headers={"Authorization": user_steve})
    assert 200 == response.status_code
