from databases import Database
from fastapi import HTTPException, status
import httpx
import asyncio
from typing import assert_never

from gameplay_computer.gameplay import Match, Connect4Action, Action, Game, Agent

from gameplay_computer import users
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
    agent_id: int,
    match: Match,
) -> Action:
    agent = await get_agent_by_id(database, agent_id)
    deployment = await repo.get_agent_deployment_by_id(database, agent_id)
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
    # We are sort of assuming right now that we know the agent is the next player and
    # that somebody else checked that before calling this.
    # It'll get checked again when the turn is created.

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
