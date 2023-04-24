from datetime import datetime
from typing import Any, Literal

# from fastapi import Form
from pydantic import BaseModel

from ..common.schemas import Agent, Game
from ..users.schemas import User


class CreateMatch(BaseModel):
    game: Game
    created_by: User
    players: list[User | Agent]


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
    id: int
    game: Game
    status: Literal["in_progress", "finished"]
    winner: int | None
    created_by: User
    created_at: datetime
    finished_at: datetime | None
    # Summaries of related data
    players: dict[int, User | Agent]
    turns: list[Turn]
    # Data from a specific turn, usually the latest one.
    turn: int
    next_player: int | None
    state: Any
    updated_at: datetime


class MatchSummary(BaseModel):
    id: int
    game_name: str
    blue: str
    red: str
    status: Literal["in_progress", "finished"]
    winner: int | None
    last_turn_at: datetime
    next_player: int | None
    is_next_player: bool
