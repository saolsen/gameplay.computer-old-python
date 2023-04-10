import asyncio
import os
from pathlib import Path
from typing import Union

import databases
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks  # type: ignore
from sse_starlette.sse import EventSourceResponse

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
    templates = Jinja2Blocks(directory=web_dir / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request):
        return templates.TemplateResponse(
            "root.html", {"request": request, "hello": "world"}
        )

    @app.get("/items/{item_id}")
    def read_item(item_id: int, q: Union[str, None] = None):
        return {"item_id": item_id, "q": q}

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

    @app.get("/foo", response_class=HTMLResponse)
    async def foo_html(request: Request):
        return "<html><body>foo</body></html>"

    from pydantic import BaseModel

    class Foo(BaseModel):
        foo: str

    @app.get("/foo", response_model=Foo)
    async def foo_json(request: Request):
        return Foo(foo="foo")

    # I am not quite ready to do the real app, I wanna try one 1 thing to make sure
    # I can do htmx right first.

    # gameplay
    # games
    #  - connect4
    # games is a list of games,
    # connect 4 shows connect 4 stuff.
    # matches
    # - post to create a new match
    # matches/matchid
    # - overview of the match data
    # matches/matchid/turns
    # - list of turns
    # - post to it to create a new turn aka take your turn.
    # that's a good start I think.

    # one things we could do is sort of like /api/blah vs just /blah
    # the stuff under api would be the routes that just talk json.

    @app.get("/games/connect4", response_class=HTMLResponse)
    async def get_connect4_html(request: Request):
        return templates.TemplateResponse("connect4.html.j2", {"request": request})

    """ @app.get("/games/connect4/matches", response_class=HTMLResponse)
    async def list_connect4_matches(request: Request):
        return templates.TemplateResponse("connect4.html.j2", {"request": request}) """

    @app.post("/games/connect4/matches", response_class=HTMLResponse)
    async def create_connect4_match(request: Request):
        return templates.TemplateResponse("connect4.html.j2", {"request": request})

    @app.get("/games/connect4/matches/{match_id}", response_class=HTMLResponse)
    async def get_connect4_match(request: Request):
        match = schemas.Match(
            game="connect4",
            opponent="ai",
            id=1,
            state="playing",
            turn=1,
            next_player=1,
            turns=[schemas.Turn(player=1, column=2, id=1, number=1, match_id=1)],
        )
        return templates.TemplateResponse(
            "connect4_match.html.j2", {"request": request, "match": match}
        )

    @app.get("/games/connect4/matches/{match_id}/turns", response_class=HTMLResponse)
    async def get_connect4_match_turns(request: Request):
        return templates.TemplateResponse("connect4.html.j2", {"request": request})

    # wow, this really works great.
    @app.post("/games/connect4/matches/{match_id}/turns", response_class=HTMLResponse)
    async def create_connect4_match_turn(request: Request):
        match = schemas.Match(
            game="connect4",
            opponent="ai",
            id=1,
            state="playing",
            turn=1,
            next_player=1,
            turns=[
                schemas.Turn(player=1, column=2, id=1, number=1, match_id=1),
                schemas.Turn(player=2, column=4, id=2, number=2, match_id=1),
            ],
        )
        return templates.TemplateResponse(
            "connect4_match.html.j2",
            {"request": request, "match": match},
            block_name="turns",
        )

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
