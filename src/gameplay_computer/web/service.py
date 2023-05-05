from typing import assert_never

from fastapi import HTTPException, status

from databases import Database

from gameplay_computer.gameplay import Agent, User, Match, Connect4Action
from gameplay_computer import gameplay
from gameplay_computer import matches, users, agents

from .schemas import MatchCreate, TurnCreate, AgentCreate
import httpx


# Stubs to keep web working.
async def get_users() -> list[users.FullUser]:
    return await users.list_users()


async def get_user(user_id: str | None) -> User:
    if user_id is not None:
        user = await users.get_user_by_id(user_id)
        if user is not None:
            return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unknown user.",
    )


async def get_user_by_id(user_id: str) -> User | None:
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
) -> Match:
    match = await matches.get_match_by_id(database, match_id, turn=turn)
    return match


async def create_agent(
    database: Database, created_by_user_id: str, new_agent: AgentCreate
) -> int:
    agent_id = await agents.create_agent(
        database, created_by_user_id, new_agent.game, new_agent.agentname, new_agent.url
    )
    return agent_id


async def take_ai_turn(
    database: Database,
    client: httpx.AsyncClient,
    match_id: int,
) -> Match:
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

    post_state = gameplay.Connect4State(
        over=False,
        winner=None,
        next_player=match.state.next_player,
        board=match.state.board,
    )

    post_players: list[gameplay.Player] = []

    for player in match.players:
        if player.kind == "user":
            post_players.append(
                gameplay.User(
                    username=player.username,
                )
            )
        elif player.kind == "agent":
            post_players.append(
                gameplay.Agent(
                    game="connect4",
                    username=player.username,
                    agentname=player.agentname,
                )
            )

    post_turns = []

    for turn in match.turns:
        post_turns.append(
            gameplay.Turn(
                number=turn.number,
                player=turn.player,
                action=turn.action,
                next_player=turn.next_player,
            )
        )

    gp_match = gameplay.Match(
        id=match.id,
        players=post_players,
        turns=post_turns,
        turn=match.turn,
        state=post_state,
    )

    gp_action = await agents.get_agent_action(database, client, agent_id, gp_match)
    action = Connect4Action(column=gp_action.column)

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
) -> Match:
    return await matches.take_action(
        database,
        match_id,
        new_turn.player,
        Connect4Action(column=new_turn.column),
        user_id,
        agent_id,
    )
