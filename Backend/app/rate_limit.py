import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address)

GUEST_LIMIT = "30/minute"
AUTHENTICATED_LIMIT = "60/minute"


def _has_valid_jwt(request: Request) -> bool:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return False
    token = auth_header[7:].strip()
    try:
        jwt.decode(token, key=settings.jwt_secret, algorithms=["HS256"], audience="fastapi-users:auth")
        return True
    except jwt.PyJWTError:
        return False


def tiered_rate_limit(route):
    """Applies the guest/authenticated tiering described above to a route function."""
    route = limiter.limit(AUTHENTICATED_LIMIT)(route)
    route = limiter.limit(GUEST_LIMIT, exempt_when=_has_valid_jwt)(route)
    return route
