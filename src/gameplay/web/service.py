import random

from databases import Database

from .. import connect4
from .schemas import Match, MatchCreate, Turn, TurnCreate
from .tables import matches, turns


def check(match: Match) -> tuple[str, int | None] | None:
    """
    See if anybody won yet.
    Just check in a dumb way for now, each possibility
    """
    # Check rows
    for row in range(0, 6):
        for col in range(0, 4):
            if (
                match.state[col][row] != 0
                and match.state[col][row]
                == match.state[col + 1][row]
                == match.state[col + 2][row]
                == match.state[col + 3][row]
            ):
                return "WIN", match.state[col][row]
    # Check cols
    for col in range(0, 7):
        for row in range(0, 3):
            if (
                match.state[col][row] != 0
                and match.state[col][row]
                == match.state[col][row + 1]
                == match.state[col][row + 2]
                == match.state[col][row + 3]
            ):
                return "WIN", match.state[col][row]
    # Check diag up
    for col in range(0, 4):
        for row in range(0, 3):
            if (
                match.state[col][row] != 0
                and match.state[col][row]
                == match.state[col + 1][row + 1]
                == match.state[col + 2][row + 2]
                == match.state[col + 3][row + 3]
            ):
                return ("WIN", match.state[col][row])

    # Check diag down
    for col in range(0, 4):
        for row in range(3, 6):
            if (
                match.state[col][row] != 0
                and match.state[col][row]
                == match.state[col + 1][row - 1]
                == match.state[col + 2][row - 2]
                == match.state[col + 3][row - 3]
            ):
                return "WIN", match.state[col][row]

    # Check draw
    for col in range(0, 7):
        if match.state[col][5] == 0:
            # There are still moves left
            return None

    return "DRAW", None


async def create_match(database: Database, new_match: MatchCreate) -> Match:
    insert_query = matches.insert().values(
        game=new_match.game,
        opponent=new_match.opponent,
        state=(
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
        ),
        turn=0,
        next_player=1,
    )
    async with database.transaction():
        match_id = await database.execute(query=insert_query)
        match = await get_match(database, match_id)
        return match


async def get_match(database: Database, match_id: int) -> Match:
    match = await database.fetch_one(
        query=matches.select().where(matches.c.id == match_id)
    )
    match_turns = await database.fetch_all(
        query=turns.select().where(turns.c.match_id == match_id)
    )

    assert match is not None
    return Match(**dict(match), turns=[Turn(**dict(t)) for t in match_turns])


async def take_ai_turn(database: Database, match_id: int) -> None:
    async with database.transaction():
        match = await get_match(database, match_id)
        if match.winner is not None:
            return
        columns = [i for i in range(7) if match.state[i][5] == 0]

        column = random.choice(columns)
        await take_turn(database, match_id, TurnCreate(column=column, player=2))
        await database.execute(
            query="select pg_notify('test', :match_id)",
            values={"match_id": str(match_id)},
        )


async def take_turn(database: Database, match_id: int, new_turn: TurnCreate) -> Match:
    async with database.transaction():
        match = await get_match(database, match_id)
        assert match is not None

        state = connect4.State(
            board=match.state, next_player=connect4.Player(match.next_player)
        )
        assert new_turn.column in state.actions()

        result = state.turn(connect4.Player(new_turn.player), new_turn.column)
        winner: int | None
        match result:
            case connect4.Player():
                winner = result.value
            case "draw":
                winner = 0
            case None:
                winner = None

        insert_turn = turns.insert().values(
            number=match.turn + 1,
            match_id=match_id,
            player=new_turn.player,
            column=new_turn.column,
        )
        update_match = (
            matches.update()
            .where(matches.c.id == match_id)
            .values(
                state=state.board,
                turn=match.turn + 1,
                next_player=state.next_player.value,
                winner=winner,
            )
        )
        await database.execute(query=insert_turn)
        await database.execute(query=update_match)
        match = await get_match(database, match_id)

    return match


async def get_matches(database: Database, user_id: int) -> list[Match]:
    # todo: filter by user_id
    user_matches = await database.fetch_all(matches.select())
    return [Match(**dict(m), turns=[]) for m in user_matches]


# Service stuff
# Users
# Games
# Matches
# Agents
