from typing import Literal

from pydantic import BaseModel


class Game(BaseModel):
    id: int
    name: Literal["connect4"]

    class Config:
        orm_mode = True


class Agent(BaseModel):
    id: int
    game_id: int
    user_id: str
    agentname: str

    class Config:
        orm_mode = True
