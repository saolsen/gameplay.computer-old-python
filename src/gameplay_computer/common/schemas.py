from typing import Literal

from pydantic import BaseModel

class BasePlayer(BaseModel):
    kind: Literal["user", "agent"]

class Game(BaseModel):
    id: int
    name: Literal["connect4"]

    class Config:
        orm_mode = True


class Agent(BasePlayer):
    kind: Literal["agent"] = "agent"
    game: str
    username: str
    agentname: str