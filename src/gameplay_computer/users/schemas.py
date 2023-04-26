from typing import Literal
from pydantic import BaseModel

from gameplay_computer.common.schemas import BasePlayer

class User(BasePlayer):
    kind: Literal["user"] = "user"
    username: str
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
