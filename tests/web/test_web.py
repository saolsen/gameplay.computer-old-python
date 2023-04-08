async def test_database(anyio_backend, database):
    result = await database.fetch_val(query="SELECT 1")
    assert result == 1


async def test_api(anyio_backend, api):
    response = await api.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
