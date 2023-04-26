from databases import Database

from .schemas import Agent, Game
from .tables import agents, games

from gameplay_computer.users.repo import get_user_by_id, get_user_by_username, get_user_id_for_username


async def get_game_by_id(database: Database, game_id: int) -> Game | None:
    game = await database.fetch_one(query=games.select().where(games.c.id == game_id))
    if game is None:
        return None
    return Game.from_orm(game)


async def get_game_by_name(database: Database, name: str) -> Game | None:
    game = await database.fetch_one(query=games.select().where(games.c.name == name))
    if game is None:
        return None
    return Game.from_orm(game)


async def get_agent_by_id(database: Database, agent_id: int) -> Agent | None:
    agent = await database.fetch_one(
        query=agents.select().where(agents.c.id == agent_id)
    )
    if agent is None:
        return None
    user = await get_user_by_id(agent["user_id"])
    assert user is not None
    return Agent(
        game="connect4",
        username=user.username,
        agentname=agent["agentname"],
    )

async def get_agent_by_username_and_agentname(
        database: Database, username: str, agentname: str
    ) -> Agent | None:
    user_id = await get_user_id_for_username(username)
    assert user_id is not None
    agent = await database.fetch_one(
        query=agents.select().where(
            (agents.c.user_id == user_id) & (agents.c.agentname == agentname)
        )
    )
    if agent is None:
        return None
    return Agent(
        game="connect4",
        username=username,
        agentname=agent["agentname"],
    )

async def get_agent_id_for_username_and_agentname(
    database: Database, username: str, agentname: str
) -> int | None:
    user_id = await get_user_id_for_username(username)
    assert user_id is not None
    agent_id = await database.fetch_val(
        query=agents.select().where(
            (agents.c.user_id == user_id) & (agents.c.agentname == agentname)
        ),
        column="id",
    )
    if agent_id is None:
        return None
    return int(agent_id)
