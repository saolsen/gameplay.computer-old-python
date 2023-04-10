import os
from pathlib import Path
from typing import Union

import databases
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sentry_sdk

from . import schemas, tables


def build_app(database: databases.Database) -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        await database.connect()

    @app.on_event("shutdown")
    async def shutdown():
        await database.disconnect()

    web_dir = Path(__file__).parent

    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    templates = Jinja2Templates(directory=web_dir / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request):
        return templates.TemplateResponse(
            "root.html", {"request": request, "hello": "world"}
        )

    @app.get("/items/{item_id}")
    def read_item(item_id: int, q: Union[str, None] = None):
        return {"item_id": item_id, "q": q}

    @app.get("/connect4", response_class=HTMLResponse)
    async def get_connect4(request: Request):
        return templates.TemplateResponse("connect4.html.j2", {"request": request})

    @app.get("/widgets/", response_model=list[schemas.Widget])
    async def read_widgets():
        # todo: put this kind of stuff in service so we can test it without web requests
        get_all = tables.widgets.select()
        return await database.fetch_all(query=get_all)

    @app.post("/widgets/", response_model=schemas.Widget)
    async def create_note(widget: schemas.WidgetCreate):
        query = tables.widgets.insert().values(
            name=widget.name, is_active=widget.is_active
        )
        last_record_id = await database.execute(query)
        return {**widget.dict(), "id": last_record_id}

    @app.get("/sentry-debug")
    async def trigger_error():
        _division_by_zero = 1 / 0

    return app


def app() -> FastAPI:
    DATABASE_URL = os.environ.get("DATABASE_URL")
    assert DATABASE_URL is not None

    database = databases.Database(DATABASE_URL)

    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT")

    if SENTRY_DSN is not None and SENTRY_ENVIRONMENT is not None:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production,
            traces_sample_rate=1.0,
        )

    _app = build_app(database)

    return _app
