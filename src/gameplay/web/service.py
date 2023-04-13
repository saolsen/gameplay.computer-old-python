from .schemas import MatchCreate, Match, TurnCreate, Turn
from .tables import matches, turns
import random
from databases import Database
import asyncio


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


async def follow_match():
    pass


async def stop_following_match():
    pass


async def take_ai_turn(database: Database, match_id: int):
    # pretend this takes a while
    await asyncio.sleep(1)
    async with database.transaction():
        await take_turn(
            database, match_id, TurnCreate(column=random.randint(0, 6), player=2)
        )
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
            )
        )
        await database.execute(query=insert_turn)
        await database.execute(query=update_match)
        match = await get_match(database, match_id)

    return match
