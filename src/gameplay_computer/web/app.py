import json
import os
from pathlib import Path
from typing import Any

import databases
import sentry_sdk
from fastapi import Depends, FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2_fragments.fastapi import Jinja2Blocks  # type: ignore
from sse_starlette.sse import EventSourceResponse

from . import service, tasks
from .auth import AuthUser, auth
from .listener import Listener
from .schemas import AgentCreate, MatchCreate, TurnCreate
from .tasks import app as papp
from .tracing import setup_tracing

database_url = os.environ.get("DATABASE_URL")
if database_url is None:
    database_url = os.environ.get("TEST_DATABASE_URL")
assert database_url is not None
database = databases.Database(database_url)

clerk_publishable_key = os.environ.get("CLERK_PUBLISHABLE_KEY")

listener = Listener(database_url)

app = FastAPI()

web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
templates = Jinja2Blocks(directory=web_dir / "templates")


def view(
    request: Request,
    template: str,
    block_name: str | None = None,
    **kwargs: Any,
) -> Any:
    if block_name is None:
        block_name = request.headers.get("hx-target")

    kwargs["request"] = request
    kwargs["clerk_publishable_key"] = clerk_publishable_key
    return templates.TemplateResponse(
        template,
        kwargs,
        block_name=block_name,
    )


@app.get("/health", response_class=HTMLResponse)
async def check_health(request: Request) -> Any:
    return Response(status_code=200)


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request) -> Any:
    return view(request, "index.html")


@app.get("/app", response_class=HTMLResponse)
async def get_app(request: Request, user: AuthUser = Depends(auth)) -> Any:
    matches = await service.get_matches(database, user.user_id)
    agents = await service.get_agents(database)
    return view(request, "app.html", user=user, matches=matches, agents=agents)


@app.post("/app/matches/create_match", response_class=HTMLResponse)
async def create_match(
    request: Request,
    response: Response,
    user: AuthUser = Depends(auth),
    new_match: MatchCreate = Depends(MatchCreate.as_form),
) -> Any:
    match_id = await service.create_match(database, user.user_id, new_match)

    traceparent = sentry_sdk.Hub.current.scope.transaction.to_traceparent()
    await tasks.run_ai_turns.defer_async(traceparent=traceparent, match_id=match_id)

    # todo: If there is any error, I return the form again with the error message filled
    # in like this, the form just posts and replaces itself

    location = json.dumps({"path": f"/app/matches/{match_id}", "target": "#main"})
    response.headers["hx-location"] = location

    return view(
        request,
        "app.html",
        block_name="create_match",
        user=user,
        # todo: errors
    )


@app.get("/app/matches/create_match/selects", response_class=HTMLResponse)
async def get_create_match_selects(
    request: Request, user: AuthUser = Depends(auth)
) -> Any:
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
                f'<input name="player_name_{n}" type="hidden" value="{user.username}">'
            )
        case "user":
            users = await service.get_users()
            options = [
                f'<option value="{u.username}">{u.username}</option>'
                for u in users
                if u.username != user.username
            ]

            return f"""
                    <label for="{player}_player">username</label>
                    <select name="player_name_{n}" id="{player}_player">
                    {"".join(options)}
                    </select>
                    """
        case "agent":
            agents = await service.get_agents(database)
            options = [
                f'<option value="{agent.username}/{agent.agentname}">'
                + f"{agent.username}/{agent.agentname}</option>"
                for agent in agents
            ]
            return f"""
                    <label for="{player}_player">agentname</label>
                    <select name="player_name_{n}" id="{player}_player">
                    {"".join(options)}
                    </select>
                    """
        case _:
            return None


@app.get("/app/matches/{match_id}", response_class=HTMLResponse)
async def get_match(
    request: Request, match_id: int, user: AuthUser = Depends(auth)
) -> Any:
    match = await service.get_match(database, match_id)
    return view(request, "connect4_match.html", user=user, match=match)


@app.get("/app/matches/{match_id}/changes", response_class=EventSourceResponse)
async def watch_match_changes(
    request: Request, match_id: int, user: AuthUser = Depends(auth)
) -> Any:
    pass
    fn = listener.listen(match_id)
    return EventSourceResponse(fn())


@app.post("/app/matches/{match_id}/turns/create_turn", response_class=HTMLResponse)
async def create_turn(
    request: Request,
    match_id: int,
    user: AuthUser = Depends(auth),
    new_turn: TurnCreate = Depends(TurnCreate.as_form),
) -> Any:
    await service.take_turn(database, match_id, new_turn, user.user_id)

    traceparent = sentry_sdk.Hub.current.scope.transaction.to_traceparent()
    await tasks.run_ai_turns.defer_async(traceparent=traceparent, match_id=match_id)

    match = await service.get_match(database, match_id)
    return view(request, "connect4_match.html", user=user, match=match)


@app.post("/app/agents/create_agent", response_class=HTMLResponse)
async def create_agent(
    request: Request,
    response: Response,
    user: AuthUser = Depends(auth),
    new_agent: AgentCreate = Depends(AgentCreate.as_form),
) -> Any:
    create_agent_errors = None

    try:
        await service.create_agent(database, user.user_id, new_agent)
    except Exception as e:
        create_agent_errors = [str(e)]

    response.headers["hx-trigger"] = "AgentUpdate"

    return view(
        request,
        "app.html",
        block_name="create_agent",
        user=user,
        create_agent_errors=create_agent_errors,
    )


@app.delete("/app/agents/{username}/{agentname}", response_class=HTMLResponse)
async def create_agent(
    request: Request,
    response: Response,
    username: str,
    agentname: str,
    user: AuthUser = Depends(auth),
) -> Any:
    deleted = await service.delete_agent(database, user.user_id, username, agentname)
    if deleted:
        response.headers["hx-trigger"] = "AgentUpdate"
        return "ok"
    else:
        raise HTTPException(status_code=404, detail="Agent not found")


@app.on_event("startup")
async def startup() -> None:
    await database.connect()
    await papp.open_async()
    setup_tracing()


@app.on_event("shutdown")
async def shutdown() -> None:
    await database.disconnect()
    await papp.close_async()
