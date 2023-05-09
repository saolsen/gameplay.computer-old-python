from sentry_sdk.tracing import trace
import json

import sqlalchemy
from databases import Database

from gameplay_computer import users, agents, common
from gameplay_computer.gameplay import (
    User,
    Agent,
    Player,
    Match,
    Turn,
    State,
    Action,
)
from .schemas import MatchSummary

from . import tables


# todo: just all sql, fuck the orm



async def create_match(
    database: Database, created_by_user_id: str, players: list[Player], state: State
) -> int:
    async with database.transaction():
        match_id: int = await database.execute(
            query=tables.matches.insert().values(
                game=state.game,
                status="in_progress",
                winner=state.winner,
                created_by=created_by_user_id,
                created_at=sqlalchemy.func.now(),
                finished_at=None,
            ),
        )

        # create the players
        for i, player in enumerate(players):
            match player:
                case User() as user:
                    user_id = await users.get_user_id_for_username(user.username)
                    assert user_id is not None
                    await database.execute(
                        query=tables.match_players.insert().values(
                            match_id=match_id,
                            number=i,
                            user_id=user_id,
                            agent_id=None,
                        )
                    )
                case Agent() as agent:
                    agent_id = await agents.get_agent_id_for_username_and_agentname(
                        database, agent.username, agent.agentname
                    )
                    assert agent_id is not None
                    await database.execute(
                        query=tables.match_players.insert().values(
                            match_id=match_id,
                            number=i,
                            user_id=None,
                            agent_id=agent_id,
                        )
                    )

        # create the initial turn
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
                0,
                null,
                null,
                :state,
                :next_player,
                now()
            )
            """,
            values={
                "match_id": match_id,
                "state": json.dumps(common.serialize_state(state)),
                "next_player": state.next_player,
            },
        )

    return match_id



async def create_match_turn(
    database: Database,
    match_id: int,
    player: int,
    action: Action,
    state: State,
    turn_number: int,
) -> bool:
    """
    Adds a turn to a match.
    If there is no next player, the match is set to "finished".
    If there is a winner, it's added.
    If the next turn isn't turn then we don't create a turn and return False.
    This keeps us from creating double turns without making us hold a
    transaction through all the game logic.
    """
    async with database.transaction():
        latest_turn = await database.fetch_val(
            query="select max(number) from match_turns where match_id = :match_id",
            values={"match_id": match_id},
        )
        if latest_turn is not None and latest_turn + 1 != turn_number:
            return False

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
                :turn,
                :player,
                :action,
                :state,
                :next_player,
                now()
            )            
            """,
            values={
                "match_id": match_id,
                "turn": turn_number,
                "player": player,
                "action": json.dumps(common.serialize_action(action)),
                "state": json.dumps(common.serialize_state(state)),
                "next_player": state.next_player if not state.over else None,
            },
        )

        if state.over:
            await database.execute(
                query="""
                update matches set
                    status = 'finished',
                    winner = :winner,
                    finished_at = now()
                where id = :match_id
                """,
                values={"match_id": match_id, "winner": state.winner},
            )

        # notify
        await database.execute(
            query="select pg_notify('test', :match_id)",
            values={"match_id": str(match_id)},
        )

        return True



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
            on blue_mp.number = 0 and m.id = blue_mp.match_id
            left join agents blue_a
            on blue_mp.agent_id = blue_a.id
            join match_players red_mp
            on red_mp.number = 1 and m.id = red_mp.match_id
            left join agents red_a
            on red_mp.agent_id = red_a.id
            where m.id in (select * from my_matches)
            order by is_next_player desc, mt.created_at desc;
            """,
        values={"user_id": user_id},
    )
    match_summaries = []
    for match in matches_r:
        if match["blue_user_id"] is not None:
            blue_user = await users.get_user_by_id(match["blue_user_id"])
            assert blue_user is not None
            blue = blue_user.username
        else:
            blue_user = await users.get_user_by_id(match["blue_agent_user_id"])
            assert blue_user is not None
            blue = f"{blue_user.username}/{match['blue_agent_name']}"

        if match["red_user_id"] is not None:
            red_user = await users.get_user_by_id(match["red_user_id"])
            assert red_user is not None
            red = red_user.username
        else:
            red_user = await users.get_user_by_id(match["red_agent_user_id"])
            assert red_user is not None
            red = f"{red_user.username}/{match['red_agent_name']}"

        match_summaries.append(
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

    return match_summaries


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
            query=tables.matches.select().where(tables.matches.c.id == match_id)
        )
        if match_r is None:
            return None

        players_r = await database.fetch_all(
            query=tables.match_players.select().where(
                tables.match_players.c.match_id == match_id
            )
        )

        turns_r = await database.fetch_all(
            query=sqlalchemy.sql.expression.select(
                [
                    tables.match_turns.c.number,
                    tables.match_turns.c.player,
                    tables.match_turns.c.action,
                    tables.match_turns.c.next_player,
                    tables.match_turns.c.created_at,
                ]
            ).where(tables.match_turns.c.match_id == match_id)
        )

        # todo: sort in sql
        turns_r.sort(key=lambda turn_r: int(turn_r["number"]))

        if turn is None:
            turn = max(turn["number"] for turn in turns_r)

        q = tables.match_turns.select().where(
            (tables.match_turns.c.match_id == match_id)
            & (tables.match_turns.c.number == turn)
        )
        latest_turn_r = await database.fetch_one(query=q)
        assert latest_turn_r is not None

    # TODO: sort in sql
    created_by = await users.get_user_by_id(match_r["created_by"])

    players_r.sort(key=lambda p: int(p["number"]))

    players: list[Player] = []
    for player_r in players_r:
        if player_r["user_id"] is not None:
            user = await users.get_user_by_id(player_r["user_id"])
            assert user is not None
            players.append(user)
        elif player_r["agent_id"] is not None:
            agent = await agents.get_agent_by_id(database, player_r["agent_id"])
            assert agent is not None
            players.append(agent)
        else:
            assert False

    match match_r["game"]:
        case "connect4":
            turns = [
                Turn(
                    number=turn_r["number"],
                    player=turn_r["player"],
                    action=common.deserialize_action("connect4", turn_r["action"])
                    if turn_r["action"] is not None
                    else None,
                    next_player=turn_r["next_player"],
                    created_at=turn_r["created_at"],
                )
                for turn_r in turns_r
            ]

            state = common.deserialize_state(
                "connect4",
                latest_turn_r["next_player"] is None,
                match_r["winner"],
                latest_turn_r["next_player"],
                latest_turn_r["state"],
            )
        case _game as game:
            assert False, f"Unknown game: {game}"

    match = Match(
        id=match_r["id"],
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
