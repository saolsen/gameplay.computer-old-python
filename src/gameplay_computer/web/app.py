import asyncio
import json
import os
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
from jwcrypto import jwk, jwt  # type: ignore
from sse_starlette.sse import EventSourceResponse

from gameplay_computer.common import schemas as cs
from gameplay_computer.web import schemas, service


class Auth:
    def __init__(self, key: jwk.JWK | None):
        self.key = key

    def __call__(self, request: Request) -> str | None:
        if self.key:
            session = request.cookies.get("__session")
            user_id = None
            if session:
                try:
                    token = jwt.JWT(key=self.key, jwt=session, expected_type="JWS")
                    token.validate(key=self.key)
                    claims = json.loads(token.claims)
                    user_id = claims["sub"]
                except Exception as e:
                    print(e)
                    # todo: redirect/refresh somehow when the token
                    # is expired so we can get a new one and still show the requested
                    # page instead of loading a not logged in page.
                    # prolly 2 handlers one that redirects and one that doesn't
                    pass
            return user_id
        else:
            # Test mode, make this a real token when you expose an api!
            return request.headers.get("Authorization")


async def run_ai_turns(database: databases.Database, match_id: int) -> None:
    while True:
        async with database.transaction():
            match = await service.get_match(database, match_id)

            if (
                match is not None
                and match.state.next_player is not None
                and isinstance(match.players[match.state.next_player], cs.Agent)
            ):
                await service.take_ai_turn(database, match_id)
            else:
                break


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


def build_app(
    database: databases.Database,
    listener: Listener,
    auth: Auth,
    clerk_publishable_key: str | None = None,
) -> FastAPI:
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

    @app.get("/health", response_class=HTMLResponse)
    async def check_health(request: Request) -> Any:
        assert database.is_connected

        return templates.TemplateResponse(
            "root.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "user_id": None,
            },
        )

    @app.get("/test", response_class=HTMLResponse)
    async def get_test(request: Request) -> Any:
        block_name = request.headers.get("hx-target")
        print(request.cookies)

        return templates.TemplateResponse(
            "test.html",
            {"request": request, "clerk_publishable_key": clerk_publishable_key},
            block_name=block_name,
        )

    @app.get("/selects", response_class=HTMLResponse)
    async def get_selects(
        request: Request,
        user_id: str | None = Depends(auth),
    ) -> Any:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None
        username = user.username

        if "player_type_1" in request.query_params:
            player_type = request.query_params["player_type_1"]
            n = 1
            player = "blue"
        elif "player_type_2" in request.query_params:
            player_type = request.query_params["player_type_2"]
            n = 2
            player = "red"
        else:
            return None

        match player_type:
            case "me":
                return (
                    f'<input name="player_name_{n}" type="hidden" value="{username}">'
                )
            case "user":
                users = await service.get_clerk_users()
                options = [
                    f'<option value="{user.username}">{user.username}</option>'
                    for user in users
                    if user.username != username
                ]

                return f"""
                <label for="{player}_player">username</label>
                <select name="player_name_{n}" id="{player}_player">
                {"".join(options)}
                </select>
                """
            case "agent":
                agents = ["steve/random"]
                options = [
                    f'<option value="{agent}">{agent}</option>' for agent in agents
                ]
                return f"""
                <label for="{player}_player">agentname</label>
                <select name="player_name_{n}" id="{player}_player">
                {"".join(options)}
                </select>
                """
            case _:
                return None

    @app.get("/", response_class=HTMLResponse)
    async def get_root(request: Request, user_id: str | None = Depends(auth)) -> Any:
        block_name = request.headers.get("hx-target")

        if user_id is not None:
            assert user_id is not None
            user = await service.get_clerk_user_by_id(user_id)
            assert user is not None
            username = user.username

            matches = await service.get_matches(database, user_id)

            return templates.TemplateResponse(
                "home.html",
                {
                    "request": request,
                    "clerk_publishable_key": clerk_publishable_key,
                    "user_id": user_id,
                    "username": username,
                    "matches": matches,
                },
                block_name=block_name,
            )
        else:
            return templates.TemplateResponse(
                "root.html",
                {
                    "request": request,
                    "clerk_publishable_key": clerk_publishable_key,
                    "user_id": user_id,
                },
                block_name=block_name,
            )

    @app.get("/games", response_class=HTMLResponse)
    async def get_games(request: Request, user_id: str | None = Depends(auth)) -> Any:
        block_name = request.headers.get("hx-target")

        return templates.TemplateResponse(
            "games.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "user_id": user_id,
            },
            block_name=block_name,
        )

    @app.get("/users", response_class=HTMLResponse)
    async def get_users(request: Request, user_id: str | None = Depends(auth)) -> Any:
        block_name = request.headers.get("hx-target")

        return templates.TemplateResponse(
            "users.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "user_id": user_id,
            },
            block_name=block_name,
        )

    @app.get("/agents", response_class=HTMLResponse)
    async def get_agents(request: Request, user_id: str | None = Depends(auth)) -> Any:
        block_name = request.headers.get("hx-target")

        return templates.TemplateResponse(
            "agents.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "user_id": user_id,
            },
            block_name=block_name,
        )

    @app.post("/matches", response_class=HTMLResponse)
    async def create_match(
        background_tasks: BackgroundTasks,
        request: Request,
        response: Response,
        user_id: str | None = Depends(auth),
        new_match: schemas.MatchCreate = Depends(schemas.MatchCreate.as_form),
    ) -> Any:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None
        username = user.username
        block_name = request.headers.get("hx-target")

        match_id = await service.create_match(user_id, database, new_match)
        match = await service.get_match(database, match_id)

        background_tasks.add_task(run_ai_turns, database, match_id)

        response.headers["HX-PUSH-URL"] = f"/matches/{match_id}/"

        return templates.TemplateResponse(
            "connect4_match.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "match": match,
                "match_id": match_id,
                "username": username,
            },
            block_name=block_name,
        )

    # returns the match
    @app.get("/matches/{match_id}", response_class=HTMLResponse)
    async def get_match(
        request: Request,
        _response: Response,
        match_id: int,
        user_id: str | None = Depends(auth),
    ) -> Any:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None
        username = user.username
        block_name = request.headers.get("hx-target")

        match = await service.get_match(database, match_id)

        return templates.TemplateResponse(
            "connect4_match.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "match": match,
                "match_id": match_id,
                "username": username,
            },
            block_name=block_name,
        )

    # returns the match
    @app.post("/matches/{match_id}/turns", response_class=HTMLResponse)
    async def create_turn(
        background_tasks: BackgroundTasks,
        request: Request,
        response: Response,
        match_id: int,
        turn: schemas.TurnCreate = Depends(schemas.TurnCreate.as_form),
        user_id: str | None = Depends(auth),
    ) -> Any:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None
        username = user.username
        block_name = request.headers.get("hx-target")

        match = await service.take_turn(database, match_id, turn, user_id=user_id)
        background_tasks.add_task(run_ai_turns, database, match_id)

        return templates.TemplateResponse(
            "connect4_match.html",
            {
                "request": request,
                "clerk_publishable_key": clerk_publishable_key,
                "match": match,
                "match_id": match_id,
                "username": username,
            },
            block_name=block_name,
        )

    @app.get("/matches/{match_id}/changes", response_class=EventSourceResponse)
    async def watch_match_changes(request: Request, match_id: int) -> Any:
        fn = listener.listen(match_id)
        return EventSourceResponse(fn())

    from gameplay_computer.matches.schemas import Match

    @app.post("/api/v1/matches")
    async def api_create_match(
            background_tasks: BackgroundTasks,
            request: Request,
            response: Response,
            new_match: schemas.MatchCreate,
            user_id: str | None = Depends(auth),
    ) -> Match | None:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None

        match_id = await service.create_match(user_id, database, new_match)
        match = await service.get_match(database, match_id)

        background_tasks.add_task(run_ai_turns, database, match_id)

        return match


    @app.get("/api/v1/matches/{match_id}")
    async def api_get_match(
            request: Request,
            _response: Response,
            match_id: int,
            user_id: str | None = Depends(auth),
    ) -> Match | None:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None

        match = await service.get_match(database, match_id)

        return match

    # returns the match
    @app.post("/api/v1/matches/{match_id}/turns")
    async def api_create_turn(
            background_tasks: BackgroundTasks,
            request: Request,
            response: Response,
            match_id: int,
            turn: schemas.TurnCreate,
            user_id: str | None = Depends(auth),
    ) -> Match | None:
        assert user_id is not None
        user = await service.get_clerk_user_by_id(user_id)
        assert user is not None

        match = await service.take_turn(database, match_id, turn, user_id=user_id)
        background_tasks.add_task(run_ai_turns, database, match_id)

        return match

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

    clerk_publishable_key = os.environ.get("CLERK_PUBLISHABLE_KEY")
    clerk_jwt_public_key = os.environ.get("CLERK_JWT_PUBLIC_KEY")
    key = None
    if clerk_jwt_public_key is not None:
        pem = bytes(clerk_jwt_public_key, "utf-8")
        key = jwk.JWK.from_pem(data=pem)
    auth = Auth(key)

    _app = build_app(
        database, listener, auth, clerk_publishable_key=clerk_publishable_key
    )

    return _app
