from datetime import datetime
from typing import Literal


from pydantic import BaseModel
from gameplay_computer.gameplay import Game


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
