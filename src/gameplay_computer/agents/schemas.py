from typing import Literal
from pydantic import BaseModel, HttpUrl


class AgentDeployment(BaseModel):
    url: HttpUrl
    active: bool
    healthy: bool


class AgentHistory(BaseModel):
    wins: int
    losses: int
    draws: int
    errors: int
