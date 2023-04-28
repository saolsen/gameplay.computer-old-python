from typing import assert_never

from databases import Database
from fastapi import HTTPException, status

from gameplay_computer import users
from gameplay_computer.common import Game
from gameplay_computer.games.connect4 import State as Connect4State

from . import repo
from .schemas import Action, Match, MatchSummary, Player


async def create_match(
    database: Database,
    created_by_user_id: str,
    game: Game,
    players: list[Player],
) -> int:
    created_by_user = await users.get_user_by_id(created_by_user_id)
    if created_by_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unknown user.",
        )

    created_by_username = created_by_user.username
    created_by_player_indexes = [
        i
        for i, p in enumerate(players)
        if p.kind == "user" and p.username == created_by_username
    ]

    match game:
        case "connect4":
            if len(players) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Connect4 requires exactly 2 players.",
                )
            player1, player2 = players
            if (player1.kind == "user" or player2.kind == "user") and len(
                created_by_player_indexes
            ) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot create a match with users unless you are one of the players.",
                )
            state = Connect4State()
            match_id = await repo.create_match(
                database, created_by_user_id, players, state
            )

            return match_id
        case _game as unknown:
            assert_never(unknown)


async def get_match_by_id(
    database: Database, match_id: int, turn: int | None = None
) -> Match:
    match = await repo.get_match_by_id(database, match_id, turn)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )
    return match


async def list_match_summaries_for_user(
    database: Database, user_id: str
) -> list[MatchSummary]:
    return await repo.list_match_summaries_for_user(database, user_id)


async def take_action(
    database: Database,
    match_id: int,
    player: int,
    action: Action,
    acting_user_id: str | None = None,
    acting_agent_id: int | None = None,
) -> Match:
    assert acting_user_id is not None or acting_agent_id is not None
    assert acting_user_id is None or acting_agent_id is None

    match = await get_match_by_id(database, match_id)

    if match.state.next_player != player:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="It is not player {player}'s turn.",
        )

    if match.state.winner is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The game is over.",
        )

    if player < 0 or player >= len(match.players):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid player {player}.",
        )

    next_player = match.players[match.state.next_player]
    if acting_user_id is not None:
        user = await users.get_user_by_id(acting_user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unknown User",
            )
        if user.username != next_player.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="It is not your turn.",
            )
    else:
        # todo: verify agents
        pass

    if action.game != match.state.game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action for this game.",
        )

    assert action in match.state.actions()
    match.state.turn(player, action)

    added = await repo.create_match_turn(
        database,
        match_id,
        player,
        action,
        match.state,
        len(match.turns),
    )
    if not added:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Turn {len(match.turns)} already exists.",
        )

    match = await get_match_by_id(database, match_id)
    return match
