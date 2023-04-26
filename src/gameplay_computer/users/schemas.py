from pydantic import BaseModel


class User(BaseModel):
    username: str
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
