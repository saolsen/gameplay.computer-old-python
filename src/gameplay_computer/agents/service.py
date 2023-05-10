import asyncio
from typing import assert_never

import httpx
import sentry_sdk
from databases import Database
from fastapi import HTTPException, status

from gameplay_computer import users
from gameplay_computer.gameplay import Action, Agent, Connect4Action, Game, Match, Turn

from ..games import Connect4Logic
from . import repo


async def create_agent(
    database: Database,
    created_by_user_id: str,
    game: Game,
    agentname: str,
    url: str,
) -> int:
    created_by_user = await users.get_user_by_id(created_by_user_id)
    if created_by_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unknown user.",
        )

    turn = Turn(
        number=0,
        player=None,
        action=None,
        next_player=0,
    )
    fake_players = [
        Agent(
            game=game,
            username=created_by_user.username,
            agentname=agentname,
        ),
        Agent(
            game=game,
            username=created_by_user.username,
            agentname=agentname,
        ),
    ]
    state = Connect4Logic.initial_state()
    fake_match = Match(
        id=1,
        players=fake_players,
        turns=[turn],
        turn=0,
        state=state,
    )
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=fake_match.dict(), timeout=1)
        except (httpx.ReadTimeout, httpx.ConnectError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent doesn't seem online.",
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent doesn't seem online.",
            )
        match fake_match.state.game:
            case "connect4":
                Connect4Action(**response.json())
            case _game as unknown:
                assert_never(unknown)

    agent_id = await repo.create_agent(
        database, created_by_user_id, game, agentname, url
    )
    return agent_id


async def get_agent_by_id(database: Database, agent_id: int) -> Agent:
    agent = await repo.get_agent_by_id(database, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown agent.",
        )
    return agent


async def get_agent_by_username_and_agentname(
    database: Database, username: str, agentname: str
) -> Agent:
    agent = await repo.get_agent_by_username_and_agentname(
        database, username, agentname
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown agent.",
        )
    return agent


async def get_agent_id_for_username_and_agentname(
    database: Database, username: str, agentname: str
) -> int:
    agent_id = await repo.get_agent_id_for_username_and_agentname(
        database, username, agentname
    )
    if agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown agent.",
        )
    return agent_id


async def get_agent_action(
    database: Database,
    client: httpx.AsyncClient,
    agent: Agent,
    match: Match,
) -> Action:
    span = sentry_sdk.Hub.current.scope.span
    if span is not None:
        span.set_tag("agent", f"{agent.username}/{agent.agentname}")

    deployment = await repo.get_agent_deployment(database, agent)
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown agent.",
        )
    if agent.game != match.state.game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wrong game.",
        )

    action: Action | None = None

    retries = 0
    while retries < 3:
        try:
            response = await client.post(deployment.url, json=match.dict())
            response.raise_for_status()
            match match.state.game:
                case "connect4":
                    action = Connect4Action(**response.json())
                case _game as unknown:
                    assert_never(unknown)
            break
        except httpx.HTTPError as e:
            print(f"Error: {e}")
            retries += 1
            await asyncio.sleep(retries)

    # todo: log errors
    if action is None:
        print("ERROR: too many agent errors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Too many agent errors.",
        )

    return action


async def list_agents(database: Database) -> list[Agent]:
    agents = await repo.list_agents(database)
    return agents
