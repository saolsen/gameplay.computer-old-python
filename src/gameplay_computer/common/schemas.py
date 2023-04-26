from typing import Literal

from pydantic import BaseModel

Game = Literal["connect4"]


class BasePlayer(BaseModel):
    kind: Literal["user", "agent"]


class Agent(BasePlayer):
    kind: Literal["agent"] = "agent"
    game: Game
    username: str
    agentname: str
