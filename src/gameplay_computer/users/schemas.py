from typing import Literal

from gameplay_computer.gameplay import User


class FullUser(User):
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
