from typing import Literal

from gameplay_computer.common import BasePlayer, Game


class Agent(BasePlayer):
    kind: Literal["agent"] = "agent"
    game: Game
    username: str
    agentname: str
