import json

import sqlalchemy
from databases import Database

from gameplay_computer.games.connect4 import State as Connect4State

from ..common import repo as cr
from ..common import schemas as cs
from ..users import repo as ur
from ..users import schemas as us
from .schemas import CreateMatch, CreateTurn, Match, MatchSummary, Player, Turn
from .tables import match_players, match_turns, matches


async def create_match(database: Database, match: CreateMatch) -> int:
    async with database.transaction():
        # create the match
        created_by_id = await ur.get_user_id_for_username(match.created_by.username)
        assert created_by_id is not None
        match_id: int = await database.execute(
            query=matches.insert().values(
                game=match.state.game,
                status="in_progress",
                winner=match.state.winner,
                created_by=created_by_id,
                created_at=sqlalchemy.func.now(),
                finished_at=None,
            ),
        )

        # create the players
        for i, player in enumerate(match.players):
            match player:
                case us.User() as user:
                    user_id = await ur.get_user_id_for_username(user.username)
                    assert user_id is not None
                    await database.execute(
                        query=match_players.insert().values(
                            match_id=match_id,
                            number=i + 1,
                            user_id=user_id,
                            agent_id=None,
                        )
                    )
                case cs.Agent() as agent:
                    agent_id = await cr.get_agent_id_for_username_and_agentname(
                        database, agent.username, agent.agentname
                    )
                    assert agent_id is not None
                    await database.execute(
                        query=match_players.insert().values(
                            match_id=match_id,
                            number=i + 1,
                            user_id=None,
                            agent_id=agent_id,
                        )
                    )

        # create the initial turn
        await database.execute(
            query=match_turns.insert().values(
                match_id=match_id,
                number=0,
                player=None,
                action=None,
                state=match.state.serialize(),
                next_player=match.state.next_player,
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
                values={"match_id": match_id, "winner": turn.winner},
            )

        # notify
        await database.execute(
            query="select pg_notify('test', :match_id)",
            values={"match_id": str(match_id)},
        )


async def list_match_summaries_for_user(
    database: Database, user_id: str
) -> list[MatchSummary]:
    matches_r = await database.fetch_all(
        query="""
            with created_matches as (
                select
                    id as match_id
                from matches
                where created_by = :user_id
            ), playing_matches as (
                select
                    match_id
                from match_players
                where user_id = :user_id
            ), my_matches as (select *
                              from created_matches
                              union
                              select *
                              from playing_matches
            ) select
                m.id as id,
                m.game as game_name,
                blue_mp.user_id as blue_user_id,
                blue_a.agentname as blue_agent_name,
                blue_a.user_id as blue_agent_user_id,
                red_mp.user_id as red_user_id,
                red_a.agentname as red_agent_name,
                red_a.user_id as red_agent_user_id,
                m.status,
                mt.next_player,
                mt.created_at as last_turn_at,
                m.winner,
                coalesce(next_mp.user_id = :user_id, false) as is_next_player
            from matches m

            join match_turns mt
            on m.id = mt.match_id
            and (
                select max(number)
                from match_turns
                where match_id = m.id
            ) = mt.number    

            left join match_players next_mp
            on mt.next_player = next_mp.number and m.id = next_mp.match_id
            join match_players blue_mp
            on blue_mp.number = 1 and m.id = blue_mp.match_id
            left join agents blue_a
            on blue_mp.agent_id = blue_a.id
            join match_players red_mp
            on red_mp.number = 2 and m.id = red_mp.match_id
            left join agents red_a
            on red_mp.agent_id = red_a.id
            where m.id in (select * from my_matches)
            order by is_next_player desc, mt.created_at desc;
            """,
        values={"user_id": user_id},
    )
    matches = []
    for match in matches_r:
        if match["blue_user_id"] is not None:
            blue_user = await ur.get_user_by_id(match["blue_user_id"])
            assert blue_user is not None
            blue = blue_user.username
        else:
            blue_user = await ur.get_user_by_id(match["blue_agent_user_id"])
            assert blue_user is not None
            blue = f"{blue_user.username}/{match['blue_agent_name']}"

        if match["red_user_id"] is not None:
            red_user = await ur.get_user_by_id(match["red_user_id"])
            assert red_user is not None
            red = red_user.username
        else:
            red_user = await ur.get_user_by_id(match["red_agent_user_id"])
            assert red_user is not None
            red = f"{red_user.username}/{match['red_agent_name']}"

        matches.append(
            MatchSummary(
                id=match["id"],
                game_name=match["game_name"],
                blue=blue,
                red=red,
                status=match["status"],
                winner=match["winner"],
                last_turn_at=match["last_turn_at"],
                next_player=match["next_player"],
                is_next_player=match["is_next_player"],
            )
        )

    return matches


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

    created_by = await ur.get_user_by_id(match_r["created_by"])

    players: dict[int, Player] = {}
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

    match match_r["game"]:
        case "connect4":
            state = Connect4State.deserialize(
                False,
                match_r["winner"],
                latest_turn_r["next_player"],
                latest_turn_r["state"],
            )
        case _game as game:
            assert False, f"Unknown game: {game}"

    match = Match(
        status=match_r["status"],
        created_by=created_by,
        created_at=match_r["created_at"],
        finished_at=match_r["finished_at"],
        players=players,
        turns=turns,
        turn=turn,
        updated_at=latest_turn_r["created_at"],
        state=state,
    )

    return match
