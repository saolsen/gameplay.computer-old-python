import pytest
import databases
from httpx import AsyncClient
from fastapi import HTTPException

from gameplay_computer.gameplay import Connect4Action
from gameplay_computer import users, matches, agents


async def test_database(database: databases.Database) -> None:
    result = await database.fetch_val(query="SELECT 1")
    assert result == 1


async def test_api(api: AsyncClient, user_steve: str) -> None:
    response = await api.get("/")
    assert 200 == response.status_code
    assert response.headers["content-type"] == "text/html; charset=utf-8"

    response = await api.get("/", headers={"Authorization": user_steve})
    assert 200 == response.status_code


async def test_a_match(database: databases.Database, user_steve: str) -> None:
    steve = await users.get_user_by_id(user_steve)
    assert steve is not None
    match_id = await matches.create_match(
        database, user_steve, "connect4", [steve, steve]
    )
    with pytest.raises(HTTPException):
        # player 0 goes first, not 1
        await matches.take_action(
            database,
            match_id,
            1,
            Connect4Action(column=0),
            acting_user_id=user_steve,
        )
    await matches.take_action(
        database,
        match_id,
        0,
        Connect4Action(column=0),
        acting_user_id=user_steve,
    )
    await matches.take_action(
        database,
        match_id,
        1,
        Connect4Action(column=1),
        acting_user_id=user_steve,
    )
    match = await matches.get_match_by_id(database, match_id)
    assert match is not None
    assert match.state.next_player == 0
    for _ in range(3):
        await matches.take_action(
            database,
            match_id,
            0,
            Connect4Action(column=2),
            acting_user_id=user_steve,
        )
        await matches.take_action(
            database,
            match_id,
            1,
            Connect4Action(column=1),
            acting_user_id=user_steve,
        )
    match = await matches.get_match_by_id(database, match_id)
    assert match is not None
    assert match.state.over is True
    assert match.state.winner == 1
    assert match.state.next_player is None


# def need more helpers dawg
# easy way to run a bunch of turns or whatever.


async def test_your_turn(
    database: databases.Database, user_gabe: str, user_steve: str
) -> None:
    steve = await users.get_user_by_id(user_steve)
    gabe = await users.get_user_by_id(user_gabe)
    assert steve is not None
    assert gabe is not None
    match_id = await matches.create_match(
        database, user_steve, "connect4", [steve, gabe]
    )
    await matches.take_action(
        database,
        match_id,
        0,
        Connect4Action(column=0),
        acting_user_id=user_steve,
    )
    await matches.take_action(
        database,
        match_id,
        1,
        Connect4Action(column=1),
        acting_user_id=user_gabe,
    )
    with pytest.raises(HTTPException):
        # gabe tries to go again, no no gabe
        await matches.take_action(
            database,
            match_id,
            1,
            Connect4Action(column=1),
            acting_user_id=user_gabe,
        )
    with pytest.raises(HTTPException):
        # gabe tries to go for steve, no way gabe
        await matches.take_action(
            database,
            match_id,
            0,
            Connect4Action(column=1),
            acting_user_id=user_gabe,
        )


async def test_agents(
    database: databases.Database, agent_api: AsyncClient, user_steve: str
) -> None:
    agent_id = await agents.create_agent(
        database,
        user_steve,
        "connect4",
        "random",
        "http://test-agents.com/connect4_random",
    )
    rand_agent = await agents.get_agent_by_id(database, agent_id)
    match_id = await matches.create_match(
        database, user_steve, "connect4", [rand_agent, rand_agent]
    )
    match = await matches.get_match_by_id(database, match_id)
    player = 0
    # Play out a match, random vs random
    while not match.state.over:
        action = await agents.get_agent_action(database, agent_api, rand_agent, match)
        match = await matches.take_action(
            database,
            match,
            player,
            action,
            actor=rand_agent,
        )
        player = 1 if player == 0 else 0
