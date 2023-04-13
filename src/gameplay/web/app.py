import asyncio
from asyncio import Queue
import os
from pathlib import Path
from collections import defaultdict

import databases
import sentry_sdk
from fastapi import FastAPI, Request, Response, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks  # type: ignore
from sse_starlette.sse import EventSourceResponse
import asyncpg_listen

from . import schemas, service


class Listener:
    def __init__(self, database_url):
        self.database_url = database_url
        self.queues = defaultdict(dict)
        self.running = False

    def _start(self):
        if not self.running:
            # @note: listener makes its own connections to the database
            # and doesn't use the pool that route handlers use.
            self.listener = asyncpg_listen.NotificationListener(
                asyncpg_listen.connect_func(self.database_url)
            )
            self.listener_task = asyncio.create_task(
                self.listener.run(
                    {"test": self.handle_test},
                    policy=asyncpg_listen.ListenPolicy.ALL,
                )
            )
            self.running = True

    async def handle_test(self, notification: asyncpg_listen.NotificationOrTimeout):
        if isinstance(notification, asyncpg_listen.Notification):
            print(f"got notification: {notification.channel} {notification.payload}")
            for _, queue in self.queues[notification.payload].items():
                queue.put_nowait(notification.payload)
        elif isinstance(notification, asyncpg_listen.Timeout):
            print(f"got timeout: {notification.channel}")

    def listen(self, match_id: int):
        self._start()
        queue = Queue()
        self.queues[str(match_id)][id(queue)] = queue

        async def listener():
            try:
                while True:
                    item = await queue.get()
                    yield item
            except asyncio.CancelledError as e:
                if id(queue) in self.queues[match_id]:
                    del self.queues[match_id][id(queue)]
                raise e

        return listener


def build_app(database: databases.Database, listener: Listener) -> FastAPI:
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
        match = await service.create_match(database, new_match)

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
    @app.get("/matches/{match_id}/", response_class=HTMLResponse)
    async def get_match(request: Request, response: Response, match_id: int):
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.get_match(database, match_id)

        block_name = None
        if hx_request:
            block_name = "match_state"  # todo: dynamic
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
        background_tasks: BackgroundTasks,
        match_id: int,
        turn: schemas.TurnCreate = Depends(schemas.TurnCreate.as_form),
    ):
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.take_turn(database, match_id, turn)
        if match.next_player == 2:
            background_tasks.add_task(service.take_ai_turn, database, match_id)

        block_name = None
        if hx_request:
            block_name = "match_state"  # todo: dynamic
            # block_name = "main_content"
            response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html.j2",
            {"request": request, "match": match},
            block_name=block_name,
        )

    @app.get("/matches/{match_id}/changes/", response_class=EventSourceResponse)
    async def watch_match_changes(request: Request, match_id: int):
        fn = listener.listen(match_id)
        return EventSourceResponse(fn())

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

    listener = Listener(DATABASE_URL)

    _app = build_app(database, listener)

    return _app
