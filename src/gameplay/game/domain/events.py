from dataclasses import dataclass


class Event:
    pass


@dataclass(frozen=True, slots=True)
class GameOver(Event):
    winner: int
