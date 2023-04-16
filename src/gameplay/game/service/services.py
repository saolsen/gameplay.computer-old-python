from ..domain import model
from ..domain.model import Game, Player
from .session import Session


async def create_match(session: Session) -> int:
    async with session.transaction():
        game = Game()
        match_id = await session.games.create(game)
        
        session.event(MatchCreated(match_id=match_id)))

    return match_id


async def get_match(match_id: int, session: Session) -> Match:
    game = await session.games.get(match_id)
        # should basically do this in the repo
        """ match = await database.fetch_one(
            query=matches.select().where(matches.c.id == match_id)
        )
        match_turns = await database.fetch_all(
            query=turns.select().where(turns.c.match_id == match_id)
        ) """

    assert game is not None
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
