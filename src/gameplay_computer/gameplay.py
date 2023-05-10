from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

Game = Literal["connect4"]


class User(BaseModel):
    kind: Literal["user"] = "user"
    username: str


class Agent(BaseModel):
    kind: Literal["agent"] = "agent"
    game: Game
    username: str
    agentname: str


Player = Annotated[Union[User, Agent], Field(discrminator="kind")]


class BaseAction(BaseModel):
    game: Game


class BaseState(BaseModel):
    game: Game
    over: bool
    winner: int | None
    next_player: int | None


# Connect4
class Connect4Space(StrEnum):
    EMPTY = " "
    BLUE = "B"
    RED = "R"


Connect4Board = list[list[Connect4Space]]


class Connect4Action(BaseAction):
    game: Literal["connect4"] = "connect4"
    column: int


class Connect4State(BaseState):
    game: Literal["connect4"] = "connect4"
    board: Connect4Board


Action = Annotated[Union[Connect4Action], Field(discrminator="game")]
State = Annotated[Union[Connect4State], Field(discrminator="game")]


class Turn(BaseModel):
    number: int
    player: int | None
    action: Action | None
    next_player: int | None


class Match(BaseModel):
    id: int
    players: list[Player]
    turns: list[Turn]
    turn: int
    state: State
