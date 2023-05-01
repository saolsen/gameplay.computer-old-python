from typing import Literal, Self

from fastapi import Form
from pydantic import BaseModel

from gameplay_computer.common import Game
from gameplay_computer.matches import Action, State, Match


class MatchCreate(BaseModel):
    game: Literal["connect4"]
    player_type_1: Literal["me", "user", "agent"]
    player_name_1: str
    player_type_2: Literal["me", "user", "agent"]
    player_name_2: str

    @classmethod
    def as_form(
        cls,
        game: Literal["connect4"] = Form(...),
        player_type_1: Literal["me", "user", "agent"] = Form(...),
        player_name_1: str = Form(...),
        player_type_2: Literal["me", "user", "agent"] = Form(...),
        player_name_2: str = Form(...),
    ) -> Self:
        return cls(
            game=game,
            player_type_1=player_type_1,
            player_name_1=player_name_1,
            player_type_2=player_type_2,
            player_name_2=player_name_2,
        )


class TurnCreate(BaseModel):
    player: int
    # note: this will have to get complicated to support multiple games
    # maybe we just have a different api for each game
    # games/connect4/matches/0/turns
    # that would make it a lot easeir I think
    column: int

    @classmethod
    def as_form(cls, player: int = Form(...), column: int = Form(...)) -> Self:
        return cls(player=player, column=column)

# Schemas for what we post to the agents.
# These will probably go in an external library.
class PostPlayer(BaseModel):
    kind: Literal["user", "agent"]
    username: str
    agentname: str | None

class PostTurn(BaseModel):
    number: int
    player: int | None
    action: Action | None
    next_player: int | None

class PostMatch(BaseModel):
    id: int
    game: Game
    players: list[PostPlayer]
    turns: list[PostTurn]
    state: State

    @classmethod
    def from_match(cls, match: Match, match_id: int) -> Self:
        post_game = match.state.game
        post_players = [
            PostPlayer(
                kind=player.kind,
                username=player.username,
                agentname=player.agentname if player.kind == "agent" else None
            )
            for player in match.players
        ]
        post_turns = [
            PostTurn(
                number=turn.number,
                player=turn.player,
                action=turn.action,
                next_player=turn.next_player,
            ) for turn in match.turns
        ]
        post_match = cls(
            id=match_id,
            game=post_game,
            players=post_players,
            turns=post_turns,
            state=match.state,
        )
        return post_match
