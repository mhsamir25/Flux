"""
current_user_optional is what makes guest mode possible: every public router depends on
it instead of current_active_user, so the same handler can attribute an execution or upload to
a logged-in user when a valid token is present, without ever requiring one — "Use a
current_user_optional dependency (returns User | None) rather than current_active_user on the
public routers."
"""
import uuid
from fastapi_users import FastAPIUsers
from app.auth.backend import auth_backend
from app.auth.manager import get_user_manager
from app.auth.models import User

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_user_optional = fastapi_users.current_user(active=True, optional=True)
