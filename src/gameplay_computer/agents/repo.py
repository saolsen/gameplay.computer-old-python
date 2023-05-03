from databases import Database
from .schemas import AgentDeployment
from . import tables
from gameplay_computer.gameplay import Agent
from gameplay_computer import users
import sqlalchemy


async def create_agent(
    database: Database, created_by_user_id: str, game: str, agentname: str, url: str
) -> int:
    async with database.transaction():
        agent_id: int = await database.execute(
            query=tables.agents.insert().values(
                game=game,
                user_id=created_by_user_id,
                agentname=agentname,
                created_at=sqlalchemy.func.now(),
            )
        )
        await database.execute(
            query=tables.agent_deployment.insert().values(
                agent_id=agent_id,
                url=url,
                healthy=True,
                active=False,
            )
        )
        await database.execute(
            query=tables.agent_history.insert().values(
                agent_id=agent_id,
                wins=0,
                losses=0,
                draws=0,
                errors=0,
            )
        )
    return agent_id


async def get_agent_by_id(database: Database, agent_id: int) -> Agent | None:
    agent = await database.fetch_one(
        query=tables.agents.select().where(tables.agents.c.id == agent_id)
    )
    if agent is None:
        return None
    user = await users.get_user_by_id(agent["user_id"])
    assert user is not None
    return Agent(
        game=agent["game"],
        username=user.username,
        agentname=agent["agentname"],
    )


async def get_agent_by_username_and_agentname(
    database: Database, username: str, agentname: str
) -> Agent | None:
    user_id = await users.get_user_id_for_username(username)
    assert user_id is not None
    agent = await database.fetch_one(
        query=tables.agents.select().where(
            (tables.agents.c.user_id == user_id)
            & (tables.agents.c.agentname == agentname)
        )
    )
    if agent is None:
        return None
    return Agent(
        game=agent["game"],
        username=username,
        agentname=agent["agentname"],
    )


async def get_agent_id_for_username_and_agentname(
    database: Database, username: str, agentname: str
) -> int | None:
    user_id = await users.get_user_id_for_username(username)
    assert user_id is not None
    agent_id = await database.fetch_val(
        query=tables.agents.select().where(
            (tables.agents.c.user_id == user_id)
            & (tables.agents.c.agentname == agentname)
        ),
        column="id",
    )
    if agent_id is None:
        return None
    return int(agent_id)


async def get_agent_deployment_by_id(
    database: Database, agent_id: int
) -> AgentDeployment | None:
    agent_deployment = await database.fetch_one(
        query=tables.agent_deployment.select().where(
            tables.agent_deployment.c.agent_id == agent_id
        )
    )
    if agent_deployment is None:
        return None
    return AgentDeployment(
        url=agent_deployment["url"],
        healthy=agent_deployment["healthy"],
        active=agent_deployment["active"],
    )
