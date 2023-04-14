import random

from databases import Database

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
                return ("WIN", match.state[col][row])
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
                return ("WIN", match.state[col][row])
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
                return ("WIN", match.state[col][row])

    # Check draw
    for col in range(0, 7):
        if match.state[col][5] == 0:
            # There are still moves left
            return None

    return ("DRAW", None)


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
        assert match.next_player == new_turn.player
        assert match.state[new_turn.column][5] == 0

        for i in range(6):
            if match.state[new_turn.column][i] == 0:
                match.state[new_turn.column][i] = new_turn.player
                break

        match.next_player = 1 if match.next_player == 2 else 2
        match.turn += 1

        # check for win
        result = check(match)
        if result is not None:
            kind, winner = result
            if kind == "WIN":
                match.winner = winner
            elif kind == "DRAW":
                match.winner = 0

        insert_turn = turns.insert().values(
            number=match.turn,
            match_id=match_id,
            player=new_turn.player,
            column=new_turn.column,
        )
        update_match = (
            matches.update()
            .where(matches.c.id == match_id)
            .values(
                state=match.state,
                turn=match.turn,
                next_player=match.next_player,
                winner=match.winner,
            )
        )
        await database.execute(query=insert_turn)
        await database.execute(query=update_match)
        match = await get_match(database, match_id)

    return match
