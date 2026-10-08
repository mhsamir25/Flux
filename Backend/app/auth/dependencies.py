"""Exports dependency callables used to enforce or optionally read authentication.
- FastAPIUsers is initialized with the User model and UUID ID type, plus the auth backend.
- current_active_user requires a valid JWT and an active user; raises if missing.
- current_user_optional returns the user if a valid token exists, else None; used by public routes.
"""
import uuid

from fastapi_users import FastAPIUsers

from app.auth.backend import auth_backend
from app.auth.manager import get_user_manager
from app.auth.models import User

# Initialize fastapi-users with the User ORM model, UUID primary key, and JWT backend
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dependency that enforces authentication: must have valid JWT + active user
current_active_user = fastapi_users.current_user(active=True)

# Dependency for public routes: returns User when token is present, None for guests
current_user_optional = fastapi_users.current_user(active=True, optional=True)
