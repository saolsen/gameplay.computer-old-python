import json
import os
from collections import namedtuple

from fastapi import HTTPException, Request, status
from jwcrypto import jwk, jwt  # type: ignore

from gameplay_computer import users

AuthUser = namedtuple("AuthUser", ["user_id", "username"])

_key: jwk.JWK | None = None


async def auth(request: Request) -> AuthUser:
    global _key
    if _key is None:
        clerk_jwt_public_key = os.environ.get("CLERK_JWT_PUBLIC_KEY")
        assert clerk_jwt_public_key is not None
        pem = bytes(clerk_jwt_public_key, "utf-8")
        key = jwk.JWK.from_pem(data=pem)
        _key = key
    key = _key
    session = request.cookies.get("__session")
    if not session:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/"},
        )
    try:
        token = jwt.JWT(key=key, jwt=session, expected_type="JWS")
        token.validate(key=key)
        claims = json.loads(token.claims)
        user_id = claims["sub"]
        assert isinstance(user_id, str)
        user = await users.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/"},
            )
        return AuthUser(user_id=user_id, username=user.username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/"},
        ) from e
