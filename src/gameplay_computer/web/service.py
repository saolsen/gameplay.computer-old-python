from typing import assert_never

from databases import Database
from httpx import AsyncClient

from gameplay_computer import agents, matches, users
from gameplay_computer.gameplay import Agent, Connect4Action, Match, User

from .schemas import AgentCreate, MatchCreate, TurnCreate


async def get_users() -> list[users.FullUser]:
    return await users.list_users()


async def get_agents(
    database: Database,
) -> list[Agent]:
    return await agents.list_agents(database)


async def create_agent(
    database: Database, created_by_user_id: str, new_agent: AgentCreate
) -> int:
    agent_id = await agents.create_agent(
        database, created_by_user_id, new_agent.game, new_agent.agentname, new_agent.url
    )
    return agent_id


async def delete_agent(
    database: Database, deleted_by_user_id: str, username: str, agentname: str
) -> bool:
    return await agents.delete_agent(database, deleted_by_user_id, username, agentname)


async def get_matches(database: Database, user_id: str) -> list[matches.MatchSummary]:
    return await matches.list_match_summaries_for_user(database, user_id)


async def get_match(
    database: Database, match_id: int, turn: int | None = None
) -> Match:
    match = await matches.get_match_by_id(database, match_id, turn=turn)
    return match


async def create_match(
    database: Database, created_by_user_id: str, new_match: MatchCreate
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


async def take_turn(
    database: Database,
    match_id: int,
    new_turn: TurnCreate,
    user_id: str,
) -> Match:
    user = await users.get_user_by_id(user_id)
    assert user is not None
    match = await matches.get_match_by_id(database, match_id)
    return await matches.take_action(
        database,
        match,
        new_turn.player,
        Connect4Action(column=new_turn.column),
        actor=user,
    )


async def take_ai_turns(database: Database, client: AsyncClient, match_id: int) -> None:
    match = await get_match(database, match_id)
    while True:
        if (
            match is not None
            and match.state.over is False
            and match.state.next_player is not None
            and isinstance(match.players[match.state.next_player], Agent)
        ):
            assert match.state.next_player is not None
            agent = match.players[match.state.next_player]
            assert isinstance(agent, Agent)

            gp_action = await agents.get_agent_action(database, client, agent, match)
            action = Connect4Action(column=gp_action.column)

            match = await matches.take_action(
                database,
                match,
                match.state.next_player,
                action,
                actor=agent,
            )
        else:
            break
