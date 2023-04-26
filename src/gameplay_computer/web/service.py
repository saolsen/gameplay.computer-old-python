import random
from typing import assert_never

from databases import Database

from .. import connect4
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
        game = await common_repo.get_game_by_name(database, new_match.game)
        if not game:
            raise ValueError(f"Game {new_match.game} not found")

        # todo
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
                    user = await users_repo.get_user_by_username(username)
                    assert user is not None
                    agent = await common_repo.get_agent_by_user_id_and_name(
                        database, user.id, agentname
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

        assert game.name == "connect4"
        connect4.State()

        match_id = await matches_repo.create_match(
            database,
            matches_schemas.CreateMatch(
                game=game,
                created_by=created_user,
                players=players,
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
        assert match.next_player is not None
        agent = match.players[match.next_player]
        assert isinstance(agent, common_schemas.Agent)

        assert agent.agentname == "random"

        # Assuming connect4 and random_agent
        state = connect4.State(
            board=match.state, next_player=connect4.Player(match.next_player)
        )
        actions = state.actions()

        column = random.choice(actions)
        await take_turn(
            database,
            match_id,
            TurnCreate(column=column, player=match.next_player),
            agent_id=agent.id,
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

        assert match.next_player is not None
        assert match.next_player == new_turn.player
        assert match.next_player in match.players
        next_player = match.players[match.next_player]
        assert next_player is not None
        if user_id is not None:
            clerk_user = await users_repo.get_user_by_id(user_id)
            assert clerk_user is not None
            assert isinstance(next_player, users_schemas.User)
            assert next_player.username == clerk_user.username
        elif agent_id is not None:
            # todo
            pass

        # Assuming connect4
        state = connect4.State(
            board=match.state, next_player=connect4.Player(match.next_player)
        )
        assert new_turn.column in state.actions()

        result = state.turn(connect4.Player(new_turn.player), new_turn.column)

        winner = None
        next_player_i = None

        match result:
            case connect4.Player():
                winner = result.value
            case "draw":
                pass
            case None:
                next_player_i = state.next_player.value
            case _result as unknown:
                assert_never(unknown)

        await matches_repo.create_match_turn(
            database,
            match.id,
            matches_schemas.CreateTurn(
                player=new_turn.player,
                action=new_turn.column,
                state=state.board,
                next_player=next_player_i,
                winner=winner,
            ),
        )

        match = await get_match(database, match_id)
        assert match is not None

    return match