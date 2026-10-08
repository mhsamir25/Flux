"""Creates the JWT authentication backend used by fastapi-users.
- BearerTransport defines the endpoint where clients send credentials to receive a token.
- get_jwt_strategy builds a JWTStrategy that signs tokens with the app secret and sets expiration.
- AuthenticationBackend combines transport + strategy so fastapi-users can verify tokens.
"""
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy

from app.config import settings

# Token endpoint clients call to log in and receive a JWT access token
bearer_transport = BearerTransport(tokenUrl="api/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    # Returns JWT strategy configured with secret and token lifetime from settings
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


# The auth backend that fastapi-users mounts in the app; handles token verification
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
