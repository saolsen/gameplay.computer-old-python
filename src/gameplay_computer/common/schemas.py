import abc
from typing import Any, Generic, Literal, Self, TypeVar

from pydantic import BaseModel, Json

Game = Literal["connect4"]

T = TypeVar("T", bound=Json[Any])


class BaseAction(BaseModel, abc.ABC, Generic[T]):
    game: Game

    @classmethod
    @abc.abstractmethod
    def deserialize(cls, t: T) -> Self:
        ...

    @abc.abstractmethod
    def serialize(self) -> T:
        ...


A = TypeVar("A", bound=BaseAction[Json[Any]])
S = TypeVar("S", bound=Json[Any])


class BaseState(BaseModel, abc.ABC, Generic[A, S]):
    game: Game
    over: bool
    winner: int | None
    next_player: int | None

    @classmethod
    @abc.abstractmethod
    def deserialize(
        cls, over: bool, winner: int | None, next_player: int | None, s: S
    ) -> Self:
        ...

    @abc.abstractmethod
    def serialize(self) -> S:
        ...

    @abc.abstractmethod
    def actions(self) -> list[A]:
        ...

    @abc.abstractmethod
    def turn(self, player: int, action: T) -> None:
        ...


class BasePlayer(BaseModel):
    kind: Literal["user", "agent"]
