from databases import Database

from .tables import games, agents
from .schemas import Game, Agent


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
    return Agent.from_orm(agent)


async def get_agent_by_user_id_and_name(
    database: Database, user_id: str, agentname: str
) -> Agent | None:
    agent = await database.fetch_one(
        query=agents.select().where(
            (agents.c.user_id == user_id) & (agents.c.agentname == agentname)
        )
    )
    if agent is None:
        return None
    return Agent.from_orm(agent)
