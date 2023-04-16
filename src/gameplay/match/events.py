import enum
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchCreated:
    match_id: int


@dataclass(frozen=True, slots=True)
class MatchUpdated:
    match_id: int


@dataclass(frozen=True, slots=True)
class MatchOver:
    match_id: int
    winner: int


Event = MatchCreated | MatchUpdated | MatchOver
