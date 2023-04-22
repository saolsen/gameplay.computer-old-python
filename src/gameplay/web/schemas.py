from typing import Literal, Self, Any
from datetime import datetime

from fastapi import Form
from pydantic import BaseModel

# Conventions
# FooRecord is the record with all the database fields.
# Foo is the API type that would get returned.
# Database ids are not usually exposed to the API.


class ClerkEmailAddressRecord(BaseModel):
    id: str
    email_address: str


class ClerkUserRecord(BaseModel):
    id: str
    username: str
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
    email_addresses: list[ClerkEmailAddressRecord]
    primary_email_address_id: str


class GameBase(BaseModel):
    name: str


class GameRecord(GameBase):
    id: int

    class Config:
        orm_mode = True


class MatchCreate(BaseModel):
    game: Literal["connect4"]
    players: list[str]

    @classmethod
    def as_form(
        cls, game: Literal["connect4"] = Form(...), players: list[str] = Form(...)
    ) -> Self:
        return cls(game=game, players=players)


class MatchRecord(BaseModel):
    id: int
    game_id: int
    status: Literal["new", "in_progress", "finished"]
    winner: int | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    class Config:
        orm_mode = True


class TurnSummaryRecord(BaseModel):
    number: int
    player: int | None
    action: Any | None
    next_player: int | None

    class Config:
        orm_mode = True


class TurnRecord(TurnSummaryRecord):
    state: Any
    created_at: datetime


class PlayerRecord(BaseModel):
    number: int
    user_id: str | None
    agent_id: int | None

    class Config:
        orm_mode = True


# The view models have the basic names so they look good in docs.


class Player(BaseModel):
    number: int
    username: str | None
    agentname: str | None


class Turn(BaseModel):
    number: int
    player: int
    action: Any


class Match(BaseModel):
    id: int
    game_name: str
    status: Literal["new", "in_progress", "finished"]
    winner: int | None
    players: dict[int, Player]
    turns: list[Turn]
    # View of a specific turn, usually the latest one.
    turn: int
    next_player: int | None
    state: Any


# class WidgetBase(BaseModel):
#     name: str
#     is_active: bool = True


# class WidgetCreate(WidgetBase):
#     pass


# class Widget(WidgetBase):
#     id: int


# class TurnBase(BaseModel):
#     player: int
#     column: int


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


# class Turn(TurnBase):
#     id: int
#     number: int
#     match_id: int


# class Match(MatchBase):
#     id: int
#     state: tuple[
#         list[int],
#         list[int],
#         list[int],
#         list[int],
#         list[int],
#         list[int],
#         list[int],
#     ]
#     turn: int
#     next_player: int
#     turns: list[Turn]
#     winner: int | None
