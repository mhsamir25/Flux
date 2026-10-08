"""Provides UserManager and database dependencies for user authentication.
- UserManager extends UUIDIDMixin and BaseUserManager to manage User rows.
- Password hashing and verification are handled by fastapi-users internally (bcrypt).
- on_after_* hooks are no-ops because there is no email delivery system.
- get_user_db creates a SQLAlchemyUserDatabase over an async session.
- get_user_manager yields a UserManager instance for dependency injection.
"""
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import settings
from app.db import get_session


# Manages user accounts; uses UUID as primary key and inherits base user logic
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    # No-op hook: called after registration; no email delivery configured
    async def on_after_register(self, user: User, request: Optional[Request] = None) -> None:
        pass

    # No-op hook: called after forgot-password request; no email delivery configured
    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        pass

    # No-op hook: called after verify request; no email delivery configured
    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        pass


# Dependency that yields a SQLAlchemyUserDatabase tied to the current async session
async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)


# Dependency that yields a UserManager using the user database
async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
