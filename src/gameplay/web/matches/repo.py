import sqlalchemy
from databases import Database
from .tables import matches, match_players, match_turns
from ..common import schemas as cs
from ..common import repo as cr
from ..users import schemas as us
from ..users import repo as ur
from .schemas import CreateMatch, CreateTurn, Match, MatchSummary, Turn
import json


async def create_match(database: Database, match: CreateMatch) -> int:
    async with database.transaction():
        # create the match
        match_id: int = await database.execute(
            query=matches.insert().values(
                game_id=match.game.id,
                status="in_progress",
                winner=None,
                created_by=match.created_by.id,
                created_at=sqlalchemy.func.now(),
                finished_at=None,
            ),
        )

        # create the players
        for i, player in enumerate(match.players):
            match player:
                case us.User() as user:
                    await database.execute(
                        query=match_players.insert().values(
                            match_id=match_id,
                            number=i + 1,
                            user_id=user.id,
                            agent_id=None,
                        )
                    )
                case cs.Agent() as agent:
                    await database.execute(
                        query=match_players.insert().values(
                            match_id=match_id,
                            number=i + 1,
                            user_id=None,
                            agent_id=agent.id,
                        )
                    )

        # create the initial turn
        await database.execute(
            query=match_turns.insert().values(
                match_id=match_id,
                number=0,
                player=None,
                action=None,
                # todo: these last two are both connect4 specific
                state=[[0] * 6 for _ in range(7)],
                next_player=1,
                created_at=sqlalchemy.func.now(),
            )
        )

    return match_id


async def create_match_turn(
    database: Database, match_id: int, turn: CreateTurn
) -> None:
    """
    Adds a turn to a match.
    If there is no next player, the match is set to "finished".
    If there is a winner, it's added.
    """
    async with database.transaction():
        await database.execute(
            query="""
            insert into match_turns (
                match_id,
                number,
                player,
                action,
                state,
                next_player,
                created_at
            ) values (
                :match_id,
                (select max(number) from match_turns where match_id = :match_id) + 1,
                :player,
                :action,
                :state,
                :next_player,
                now()
            )            
            """,
            values={
                "match_id": match_id,
                "player": turn.player,
                "action": json.dumps(turn.action),
                "state": json.dumps(turn.state),
                "next_player": turn.next_player,
            },
        )

        if turn.next_player is None:
            await database.execute(
                query="""
                update matches set
                    status = 'finished',
                    winner = :winner,
                    finished_at = now()
                where id = :match_id
                """,
                values={"match_id": match_id, "winner": turn.winner}
            )

        # notify
        await database.execute(
            query="select pg_notify('test', :match_id)",
            values={"match_id": str(match_id)},
        )


async def list_match_summaries_for_user(user_id: str) -> list[MatchSummary]:
    return []


# Match with players, turns and state?
async def get_match_by_id(
    database: Database, match_id: int, turn: int | None = None
) -> Match | None:
    """
    Fetch a match by id.
    If turn is not None, the state of the match is set to the state of the turn.
    Otherwise, the state of the match is the state of the latest turn.
    """
    async with database.transaction():
        match_r = await database.fetch_one(
            query=matches.select().where(matches.c.id == match_id)
        )
        if match_r is None:
            return None

        players_r = await database.fetch_all(
            query=match_players.select().where(match_players.c.match_id == match_id)
        )

        turns_r = await database.fetch_all(
            query=sqlalchemy.sql.expression.select(
                [
                    match_turns.c.number,
                    match_turns.c.player,
                    match_turns.c.action,
                    match_turns.c.next_player,
                    match_turns.c.created_at,
                ]
            ).where(match_turns.c.match_id == match_id)
        )

        turns_r.sort(key=lambda turn_r: int(turn_r["number"]))

        if turn is None:
            turn = max(turn["number"] for turn in turns_r)

        q = match_turns.select().where(
            (match_turns.c.match_id == match_id) & (match_turns.c.number == turn)
        )
        latest_turn_r = await database.fetch_one(query=q)
        assert latest_turn_r is not None

        game = await cr.get_game_by_id(database, match_r["game_id"])
        assert game is not None

    created_by = await ur.get_user_by_id(match_r["created_by"])

    players: dict[int, us.User | cs.Agent] = {}
    for player_r in players_r:
        if player_r["user_id"] is not None:
            user = await ur.get_user_by_id(player_r["user_id"])
            assert user is not None
            players[player_r["number"]] = user
        elif player_r["agent_id"] is not None:
            agent = await cr.get_agent_by_id(database, player_r["agent_id"])
            assert agent is not None
            players[player_r["number"]] = agent
        else:
            assert False

    turns = [Turn.from_orm(turn_r) for turn_r in turns_r]

    match = Match(
        id=match_r["id"],
        game=game,
        status=match_r["status"],
        winner=match_r["winner"],
        created_by=created_by,
        created_at=match_r["created_at"],
        finished_at=match_r["finished_at"],
        players=players,
        turns=turns,
        turn=turn,
        next_player=latest_turn_r["next_player"],
        state=latest_turn_r["state"],
        updated_at=latest_turn_r["created_at"],
    )

    return match
