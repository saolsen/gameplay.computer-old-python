import datetime
import random
import httpx
import sqlalchemy
import os
import json
from typing import assert_never

from databases import Database

from .. import connect4

# from .schemas import Match, MatchCreate, Turn, TurnCreate
from .schemas import (
    MatchCreate,
    TurnSummaryRecord,
    MatchSummaryRecord,
    GameBase,
    GameRecord,
    ClerkUserRecord,
    PlayerRecord,
    Match,
    Turn,
    Player,
    MatchRecord,
    TurnRecord,
    TurnCreate,
)
from . import tables


# todo: maybe a seperation between data access stuff like this
# and more "servicery stuff"
async def get_game_record(database: Database, name: str) -> GameRecord | None:
    game = await database.fetch_one(
        query=tables.games.select().where(tables.games.c.name == name)
    )
    if game:
        return GameRecord.from_orm(game)
    return None


# suuuuuuuper shit cache, make better pls
_users_cache = []
_cache_updated: datetime.datetime | None = None


async def update_cache(force=False) -> None:
    global _users_cache
    global _cache_updated
    now = datetime.datetime.utcnow()
    if (
        force
        or _cache_updated is None
        or (now - _cache_updated) > datetime.timedelta(minutes=1)
    ):
        api_key = os.environ.get("CLERK_SECRET_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}
        clerk_users = []
        async with httpx.AsyncClient(headers=headers) as client:
            users = await client.get("https://api.clerk.dev/v1/users")
            users.raise_for_status()
            users = users.json()
            for user in users:
                clerk_users.append(ClerkUserRecord(**user))
        _users_cache = clerk_users
        _cache_updated = now


async def get_clerk_users(force=False) -> list[ClerkUserRecord]:
    await update_cache(force)
    return _users_cache


async def get_clerk_user_by_id(user_id: str, force=False) -> ClerkUserRecord:
    users = await get_clerk_users(force=force)
    for user in users:
        if user.id == user_id:
            return user
    # bust cache and try again
    if not force:
        return await get_clerk_user_by_id(user_id, force=True)


async def get_clerk_user_username(username: str, force=False) -> ClerkUserRecord:
    users = await get_clerk_users(force=force)
    for user in users:
        if user.username == username:
            return user
    if not force:
        return await get_clerk_user_username(username, force=True)


async def get_match_record(database: Database, match_id: int) -> MatchRecord | None:
    match = await database.fetch_one(
        query=tables.matches.select().where(tables.matches.c.id == match_id)
    )
    if match:
        return MatchRecord.from_orm(match)
    return None


async def get_matches(database: Database, user_id: str) -> list[MatchSummaryRecord]:
    matches = await database.fetch_all(
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
            g.name as game_name,
            blue_mp.user_id as blue_user_id, blue_a.name as blue_agent_name, blue_a.user_id as blue_agent_user_id,
            red_mp.user_id as red_user_id, red_a.name as red_agent_name, red_a.user_id as red_agent_user_id,
            m.status,
            m.next_player,
            m.winner,
            m.updated_at,
            coalesce(next_mp.user_id = :user_id, false) as is_next_player
        from matches m
        join games g on m.game_id = g.id
        left join match_players next_mp on m.next_player = next_mp.number and m.id = next_mp.match_id
        join match_players blue_mp on blue_mp.number = 1 and m.id = blue_mp.match_id
        left join agents blue_a on blue_mp.agent_id = blue_a.id
        join match_players red_mp on red_mp.number = 2 and m.id = red_mp.match_id
        left join agents red_a on red_mp.agent_id = red_a.id
        where m.id in (select * from my_matches)
        order by is_next_player desc, m.updated_at desc;
        """,
        values={"user_id": user_id},
    )
    match_summaries = []
    for match in matches:
        blue = None
        if match.blue_user_id is not None:
            blue_user = await get_clerk_user_by_id(match.blue_user_id)
            blue = blue_user.username
        else:
            blue_user = await get_clerk_user_by_id(match.blue_agent_user_id)
            blue = f"{blue_user.username}/{match.blue_agent_name}"

        red = None
        if match.red_user_id is not None:
            red_user = await get_clerk_user_by_id(match.red_user_id)
            red = red_user.username
        else:
            red_user = await get_clerk_user_by_id(match.red_agent_user_id)
            red = f"{red_user.username}/{match.red_agent_name}"

        match_summaries.append(
            MatchSummaryRecord(
                id=match.id,
                game_name=match.game_name,
                blue=blue,
                red=red,
                status=match.status,
                winner=match.winner,
                updated_at=match.updated_at,
                next_player=match.next_player,
                is_next_player=match.is_next_player,
            )
        )

    return match_summaries


async def create_match(
    created_by: str, database: Database, new_match: MatchCreate
) -> int:
    async with database.transaction():
        # game
        game_record = await get_game_record(database, new_match.game)
        if not game_record:
            raise ValueError(f"Game {new_match.game} not found")

        clerk_users = await get_clerk_users()
        created_by_username = None
        for clerk_user in clerk_users:
            if clerk_user.id == created_by:
                created_by_username = clerk_user.username
                break
        assert created_by_username is not None

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

        # players

        new_match_players = [
            {"type": new_match.player_type_1, "name": new_match.player_name_1},
            {"type": new_match.player_type_2, "name": new_match.player_name_2},
        ]

        players = []
        for new_match_player in new_match_players:
            type = new_match_player["type"]
            name = new_match_player["name"]
            match type:
                case "me" | "user":
                    clerk_id = None
                    for clerk_user in clerk_users:
                        if clerk_user.username == name:
                            clerk_id = clerk_user.id
                            break
                    assert clerk_id is not None
                    players.append(("user", clerk_id))
                case "agent":
                    username, agentname = name.split("/")
                    clerk_id = None
                    for clerk_user in clerk_users:
                        if clerk_user.username == username:
                            clerk_id = clerk_user.id
                            break
                    assert clerk_id is not None

                    agent = await database.fetch_one(
                        query=tables.agents.select().where(
                            tables.agents.c.user_id == clerk_id
                            and tables.agents.c.name == agentname
                        )
                    )
                    assert agent is not None
                    assert "id" in agent
                    players.append(("agent", agent["id"]))

                case _ as unknown:
                    assert_never(unknown)

        assert game_record.name == "connect4"
        state = connect4.State()

        create_match = tables.matches.insert().values(
            game_id=game_record.id,
            status="new",
            turn=0,
            next_player=1,
            # todo: created by should be the user making the request
            created_by=created_by,
            created_at=sqlalchemy.func.now(),
            updated_at=sqlalchemy.func.now(),
            finished_at=None,
        )
        match_id = await database.execute(query=create_match)

        for i, player in enumerate(players):
            user_id = None
            agent_id = None
            type, id = player
            match type:
                case "user":
                    user_id = id
                case "agent":
                    agent_id = id
                case _ as unknown:
                    assert_never(unknown)
            await database.execute(
                query=tables.match_players.insert().values(
                    match_id=match_id,
                    number=i + 1,
                    user_id=user_id,
                    agent_id=agent_id,
                )
            )

        await database.execute(
            query=tables.match_turns.insert().values(
                match_id=match_id,
                number=0,
                player=None,
                state=[[0] * 6 for _ in range(7)],
                next_player=1,
                created_at=sqlalchemy.func.now(),
            )
        )

    return match_id


async def get_match(
    database: Database, match_id: int, turn: int | None = None
) -> Match | None:
    async with database.transaction():
        match = await get_match_record(database, match_id)

        mr = await database.fetch_one(
            tables.matches.select().where(tables.matches.c.id == match_id)
        )
        if mr is None:
            return None
        match_record = MatchRecord.from_orm(mr)

        prs = await database.fetch_all(
            tables.match_players.select().where(
                tables.match_players.c.match_id == match_id
            )
        )
        player_records = [PlayerRecord.from_orm(p) for p in prs]

        # hack
        # todo: we have to join this one, ugh
        players = {}
        for p in player_records:
            username = None
            agentname = None
            user_id = p.user_id
            if user_id is not None:
                user = await get_clerk_user_by_id(user_id)
                username = user.username
            elif p.agent_id is not None:
                agent = await database.fetch_one(
                    tables.agents.select().where(tables.agents.c.id == p.agent_id)
                )
                user = await get_clerk_user_by_id(agent.user_id)
                agentname = f"{user.username}/{agent.name}"

            players[p.number] = Player(
                number=p.number,
                username=username,
                agentname=agentname,
            )

        tss = await database.fetch_all(
            # todo: how do I pick the columns to query?
            tables.match_turns.select().where(
                tables.match_turns.c.match_id == match_id,
            )
        )
        turn_summarys = [TurnSummaryRecord.from_orm(ts) for ts in tss]

        if turn is None:
            turn = max((ts.number for ts in turn_summarys))

        tr = await database.fetch_one(
            tables.match_turns.select().where(
                tables.match_turns.c.match_id == match_id,
                tables.match_turns.c.number == turn,
            )
        )
        assert tr is not None
        view_turn = TurnRecord.from_orm(tr)
        view_turn.state = json.loads(view_turn.state)

        turns = []
        for t in sorted(turn_summarys, key=lambda x: x.number):
            turns.append(
                Turn(
                    number=t.number,
                    player=t.player,
                    action=t.action,
                )
            )

        return Match(
            id=match_record.id,
            # todo: game_name join to game
            game_name="connect4",
            status=match_record.status,
            winner=match_record.winner,
            players=players,
            turns=turns,
            turn=turn,
            next_player=view_turn.next_player,
            state=view_turn.state,
        )


async def take_ai_turn(
    database: Database,
    match_id: int,
    agent_name: str,
) -> None:
    async with database.transaction():
        match = await get_match(database, match_id)
        assert match is not None
        assert match.next_player is not None
        assert match.players[match.next_player].agentname == agent_name

        username, agentname = agent_name.split("/")
        clerk_user = await get_clerk_user_username(username)

        agent = await database.fetch_one(
            query=tables.agents.select().where(
                tables.agents.c.user_id == clerk_user.id
                and tables.agents.c.name == agentname
            )
        )
        assert agent is not None
        assert "id" in agent
        agent_id = agent["id"]

        # Assuming connect4 and random_agent
        board = match.state
        state = connect4.State(
            board=match.state, next_player=connect4.Player(match.next_player)
        )
        actions = state.actions()

        column = random.choice(actions)
        await take_turn(
            database,
            match_id,
            TurnCreate(column=column, player=match.next_player),
            agent_id=agent_id,
        )


async def take_turn(
    database: Database,
    match_id: int,
    new_turn: TurnCreate,
    user_id: str | None = None,
    agent_id: int | None = None,
) -> Match:
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
            clerk_user = await get_clerk_user_by_id(user_id)
            assert next_player.username == clerk_user.username
        elif agent_id is not None:
            # todo
            pass

        # Assuming connect4
        board = match.state
        state = connect4.State(
            board=match.state, next_player=connect4.Player(match.next_player)
        )
        assert new_turn.column in state.actions()

        result = state.turn(connect4.Player(new_turn.player), new_turn.column)
        next_player = None
        match result:
            case connect4.Player():
                await database.execute(
                    query=tables.matches.update()
                    .where(tables.matches.c.id == match_id)
                    .values(
                        status="finished",
                        turn=match.turn + 1,
                        next_player=None,
                        winner=result.value,
                        updated_at=sqlalchemy.func.now(),
                        finished_at=sqlalchemy.func.now(),
                    )
                )
            case "draw":
                await database.execute(
                    query=tables.matches.update()
                    .where(tables.matches.c.id == match_id)
                    .values(
                        status="finished",
                        turn=match.turn + 1,
                        next_player=None,
                        winner=None,
                        updated_at=sqlalchemy.func.now(),
                        finished_at=sqlalchemy.func.now(),
                    )
                )
            case None:
                next_player = state.next_player.value
                await database.execute(
                    query=tables.matches.update()
                    .where(tables.matches.c.id == match_id)
                    .values(
                        status="in_progress",
                        turn=match.turn + 1,
                        next_player=next_player,
                        updated_at=sqlalchemy.func.now(),
                    )
                )

        insert_turn = tables.match_turns.insert().values(
            match_id=match_id,
            number=match.turn + 1,
            player=new_turn.player,
            action=new_turn.column,
            state=state.board,
            next_player=next_player,
            created_at=sqlalchemy.func.now(),
        )
        await database.execute(query=insert_turn)

        # notify
        await database.execute(
            query="select pg_notify('test', :match_id)",
            values={"match_id": str(match_id)},
        )

        return await get_match(database, match_id)

    # async def take_turn(database: Database, match_id: int, new_turn: TurnCreate) -> Match:
    #     async with database.transaction():
    #         match = await get_match(database, match_id)
    #         assert match is not None

    #         state = connect4.State(
    #             board=match.state, next_player=connect4.Player(match.next_player)
    #         )
    #         assert new_turn.column in state.actions()

    #         result = state.turn(connect4.Player(new_turn.player), new_turn.column)
    #         winner: int | None
    #         match result:
    #             case connect4.Player():
    #                 winner = result.value
    #             case "draw":
    #                 winner = 0
    #             case None:
    #                 winner = None

    #         insert_turn = turns.insert().values(
    #             number=match.turn + 1,
    #             match_id=match_id,
    #             player=new_turn.player,
    #             column=new_turn.column,
    #         )
    #         update_match = (
    #             matches.update()
    #             .where(matches.c.id == match_id)
    #             .values(
    #                 state=state.board,
    #                 turn=match.turn + 1,
    #                 next_player=state.next_player.value,
    #                 winner=winner,
    #             )
    #         )
    #         await database.execute(query=insert_turn)
    #         await database.execute(query=update_match)
    #         match = await get_match(database, match_id)

    #     return match

    # insert_query = matches.insert().values(
    #     game=new_match.game,
    #     opponent=new_match.opponent,
    #     state=(
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 0],
    #     ),
    #     turn=0,
    #     next_player=1,
    # )
    # async with database.transaction():
    #     match_id = await database.execute(query=insert_query)
    #     match = await get_match(database, match_id)
    #     return match


# def check(match: Match) -> tuple[str, int | None] | None:
#     """
#     See if anybody won yet.
#     Just check in a dumb way for now, each possibility
#     """
#     # Check rows
#     for row in range(0, 6):
#         for col in range(0, 4):
#             if (
#                 match.state[col][row] != 0
#                 and match.state[col][row]
#                 == match.state[col + 1][row]
#                 == match.state[col + 2][row]
#                 == match.state[col + 3][row]
#             ):
#                 return "WIN", match.state[col][row]
#     # Check cols
#     for col in range(0, 7):
#         for row in range(0, 3):
#             if (
#                 match.state[col][row] != 0
#                 and match.state[col][row]
#                 == match.state[col][row + 1]
#                 == match.state[col][row + 2]
#                 == match.state[col][row + 3]
#             ):
#                 return "WIN", match.state[col][row]
#     # Check diag up
#     for col in range(0, 4):
#         for row in range(0, 3):
#             if (
#                 match.state[col][row] != 0
#                 and match.state[col][row]
#                 == match.state[col + 1][row + 1]
#                 == match.state[col + 2][row + 2]
#                 == match.state[col + 3][row + 3]
#             ):
#                 return ("WIN", match.state[col][row])

#     # Check diag down
#     for col in range(0, 4):
#         for row in range(3, 6):
#             if (
#                 match.state[col][row] != 0
#                 and match.state[col][row]
#                 == match.state[col + 1][row - 1]
#                 == match.state[col + 2][row - 2]
#                 == match.state[col + 3][row - 3]
#             ):
#                 return "WIN", match.state[col][row]

#     # Check draw
#     for col in range(0, 7):
#         if match.state[col][5] == 0:
#             # There are still moves left
#             return None

#     return "DRAW", None


# async def create_match(database: Database, new_match: MatchCreate) -> Match:
#     insert_query = matches.insert().values(
#         game=new_match.game,
#         opponent=new_match.opponent,
#         state=(
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#             [0, 0, 0, 0, 0, 0],
#         ),
#         turn=0,
#         next_player=1,
#     )
#     async with database.transaction():
#         match_id = await database.execute(query=insert_query)
#         match = await get_match(database, match_id)
#         return match


# async def get_match(database: Database, match_id: int) -> Match:
#     match = await database.fetch_one(
#         query=matches.select().where(matches.c.id == match_id)
#     )
#     match_turns = await database.fetch_all(
#         query=turns.select().where(turns.c.match_id == match_id)
#     )

#     assert match is not None
#     return Match(**dict(match), turns=[Turn(**dict(t)) for t in match_turns])


# async def take_ai_turn(database: Database, match_id: int) -> None:
#     async with database.transaction():
#         match = await get_match(database, match_id)
#         if match.winner is not None:
#             return
#         columns = [i for i in range(7) if match.state[i][5] == 0]

#         column = random.choice(columns)
#         await take_turn(database, match_id, TurnCreate(column=column, player=2))
#         await database.execute(
#             query="select pg_notify('test', :match_id)",
#             values={"match_id": str(match_id)},
#         )


# async def take_turn(database: Database, match_id: int, new_turn: TurnCreate) -> Match:
#     async with database.transaction():
#         match = await get_match(database, match_id)
#         assert match is not None

#         state = connect4.State(
#             board=match.state, next_player=connect4.Player(match.next_player)
#         )
#         assert new_turn.column in state.actions()

#         result = state.turn(connect4.Player(new_turn.player), new_turn.column)
#         winner: int | None
#         match result:
#             case connect4.Player():
#                 winner = result.value
#             case "draw":
#                 winner = 0
#             case None:
#                 winner = None

#         insert_turn = turns.insert().values(
#             number=match.turn + 1,
#             match_id=match_id,
#             player=new_turn.player,
#             column=new_turn.column,
#         )
#         update_match = (
#             matches.update()
#             .where(matches.c.id == match_id)
#             .values(
#                 state=state.board,
#                 turn=match.turn + 1,
#                 next_player=state.next_player.value,
#                 winner=winner,
#             )
#         )
#         await database.execute(query=insert_turn)
#         await database.execute(query=update_match)
#         match = await get_match(database, match_id)

#     return match


# async def get_matches(database: Database, user_id: int) -> list[Match]:
#     # todo: filter by user_id
#     # user_matches = await database.fetch_all(matches.select())
#     # return [Match(**dict(m), turns=[]) for m in user_matches]
#     return []


# # Service stuff
# # Users
# # Games
# # Matches
# # Agents


# # async def get_user_id(database: Database, clerk_user_id: str) -> int:
# #     print(clerk_user_id)
# #     user = await database.fetch_one(
# #         query=tables.users.select().where(tables.users.c.clerk_user_id == clerk_user_id)
# #     )
# #     print(user)
# #     if user is None:
# #         insert_query = tables.users.insert().values(clerk_user_id=clerk_user_id)
# #         user_id = await database.execute(query=insert_query)
# #         print(user_id)
# #         return user_id
# #     return user["id"]
