import datetime
import os
from pydantic import BaseModel

import httpx

from .schemas import User

class ClerkEmailAddress(BaseModel):
    id: str
    email_address: str


class ClerkUser(BaseModel):
    id: str
    username: str
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
    email_addresses: list[ClerkEmailAddress]
    primary_email_address_id: str


# suuuuuuuper shit cache, make better pls
_users_cache: list[ClerkUser] = []
_cache_updated: datetime.datetime | None = None


async def _update_cache(force: bool = False) -> None:
    global _users_cache
    global _cache_updated
    now = datetime.datetime.utcnow()
    if (
        force
        or _cache_updated is None
        or (now - _cache_updated) > datetime.timedelta(minutes=1)
    ):
        api_key = os.environ.get("CLERK_SECRET_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}
        clerk_users = []
        async with httpx.AsyncClient(headers=headers) as client:
            req = await client.get("https://api.clerk.dev/v1/users")
            req.raise_for_status()
            users = req.json()
            for user in users:
                clerk_users.append(ClerkUser(**user))
        _users_cache = clerk_users
        _cache_updated = now


async def _list_clerk_users(force: bool = False) -> list[ClerkUser]:
    await _update_cache(force)
    return _users_cache


async def list_users(force: bool = False) -> list[User]:
    clerk_users = await _list_clerk_users(force)
    return [
        User(
            username=clerk_user.username,
            first_name=clerk_user.first_name,
            last_name=clerk_user.last_name,
            profile_image_url=clerk_user.profile_image_url,
        ) for clerk_user in clerk_users
    ]


async def get_user_by_id(user_id: str, force: bool = False) -> User | None:
    clerk_users = await _list_clerk_users(force)
    for clerk_user in clerk_users:
        if clerk_user.id == user_id:
            return User(
                username=clerk_user.username,
                first_name=clerk_user.first_name,
                last_name=clerk_user.last_name,
                profile_image_url=clerk_user.profile_image_url,
            )
    if not force:
        return await get_user_by_id(user_id, force=True)
    return None


async def get_user_by_username(username: str, force: bool = False) -> User | None:
    clerk_users = await _list_clerk_users(force)
    for clerk_user in clerk_users:
        if clerk_user.username == username:
            return User(
                username=clerk_user.username,
                first_name=clerk_user.first_name,
                last_name=clerk_user.last_name,
                profile_image_url=clerk_user.profile_image_url,
            )
    if not force:
        return await get_user_by_username(username, force=True)
    return None


async def get_user_id_for_username(username: str, force: bool = False) -> str | None:
    clerk_users = await _list_clerk_users(force)
    for clerk_user in clerk_users:
        if clerk_user.username == username:
            return clerk_user.id
    if not force:
        return await get_user_id_for_username(username, force=True)
    return None
