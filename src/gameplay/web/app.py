import asyncio
import os
from pathlib import Path

import databases
import sentry_sdk
from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks  # type: ignore
from sse_starlette.sse import EventSourceResponse

from . import schemas, service


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
    templates = Jinja2Blocks(directory=web_dir / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def get_root(request: Request):
        return templates.TemplateResponse("root.html.j2", {"request": request})

    # returns the match
    @app.post("/matches/", response_class=HTMLResponse)
    async def create_match(request: Request, response: Response):
        hx_request = request.headers.get("hx-request") == "true"

        new_match = schemas.MatchCreate(game="connect4", opponent="ai")
        match = await service.create_match(new_match)

        block_name = None
        if hx_request:
            block_name = "main_content"
            response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html.j2",
            {"request": request, "match": match},
            block_name=block_name,
        )

    # returns the match
    @app.get("/matches/{match_id}", response_class=HTMLResponse)
    async def get_match(request: Request, response: Response, match_id: int):
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.get_match(match_id)

        block_name = None
        if hx_request:
            block_name = "main_content"
            response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html.j2",
            {"request": request, "match": match},
            block_name=block_name,
        )

    # returns the match
    @app.post("/matches/{match_id}/turns/", response_class=HTMLResponse)
    async def create_turn(
        request: Request,
        response: Response,
        match_id: int,
        turn: schemas.TurnCreate = Depends(schemas.TurnCreate.as_form),
    ):
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.take_turn(match_id, turn)

        block_name = None
        if hx_request:
            block_name = "main_content"
            response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html.j2",
            {"request": request, "match": match},
            block_name=block_name,
        )

    @app.get("/matches/{match_id}/changes", response_class=EventSourceResponse)
    async def watch_match_changes(request: Request):
        pass

    @app.get("/sse", response_class=EventSourceResponse)
    async def sse(request: Request):
        async def event_publisher():
            i = 0
            try:
                while True:
                    i += 1
                    yield dict(data=i)
                    await asyncio.sleep(0.2)
            except asyncio.CancelledError as e:
                print(f"Disconnected from client (via refresh/close) {request.client}")
                # Do any other cleanup, if any
                # todo: I dunno that I really need to raise again...
                # we're just done, client is gone.
                raise e

        return EventSourceResponse(event_publisher())

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
