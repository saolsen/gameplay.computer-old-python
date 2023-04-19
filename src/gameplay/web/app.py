import asyncio
import os
import json
from asyncio import Queue
from collections import defaultdict
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import asyncpg_listen
import databases
import sentry_sdk
from fastapi import BackgroundTasks, Depends, FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks  # type: ignore
from sse_starlette.sse import EventSourceResponse
from jwcrypto import jwt, jwk

from . import schemas, service


class Listener:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.queues: dict[int, dict[int, Queue[str]]] = defaultdict(dict)
        self.running = False

    def _start(self) -> None:
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

    async def handle_test(
        self, notification: asyncpg_listen.NotificationOrTimeout
    ) -> None:
        if isinstance(notification, asyncpg_listen.Notification):
            print(f"got notification: {notification.channel} {notification.payload}")
            if notification.payload is not None:
                match_id = int(notification.payload)
                for _, queue in self.queues[match_id].items():
                    queue.put_nowait(notification.payload)
        elif isinstance(notification, asyncpg_listen.Timeout):
            pass
            # print(f"got timeout: {notification.channel}")

    def listen(self, match_id: int) -> Callable[[], AsyncIterator[str]]:
        self._start()
        queue: Queue[str] = Queue()
        self.queues[match_id][id(queue)] = queue

        async def listener() -> AsyncIterator[str]:
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
    clerk_publishable_key = os.environ.get("CLERK_PUBLISHABLE_KEY")
    assert clerk_publishable_key is not None

    clerk_jwt_public_key = os.environ.get("CLERK_JWT_PUBLIC_KEY")
    assert clerk_jwt_public_key is not None
    pem = bytes(clerk_jwt_public_key, "utf-8")
    key = jwk.JWK.from_pem(data=pem)

    def get_user(request: Request) -> str | None:
        session = request.cookies.get("__session")
        user_id = None
        if session:
            token = jwt.JWT(key=key, jwt=session, expected_type="JWS")
            token.validate(key=key)
            claims = json.loads(token.claims)
            user_id = claims["sub"]
            print(user_id)
        return user_id
        """ token = req.headers["Authorization"]
        # Here your code for verifying the token or whatever you use
        if token is not valid:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return True """

    app = FastAPI()

    @app.on_event("startup")
    async def startup() -> None:
        await database.connect()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await database.disconnect()

    web_dir = Path(__file__).parent

    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    templates = Jinja2Blocks(directory=web_dir / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def get_root(
        request: Request, user_id: str | None = Depends(get_user)
    ) -> Any:
        # print(request.cookies)
        # session = request.cookies.get("__session")
        # user_id = None
        # if session:
        #     token = jwt.JWT(key=key, jwt=session, expected_type="JWS")
        #     token.validate(key=key)
        #     claims = json.loads(token.claims)
        #     user_id = claims["sub"]
        #     print(user_id)

        return templates.TemplateResponse(
            "root.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "user_id": user_id,
            },
        )

    @app.get("/test", response_class=HTMLResponse)
    async def get_test(request: Request) -> Any:
        print(request.cookies)

        return templates.TemplateResponse(
            "test.html",
            {"request": request, "clerk_publishable_key": clerk_publishable_key},
        )

    # returns the match
    @app.post("/matches/", response_class=HTMLResponse)
    async def create_match(request: Request, response: Response) -> Any:
        hx_request = request.headers.get("hx-request") == "true"

        new_match = schemas.MatchCreate(game="connect4", opponent="ai")
        match = await service.create_match(database, new_match)

        block_name = None
        if hx_request:
            block_name = "main_content"
            response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html",
            {"request": request, "match": match},
            block_name=block_name,
        )

    # returns the match
    @app.get("/matches/{match_id}/", response_class=HTMLResponse)
    async def get_match(request: Request, _response: Response, match_id: int) -> Any:
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.get_match(database, match_id)

        block_name = None
        if hx_request:
            block_name = "match_state"  # todo: dynamic
            # response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html",
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
    ) -> Any:
        hx_request = request.headers.get("hx-request") == "true"

        match = await service.take_turn(database, match_id, turn)
        if match.next_player == 2:
            background_tasks.add_task(service.take_ai_turn, database, match_id)

        block_name = None
        if hx_request:
            block_name = "match_state"  # todo: dynamic
            # block_name = "main_content"
            # response.headers["HX-PUSH-URL"] = f"/matches/{match.id}/"

        return templates.TemplateResponse(
            "connect4_match.html",
            {"request": request, "match": match},
            block_name=block_name,
        )

    @app.get("/matches/{match_id}/changes/", response_class=EventSourceResponse)
    async def watch_match_changes(request: Request, match_id: int) -> Any:
        fn = listener.listen(match_id)
        return EventSourceResponse(fn())

    return app


def app() -> FastAPI:
    database_url = os.environ.get("DATABASE_URL")
    assert database_url is not None

    database = databases.Database(database_url)

    sentry_dsn = os.environ.get("SENTRY_DSN")
    sentry_environment = os.environ.get("SENTRY_ENVIRONMENT")

    if sentry_dsn is not None and sentry_environment is not None:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=sentry_environment,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production,
            traces_sample_rate=1.0,
        )

    listener = Listener(database_url)

    _app = build_app(database, listener)

    return _app
