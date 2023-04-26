from datetime import datetime
from typing import Annotated, Any, Literal, Union

# from fastapi import Form
from pydantic import BaseModel, Field

from gameplay_computer.games.connect4 import Action as Connect4Action
from gameplay_computer.games.connect4 import State as Connect4State

from ..common.schemas import Agent, Game
from ..users.schemas import User

Player = Annotated[Union[User, Agent], Field(discrminator="kind")]

Action = Annotated[Union[Connect4Action], Field(discrminator="game")]
State = Annotated[Union[Connect4State], Field(discrminator="game")]


class CreateMatch(BaseModel):
    created_by: User
    players: list[Player]
    state: State


class CreateTurn(BaseModel):
    player: int
    action: Any
    state: Any
    next_player: int | None
    winner: int | None


class Turn(BaseModel):
    number: int
    player: int | None
    action: Any | None
    next_player: int | None
    created_at: datetime

    class Config:
        orm_mode = True


class Match(BaseModel):
    status: Literal["in_progress", "finished"]
    created_by: User
    created_at: datetime
    finished_at: datetime | None

    players: dict[int, Player]
    turns: list[Turn]

    turn: int
    updated_at: datetime
    state: State


class MatchSummary(BaseModel):
    id: int
    game_name: Game
    blue: str
    red: str
    status: Literal["in_progress", "finished"]
    winner: int | None
    last_turn_at: datetime
    next_player: int | None
    is_next_player: bool
