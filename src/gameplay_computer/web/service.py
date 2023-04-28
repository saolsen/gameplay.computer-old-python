import random
from typing import assert_never

from databases import Database

from gameplay_computer import matches, users, agents
from gameplay_computer.agents import Agent
from gameplay_computer.users import User

from gameplay_computer.games.connect4 import Action as Connect4Action
from .schemas import MatchCreate, TurnCreate


# Stubs to keep web working.
async def get_clerk_users() -> list[User]:
    return await users.list_users()


async def get_clerk_user_by_id(user_id: str) -> User | None:
    return await users.get_user_by_id(user_id)


async def get_matches(database: Database, user_id: str) -> list[matches.MatchSummary]:
    return await matches.list_match_summaries_for_user(database, user_id)


async def create_match(
    created_by_user_id: str, database: Database, new_match: MatchCreate
) -> int:
    created_user = await users.get_user_by_id(created_by_user_id)
    assert created_user is not None

    # players
    new_match_players = [
        (new_match.player_type_1, new_match.player_name_1),
        (new_match.player_type_2, new_match.player_name_2),
    ]

    # This is like a from_form method, could go in the MatchCreate
    players: list[User | Agent] = []
    for new_match_player in new_match_players:
        type, name = new_match_player
        match type:
            case "me" | "user":
                user = await users.get_user_by_username(name)
                assert user is not None
                players.append(user)
            case "agent":
                username, agentname = name.split("/")
                agent = await agents.get_agent_by_username_and_agentname(
                    database, username, agentname
                )
                assert agent is not None
                players.append(agent)
            case _type as unknown:
                assert_never(unknown)

    match_id = await matches.create_match(
        database, created_by_user_id, "connect4", players
    )

    return match_id


async def get_match(
    database: Database, match_id: int, turn: int | None = None
) -> matches.Match:
    match = await matches.get_match_by_id(database, match_id, turn=turn)
    return match


async def take_ai_turn(
    database: Database,
    match_id: int,
) -> matches.Match:
    match = await get_match(database, match_id)

    assert match.state.next_player is not None
    agent = match.players[match.state.next_player]
    assert isinstance(agent, Agent)

    assert agent.agentname == "random"

    # todo: rework take_turn to not need the id (or something)
    agent_id = await agents.get_agent_id_for_username_and_agentname(
        database, agent.username, agent.agentname
    )
    assert agent_id is not None

    actions = match.state.actions()
    action = random.choice(actions)

    assert isinstance(action, Connect4Action)

    next_match = await matches.take_action(
        database,
        match_id,
        match.state.next_player,
        action,
        acting_agent_id=agent_id,
    )
    return next_match


async def take_turn(
    database: Database,
    match_id: int,
    new_turn: TurnCreate,
    user_id: str | None = None,
    agent_id: int | None = None,
) -> matches.Match:
    return await matches.take_action(
        database,
        match_id,
        new_turn.player,
        Connect4Action(column=new_turn.column),
        user_id,
        agent_id,
    )
