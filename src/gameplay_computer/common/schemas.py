import abc
from typing import Generic, TypeVar

from gameplay_computer.gameplay import BaseAction, BaseState

A = TypeVar("A", bound=BaseAction)
S = TypeVar("S", bound=BaseState)


class ALogic(abc.ABC, Generic[A, S]):
    @staticmethod
    @abc.abstractmethod
    def initial_state() -> S:
        ...

    @staticmethod
    @abc.abstractmethod
    def actions(s: S) -> list[A]:
        ...

    @staticmethod
    @abc.abstractmethod
    def turn(s: S, player: int, action: A) -> None:
        ...
