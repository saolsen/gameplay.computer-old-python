async def test_database(anyio_backend, database):
    result = await database.fetch_val(query="SELECT 1")
    assert result == 1


async def test_api(anyio_backend, api):
    response = await api.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


async def test_widgets(anyio_backend, api):
    response = await api.get("/widgets/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == []

    response = await api.post("/widgets/", json={"name": "one", "is_active": True})
    assert response.status_code == 200
    response = await api.post("/widgets/", json={"name": "two", "is_active": False})
    assert response.status_code == 200

    response = await api.get("/widgets/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    json = response.json()
    assert len(json) == 2
    assert json[0]["name"] == "one"
    assert json[0]["is_active"] is True
    assert json[1]["name"] == "two"
    assert json[1]["is_active"] is False
