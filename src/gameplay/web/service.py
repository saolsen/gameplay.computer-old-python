import random
import httpx
import sqlalchemy
import os
import json

from databases import Database

from .. import connect4

# from .schemas import Match, MatchCreate, Turn, TurnCreate
from .schemas import (
    MatchCreate,
    TurnSummaryRecord,
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


async def get_clerk_users() -> list[ClerkUserRecord]:
    clerk_users = []

    # todo: make the client in init and pass in
    api_key = os.environ.get("CLERK_SECRET_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(headers=headers) as client:
        users = await client.get("https://api.clerk.dev/v1/users")
        users.raise_for_status()
        users = users.json()
        for user in users:
            clerk_users.append(ClerkUserRecord(**user))
    return clerk_users


async def get_match_record(database: Database, match_id: int) -> MatchRecord | None:
    match = await database.fetch_one(
        query=tables.matches.select().where(tables.matches.c.id == match_id)
    )
    if match:
        return MatchRecord.from_orm(match)
    return None


async def create_match(database: Database, new_match: MatchCreate) -> int:
    async with database.transaction():
        # game
        game_record = await get_game_record(database, new_match.game)
        if not game_record:
            raise ValueError(f"Game {new_match.game} not found")

        players = []

        # todo: get_clerk_user_by_username
        clerk_users = await get_clerk_users()
        for player_username in new_match.players:
            clerk_id = None
            for clerk_user in clerk_users:
                if clerk_user.username == player_username:
                    clerk_id = clerk_user.id
                break
            assert clerk_id is not None

            players.append(clerk_id)

        assert game_record.name == "connect4"
        state = connect4.State()

        create_match = tables.matches.insert().values(
            game_id=game_record.id,
            status="new",
            # todo: created by should be the user making the request
            created_by=players[0],
            created_at=sqlalchemy.func.now(),
            updated_at=sqlalchemy.func.now(),
            finished_at=None,
        )
        match_id = await database.execute(query=create_match)

        for i, player_id in enumerate(players):
            await database.execute(
                query=tables.match_players.insert().values(
                    match_id=match_id,
                    number=i + 1,
                    user_id=player_id,
                    agent_id=None,
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
            players[p.number] = Player(
                number=p.number,
                username="steve",
                agentname=None,
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
        for t in sorted(turns, key=lambda x: x.number):
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


async def take_turn(database: Database, match_id: int, new_turn: TurnCreate) -> Match:
    async with database.transaction():
        match = await get_match(database, match_id)
        assert match is not None

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
                        winner=result.value,
                        finished_at=sqlalchemy.func.now(),
                    )
                )
            case "draw":
                await database.execute(
                    query=tables.matches.update()
                    .where(tables.matches.c.id == match_id)
                    .values(
                        status="finished",
                        winner=None,
                        finished_at=sqlalchemy.func.now(),
                    )
                )
            case None:
                next_player = state.next_player.value

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
