from typing import Literal
from pydantic import BaseModel, HttpUrl

from gameplay_computer.common import BasePlayer, Game


class Agent(BasePlayer):
    kind: Literal["agent"] = "agent"
    game: Game
    username: str
    agentname: str

class AgentDeployment(BaseModel):
    url: HttpUrl
    active: bool
