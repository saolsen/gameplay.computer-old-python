# pylint: disable=too-few-public-methods
from datetime import date
from typing import Optional, NewType
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateMatch:
    pass


@dataclass(frozen=True, slots=True)
class DeleteMatch:
    pass


Command = CreateMatch | DeleteMatch
