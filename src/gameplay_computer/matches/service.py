from typing import assert_never

from databases import Database
from fastapi import HTTPException, status

from gameplay_computer import users
from gameplay_computer.gameplay import Action, Agent, Game, Match, Player, User
from gameplay_computer.games.connect4 import Connect4Logic

from . import repo
from .schemas import MatchSummary


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
                    detail="You cannot create a match with users unless you are one"
                    + "of the players.",
                )
            state = Connect4Logic.initial_state()
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
    match: Match,
    player: int,
    action: Action,
    actor: User | Agent,
) -> Match:
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

    if match.turn != match.turns[-1].number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can not overwrite a turn.",
        )

    if player < 0 or player >= len(match.players):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid player {player}.",
        )

    next_player = match.players[match.state.next_player]
    if next_player.kind == "user":
        if not isinstance(actor, User):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unknown User",
            )
        if next_player.username != actor.username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="It is not your turn.",
            )
    elif next_player.kind == "agent":
        if not isinstance(actor, Agent):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unknown Agent",
            )
        if (
            next_player.username != actor.username
            or next_player.agentname != actor.agentname
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="It is not your turn.",
            )
    else:
        assert_never(next_player.kind)

    if action.game != match.state.game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action for this game.",
        )

    assert action in Connect4Logic.actions(match.state)
    Connect4Logic.turn(match.state, player, action)

    added = await repo.create_match_turn(
        database,
        match.id,
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

    match = await get_match_by_id(database, match.id)
    return match
