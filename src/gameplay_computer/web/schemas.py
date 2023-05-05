from typing import Literal, Self

from fastapi import Form
from pydantic import BaseModel, HttpUrl


class MatchCreate(BaseModel):
    game: Literal["connect4"]
    player_type_1: Literal["me", "user", "agent"]
    player_name_1: str
    player_type_2: Literal["me", "user", "agent"]
    player_name_2: str

    @classmethod
    def as_form(
        cls,
        game: Literal["connect4"] = Form(...),
        player_type_1: Literal["me", "user", "agent"] = Form(...),
        player_name_1: str = Form(...),
        player_type_2: Literal["me", "user", "agent"] = Form(...),
        player_name_2: str = Form(...),
    ) -> Self:
        return cls(
            game=game,
            player_type_1=player_type_1,
            player_name_1=player_name_1,
            player_type_2=player_type_2,
            player_name_2=player_name_2,
        )


class TurnCreate(BaseModel):
    player: int
    # note: this will have to get complicated to support multiple games
    # maybe we just have a different api for each game
    # games/connect4/matches/0/turns
    # that would make it a lot easeir I think
    column: int

    @classmethod
    def as_form(cls, player: int = Form(...), column: int = Form(...)) -> Self:
        return cls(player=player, column=column)


class AgentCreate(BaseModel):
    game: Literal["connect4"]
    agentname: str
    url: HttpUrl

    @classmethod
    def as_form(
        cls,
        game: Literal["connect4"] = Form(...),
        agentname: str = Form(...),
        url: HttpUrl = Form(...),
    ) -> Self:
        return cls(game=game, agentname=agentname, url=url)
