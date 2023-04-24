import datetime
import os
import httpx

from .schemas import User

# suuuuuuuper shit cache, make better pls
_users_cache: list[User] = []
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
                clerk_users.append(User(**user))
        _users_cache = clerk_users
        _cache_updated = now


async def list_users(force: bool = False) -> list[User]:
    await _update_cache(force)
    return _users_cache


async def get_user_by_id(user_id: str, force: bool = False) -> User | None:
    users = await list_users(force=force)
    for user in users:
        if user.id == user_id:
            return user
    if not force:
        return await get_user_by_id(user_id, force=True)
    return None


async def get_user_by_username(username: str, force: bool = False) -> User | None:
    users = await list_users(force=force)
    for user in users:
        if user.username == username:
            return user
    if not force:
        return await get_user_by_username(username, force=True)
    return None
