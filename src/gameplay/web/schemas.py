from typing import Literal

from pydantic import BaseModel
from fastapi import Form


class WidgetBase(BaseModel):
    name: str
    is_active: bool = True


class WidgetCreate(WidgetBase):
    pass


class Widget(WidgetBase):
    id: int


class TurnBase(BaseModel):
    player: int
    column: int


class TurnCreate(TurnBase):
    @classmethod
    def as_form(cls, player: int = Form(...), column: int = Form(...)):
        return cls(player=player, column=column)


class Turn(TurnBase):
    id: int
    number: int
    match_id: int


class MatchBase(BaseModel):
    game: Literal["connect4"]
    opponent: Literal["ai"]


class MatchCreate(MatchBase):
    pass


class Match(MatchBase):
    id: int
    state: tuple[
        list[int],
        list[int],
        list[int],
        list[int],
        list[int],
        list[int],
        list[int],
    ]
    turn: int
    next_player: int
    turns: list[Turn]
