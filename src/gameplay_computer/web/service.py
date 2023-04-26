import random
from typing import assert_never

from databases import Database

from gameplay_computer.games.connect4 import Action as Connect4Action
from gameplay_computer.games.connect4 import State as Connect4State

from ..common import repo as common_repo
from ..common import schemas as common_schemas
from ..matches import repo as matches_repo
from ..matches import schemas as matches_schemas
from ..users import repo as users_repo
from ..users import schemas as users_schemas
from ..web.schemas import MatchCreate, TurnCreate

# TODO: we don't wanna import any tables in service,
# that's sorta how we know we're doing well.


# Stubs to keep web working.
async def get_clerk_users() -> list[users_schemas.User]:
    return await users_repo.list_users()


async def get_clerk_user_by_id(user_id: str) -> users_schemas.User | None:
    return await users_repo.get_user_by_id(user_id)


async def get_matches(
    database: Database, user_id: str
) -> list[matches_schemas.MatchSummary]:
    return await matches_repo.list_match_summaries_for_user(database, user_id)


async def create_match(
    created_by: str, database: Database, new_match: MatchCreate
) -> int:
    async with database.transaction():
        created_user = await users_repo.get_user_by_id(created_by)
        assert created_user is not None

        # players

        new_match_players = [
            (new_match.player_type_1, new_match.player_name_1),
            (new_match.player_type_2, new_match.player_name_2),
        ]

        players: list[users_schemas.User | common_schemas.Agent] = []
        for new_match_player in new_match_players:
            type, name = new_match_player
            match type:
                case "me" | "user":
                    user = await users_repo.get_user_by_username(name)
                    assert user is not None
                    players.append(user)
                case "agent":
                    username, agentname = name.split("/")
                    agent = await common_repo.get_agent_by_username_and_agentname(
                        database, username, agentname
                    )
                    assert agent is not None
                    players.append(agent)
                case _type as unknown:
                    assert_never(unknown)

        created_by_username = created_user.username

        # Some janky authorization, this should actually be done in the form so
        # the user gets error messages.
        if new_match.player_type_1 == "me":
            assert new_match.player_name_1 == created_by_username
        if new_match.player_type_2 == "me":
            assert new_match.player_name_2 == created_by_username
        if new_match.player_type_1 == "user":
            assert new_match.player_name_1 != created_by_username
        if new_match.player_type_2 == "user":
            assert new_match.player_name_2 != created_by_username

        if new_match.player_type_1 == "user" and new_match.player_type_2 == "user":
            assert False, "You have to be one of the players."
        if new_match.player_type_1 == "user" and new_match.player_type_2 == "agent":
            assert False, "You have to be one of the players."
        if new_match.player_type_1 == "agent" and new_match.player_type_2 == "user":
            assert False, "You have to be one of the players."

        assert new_match.game == "connect4"
        state = Connect4State()

        match_id = await matches_repo.create_match(
            database,
            matches_schemas.CreateMatch(
                created_by=created_user,
                players=players,
                state=state,
            ),
        )

    return match_id


async def get_match(
    database: Database, match_id: int, turn: int | None = None
) -> matches_schemas.Match | None:
    match = await matches_repo.get_match_by_id(database, match_id, turn=turn)
    return match


async def take_ai_turn(
    database: Database,
    match_id: int,
) -> None:
    async with database.transaction():
        match = await get_match(database, match_id)
        assert match is not None
        assert match.state.next_player is not None
        agent = match.players[match.state.next_player]
        assert isinstance(agent, common_schemas.Agent)

        assert agent.agentname == "random"

        # todo: rework take_turn to not need the id (or something)
        agent_id = await common_repo.get_agent_id_for_username_and_agentname(
            database, agent.username, agent.agentname
        )
        assert agent_id is not None

        actions = match.state.actions()
        action = random.choice(actions)

        assert isinstance(action, Connect4Action)

        await take_turn(
            database,
            match_id,
            TurnCreate(column=action.column, player=match.state.next_player),
            agent_id=agent_id,
        )


async def take_turn(
    database: Database,
    match_id: int,
    new_turn: TurnCreate,
    user_id: str | None = None,
    agent_id: int | None = None,
) -> matches_schemas.Match:
    # todo: better way to handle this
    assert user_id is not None or agent_id is not None
    assert user_id is None or agent_id is None

    async with database.transaction():
        match = await get_match(database, match_id)
        assert match is not None

        assert match.state.next_player is not None
        assert match.state.next_player == new_turn.player
        assert match.state.next_player in match.players
        next_player = match.players[match.state.next_player]
        assert next_player is not None
        if user_id is not None:
            clerk_user = await users_repo.get_user_by_id(user_id)
            assert clerk_user is not None
            assert isinstance(next_player, users_schemas.User)
            assert next_player.username == clerk_user.username
        elif agent_id is not None:
            # todo
            pass

        action: matches_schemas.Action
        next_state: matches_schemas.State
        match match.state.game:
            case "connect4":
                assert isinstance(match.state, Connect4State)
                action = Connect4Action(column=new_turn.column)
                assert action in match.state.actions()

                next_state = match.state.turn(new_turn.player, action)

            case _game as unknown:
                assert_never(unknown)

        await matches_repo.create_match_turn(
            database,
            match_id,
            matches_schemas.CreateTurn(
                player=new_turn.player,
                action=action.serialize(),
                state=next_state.serialize(),
                next_player=next_state.next_player,
                winner=next_state.winner,
            ),
        )

        match = await get_match(database, match_id)
        assert match is not None

    return match
