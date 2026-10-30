"""
Columns (id, email, hashed_password, is_active, is_superuser, is_verified) come entirely
from the mixin; nothing app-specific to add yet. PipelineTemplate.owner_id will
foreign-key against this table's `id`.
"""
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass
